# METAR Flight Category Alerts

Checks METARs every 5 minutes and sends a push notification when an airport
changes flight category (VFR / MVFR / IFR / LIFR). Runs free on GitHub Actions.
Notifications go through ntfy (free app for iPhone and Android).

## Setup (one time)

1. Create a **public** GitHub repository (public repos get unlimited free Actions
   minutes; a private repo would burn through the free tier at this frequency).
2. Upload these files, keeping the `.github/workflows/` folder path intact.
3. In the repo: **Settings > Secrets and variables > Actions > Variables**, add
   `NTFY_PREFIX` with a unique, hard-to-guess name, e.g. `acme-wx-7f3k`.
4. Edit `airports.txt` with the airports you want to watch.
5. Go to the **Actions** tab, enable workflows, open "METAR flight category
   alerts" and click **Run workflow** once. The first run records each airport's
   current category without alerting; alerts start on the next change.

## For pilots

1. Install the **ntfy** app.
2. Tap **+** and subscribe to `<NTFY_PREFIX>-<ICAO>` for each airport you want,
   e.g. `acme-wx-7f3k-KDEN`.

Deteriorating conditions arrive as high priority; improvements as normal priority.
Each alert includes the raw METAR.

To add an airport, add it to `airports.txt`. Pilots can then subscribe to it.

## Good to know

- GitHub runs scheduled jobs on a best-effort basis; delays of 5 to 15+ minutes
  happen, especially at busy times.
- GitHub pauses scheduled workflows in public repos after 60 days with no repo
  activity and emails you first. Re-enable from the Actions tab or push a commit.
- ntfy.sh topics are public to anyone who knows the name, which is why the
  prefix should be hard to guess. You can self-host ntfy and set `NTFY_SERVER`.
- Weather data comes from aviationweather.gov. This is a convenience alert, not
  an official weather briefing.
