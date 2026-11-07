# BookMyShow notification
A python script to notify as soon as tickets for a given show are available on BookMyShow

---

## Two ways to use this

1. **Docker service + web UI (recommended)** — a small container that polls in the background, pushes to Pushbullet, and serves its own browser UI at `http://localhost:8080`.
2. **CLI script** — the original one-shot command, documented under [CLI](#cli).

---

## Run as a Docker service

One container, one process, one SQLite file. It serves the web UI and polls BookMyShow in the background — no Redis, no worker queue, no build step.

### Quick start

```bash
cp .env.example .env          # then edit APP_TOKEN (and optionally PUSHBULLET_TOKEN)
docker compose up -d --build
open http://localhost:8080
```

Create a watch in the UI: city → cinema → movie (or type a title for an upcoming release) → dates → format → save. When a showtime appears you get a Pushbullet push and the card flips to **found** with a deep link.

### Configuration

| Variable | Default | Purpose |
|---|---|---|
| `APP_TOKEN` | *(empty)* | Shared token protecting the UI/API. Empty disables auth — localhost / trusted LAN only. |
| `PUSHBULLET_TOKEN` | *(empty)* | Pushbullet access token. Overrides any token saved in Settings. |
| `BMS_DB_PATH` | `/data/bms.db` | SQLite file; mount `/data` as a volume. |
| `BMS_TIMEZONE` | `Asia/Kolkata` | Timezone used to resolve "today" / "tomorrow". |
| `BMS_DEFAULT_INTERVAL` | `60` | Default poll interval in seconds. |
| `BMS_POLL_TICK` | `5` | How often the scheduler wakes up. |
| `PORT` | `8080` | HTTP port inside the container. |

Get a Pushbullet token from pushbullet.com → Settings → Access Tokens. You can save it in the UI (**Settings**) instead of the environment; the env value wins.

### Start on boot (macOS)

Docker Desktop → Settings → General → *Start Docker Desktop when you log in*. The container already uses `restart: unless-stopped`.

For belt-and-braces (launches Docker too if it isn't running):

```bash
./deploy/install-launchagent.sh     # installs ~/Library/LaunchAgents/com.local.bms-notifier.plist
./deploy/uninstall-launchagent.sh   # removes it
```

Logs: `/tmp/bms-notifier.log` and `/tmp/bms-notifier.err`.

### Notification rules

- A watch notifies **once**, on the transition from "no showtimes" to "showtimes listed", then stops polling and shows the match. **Pause/Resume** watches again; **Check now** probes without sending a push.
- Tickets count as available when the cinema lists at least one showtime for a title matching the watch (and the chosen format, if any). This mirrors the CLI's substring matching.
- Failed upstream requests are recorded on the card (`last error`) and retried on the next tick; they never stop the watch.

### API

The UI is a thin client over a JSON API. Every endpoint needs the token — either the login cookie or `Authorization: Bearer <token>`:

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/healthz` | Liveness probe (no auth). |
| `GET` | `/api/regions?q=` | City/region autocomplete. |
| `GET` | `/api/venues?region=BANG&q=` | Cinema autocomplete. |
| `GET` | `/api/movies?region=BANG&q=` | Now-showing movies. |
| `GET` / `POST` | `/api/watches` | List / create watches. |
| `PATCH` / `DELETE` | `/api/watches/{id}` | Edit, pause/resume, delete. |
| `POST` | `/api/watches/{id}/check` | Check now (no notification). |
| `GET` | `/api/watches/{id}/history` | Recent checks. |
| `GET` / `PATCH` | `/api/settings` | Pushbullet config (token is always masked). |
| `POST` | `/api/notifications/test` | Send a test push. |

### Development

```bash
python3.13 -m venv .venv
./.venv/bin/pip install -r requirements-server.txt pytest httpx
./.venv/bin/python -m pytest tests/test_service.py
APP_TOKEN=dev ./.venv/bin/python -m app     # http://localhost:8080
```

The service reuses [bms_api.py](./bms_api.py), [search.py](./search.py), [notifier.py](./notifier.py) and [bmsTypes.py](./bmsTypes.py). `alarm.py`, `ui.py` and the desktop-only dependencies are only needed by the CLI and are not in the image.

---

## CLI

### Dependencies

Install dependencies using:<br />
`pip3 install -r requirements.txt`

---

### Usage

There are multiple fields required while running the script:
```
usage: ./BookMyShow.py [-h] -m MOVIE -c CINEMA [-f {2D,3D,4DX,DOLBY CINEMA 2D,2D SCREEN X,4DX 3D,IMAX 2D,IMAX 3D,ICE,3D SCREEN X,EPIQ 3D,DOLBY CINEMA 3D,MX4D 3D,HDR By Barco,ICE 3D}] -d
                       DATE -r REGIONCODE [-i INTERVAL] [-a ALARM]
                       [-b ACCESS_TOKEN [DEVICE_ID ...]]

A script to check if tickets are available for the movie in the specified cinema at a given date

optional arguments:
  -h, --help            show this help message and exit
  -m MOVIE, --movie MOVIE
                        The movie you're looking to book tickets for
  -c CINEMA, --cinema CINEMA
                        The cinema in which you want to watch the movie
  -f {2D,3D,4DX,DOLBY CINEMA 2D,2D SCREEN X,4DX 3D,IMAX 2D,IMAX 3D,ICE,3D SCREEN X,EPIQ 3D,DOLBY CINEMA 3D,MX4D 3D,HDR By Barco,ICE 3D}, --format {2D,3D,4DX,DOLBY CINEMA 2D,2D SCREEN X,4DX 3D,IMAX 2D,IMAX 3D,ICE,3D SCREEN X,EPIQ 3D,DOLBY CINEMA 3D,MX4D 3D,HDR By Barco,ICE 3D}
                        Preferred format, if any
  -d DATE, --date DATE  Format: YYYYMMDD | The date on which you want to book tickets.
  -r REGIONCODE, --regionCode REGIONCODE
                        The region code of your area; BANG for Bengaluru
  -i INTERVAL, --interval INTERVAL
                        BMS server will be queried every interval seconds
  -a ALARM, --alarm ALARM
                        Path to audio file that will play as an alarm when notified ( optional )
  -b ACCESS_TOKEN [DEVICE_ID ...], --pushBullet ACCESS_TOKEN [DEVICE_ID ...]
                        Send notification to your device using pushbullet

And you will be the first one to be notified as soon as the show is available
```

To check for shows one can run similar commands:<br />
`./BookMyShow.py --movie "avengers" --cinema "pvr" --date "20190426" --regionCode "BANG" --format "3D"`  
`./BookMyShow.py --movie "flash" --cinema "nexus" --date "20230619" --regionCode "BANG" --format "3D"`
`./BookMyShow.py --movie "flash" --cinema "nexus" --date "20230619" --regionCode "BANG"`

---

### Testing individual components

An alternate CLI lets you exercise the components directly:

```
python bms_cli.py region bang
python bms_cli.py venue BANG
python bms_cli.py venue BANG pvr
python bms_cli.py movie bang
python bms_cli.py movie bang --languages hindi
python bms_cli.py notify "Test" "Hello from bms_cli"
python bms_cli.py notify "Test" "Hello" --pushbullet TOKEN
python bms_cli.py alarm --kind bell --duration 2
python bms_cli.py alarm --kind file --path /path/to/alarm.mp3
```

- `region <query>` — search regions/cities by code, name, or alias.
- `venue <region_code> [query]` — list venues/cinemas within a region (optionally filtered by code/name).
- `movie <region> [--languages LANG]` — list movies currently showing in a region.
- `notify <title> <message>` — show a native macOS desktop notification (no CLI required). Add `--pushbullet TOKEN [DEVICE_ID]` to push via the Pushbullet API.
- `alarm --kind bell|sine|file [--path PATH] [--duration SECONDS]` — trigger a bounded test alarm.

Note: the venues endpoint used by the app is `https://in.bookmyshow.com/api/v2/mobile/venues`.

---

### Notifications
Desktop notifications use the native macOS Notification Center (`osascript`), and Pushbullet pushes use the Pushbullet REST API directly — no `ntfy` CLI is required.

---

#### Hope you will be the first one to grab a ticket
