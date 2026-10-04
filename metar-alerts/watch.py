#!/usr/bin/env python3
"""Watch METARs and send an ntfy push alert when an airport's flight category changes.

Each airport gets its own ntfy topic: <NTFY_PREFIX>-<ICAO>  (e.g. mywx-KDEN).
Pilots subscribe in the ntfy app to the airports they care about.
Standard library only, no pip installs needed.
"""
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

API = "https://aviationweather.gov/api/data/metar"
ROOT = Path(__file__).resolve().parent
AIRPORTS_FILE = ROOT / "airports.txt"
STATE_FILE = ROOT / "state.json"
NTFY_SERVER = (os.environ.get("NTFY_SERVER") or "https://ntfy.sh").rstrip("/")
NTFY_PREFIX = (os.environ.get("NTFY_PREFIX") or "").strip()
USER_AGENT = "metar-category-alerts/1.0"

ORDER = ["VFR", "MVFR", "IFR", "LIFR"]
EMOJI = {"VFR": "green_circle", "MVFR": "large_blue_circle",
         "IFR": "red_circle", "LIFR": "purple_circle"}


def load_airports():
    ids = []
    for line in AIRPORTS_FILE.read_text().splitlines():
        code = line.split("#", 1)[0].strip().upper()
        if not code:
            continue
        if not re.fullmatch(r"[A-Z0-9]{3,4}", code):
            print(f"Skipping invalid airport id: {code!r}")
            continue
        if code not in ids:
            ids.append(code)
    return ids


def load_state():
    try:
        return json.loads(STATE_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")


def fetch_metars(ids):
    """Return {ICAO: latest METAR dict} from aviationweather.gov."""
    result = {}
    for i in range(0, len(ids), 100):
        chunk = ids[i:i + 100]
        url = f"{API}?ids={','.join(chunk)}&format=json"
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8").strip()
        if not body:
            continue
        for ob in json.loads(body):
            icao = (ob.get("icaoId") or "").upper()
            if not icao:
                continue
            prev = result.get(icao)
            if prev is None or (ob.get("obsTime") or 0) > (prev.get("obsTime") or 0):
                result[icao] = ob
    return result


def parse_vis(v):
    """Visibility in statute miles. Handles 10, '10+', '1 1/2', 'M1/4'."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).upper()
    for junk in ("SM", "+", "P", "M"):
        s = s.replace(junk, "")
    try:
        total = 0.0
        for part in s.split():
            if "/" in part:
                n, d = part.split("/")
                total += float(n) / float(d)
            else:
                total += float(part)
        return total
    except (ValueError, ZeroDivisionError):
        return None


def parse_ceiling(raw):
    """Lowest BKN/OVC/VV layer in feet AGL, from the raw METAR (remarks ignored)."""
    if not raw:
        return None
    body = raw.split(" RMK", 1)[0]
    bases = [int(h) * 100 for h in re.findall(r"\b(?:BKN|OVC|VV)(\d{3})", body)]
    return min(bases) if bases else None


def compute_category(ceiling, vis):
    if ceiling is None and vis is None:
        return None
    c = ceiling if ceiling is not None else 99999
    v = vis if vis is not None else 99
    if c < 500 or v < 1:
        return "LIFR"
    if c < 1000 or v < 3:
        return "IFR"
    if c <= 3000 or v <= 5:
        return "MVFR"
    return "VFR"


def get_category(ob):
    cat = (ob.get("fltCat") or "").upper()
    if cat in ORDER:
        return cat
    return compute_category(parse_ceiling(ob.get("rawOb")), parse_vis(ob.get("visib")))


def notify(icao, old, new, ob):
    worse = ORDER.index(new) > ORDER.index(old)
    headers = {
        "Title": f"{icao}: {old} -> {new}",
        "Tags": f"{EMOJI[new]},{'arrow_down' if worse else 'arrow_up'}",
        "Priority": "high" if worse else "default",
        "User-Agent": USER_AGENT,
    }
    body = (ob.get("rawOb") or f"{icao} is now {new}").encode("utf-8")
    url = f"{NTFY_SERVER}/{NTFY_PREFIX}-{icao}"
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=15) as resp:
        resp.read()


def main():
    if not NTFY_PREFIX:
        sys.exit("NTFY_PREFIX is not set. Add it as a repository variable (see README).")

    airports = load_airports()
    if not airports:
        sys.exit("airports.txt has no airports.")
    state = load_state()

    try:
        obs = fetch_metars(airports)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
        print(f"METAR fetch failed, will retry next run: {e}")
        return

    for icao in airports:
        ob = obs.get(icao)
        if not ob:
            print(f"{icao}: no current METAR")
            continue
        new = get_category(ob)
        if not new:
            print(f"{icao}: could not determine category")
            continue
        old = state.get(icao)
        if old and old != new:
            try:
                notify(icao, old, new, ob)
                print(f"{icao}: {old} -> {new} (alert sent)")
            except (urllib.error.URLError, TimeoutError) as e:
                print(f"{icao}: {old} -> {new} but alert failed, will retry: {e}")
                continue  # keep old state so the alert is retried
        elif not old:
            print(f"{icao}: starting at {new} (no alert on first sighting)")
        else:
            print(f"{icao}: {new} (no change)")
        state[icao] = new

    save_state({k: v for k, v in state.items() if k in airports})


if __name__ == "__main__":
    main()
