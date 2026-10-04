import json
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WATCH_PATH = ROOT / "metar-alerts" / "watch.py"

spec = importlib.util.spec_from_file_location("watch", WATCH_PATH)
watch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(watch)


def test_parse_vis_handles_common_formats():
    assert watch.parse_vis(10) == 10.0
    assert watch.parse_vis("10+") == 10.0
    assert watch.parse_vis("1 1/2") == 1.5
    assert watch.parse_vis("M1/4") == 0.25
    assert watch.parse_vis("bogus") is None


def test_parse_ceiling_extracts_bkn_ovc_layer():
    raw = "KDEN 2024/01/01 12:00Z BKN006 OVC010 10SM"
    assert watch.parse_ceiling(raw) == 600


def test_compute_category():
    assert watch.compute_category(600, 10) == "IFR"
    assert watch.compute_category(1500, 5) == "MVFR"
    assert watch.compute_category(4000, 10) == "VFR"
    assert watch.compute_category(200, 0.5) == "LIFR"


def test_get_category_prefers_fltcat_when_present():
    ob = {"fltCat": "IFR"}
    assert watch.get_category(ob) == "IFR"


def test_get_category_falls_back_to_computed_visibility_and_ceiling():
    ob = {"rawOb": "KDEN 12Z BKN006 OVC010 2SM", "visib": "2"}
    assert watch.get_category(ob) == "IFR"


def test_load_airports_ignores_comments_and_duplicates(tmp_path, monkeypatch):
    airports_file = tmp_path / "airports.txt"
    airports_file.write_text(
        "KDEN\nkdsm # comment\nKDEN\n1234\n12345\n"
    )
    monkeypatch.setattr(watch, "AIRPORTS_FILE", airports_file)

    assert watch.load_airports() == ["KDEN", "KDSM", "1234"]


def test_save_and_load_state_round_trip(tmp_path, monkeypatch):
    state_file = tmp_path / "state.json"
    monkeypatch.setattr(watch, "STATE_FILE", state_file)

    watch.save_state({"KDEN": "VFR", "KJFK": "IFR"})
    assert json.loads(state_file.read_text()) == {"KDEN": "VFR", "KJFK": "IFR"}
    assert watch.load_state() == {"KDEN": "VFR", "KJFK": "IFR"}
