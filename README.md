# BookMyShow notification
A python script to notify as soon as tickets for a given show are available on BookMyShow

---

## Two ways to use this

1. **Docker service + web UI (recommended)** — a small container that polls in the background, pushes to Pushbullet, and serves its own browser UI at `http://localhost:7654`.
2. **CLI script** — the original one-shot command, documented under [CLI](#cli).

---

## Run as a Docker service

One container, one process, one SQLite file. It serves the web UI and polls BookMyShow in the background — no Redis, no worker queue, no build step.

### Quick start

```bash
cp .env.example .env          # set APP_TOKEN (auth for the web UI)
docker compose up -d --build
open http://localhost:7654
```

Create a watch in the UI: city → cinema → movie (or type a title for an upcoming release) → dates → format → save. When a showtime appears you get a Pushbullet push and the card flips to **found** with a deep link.

### Data location

State lives in a Docker **named volume** called `bms_data`, which is backed by a plain directory on the internal SSD:

```
~/docker/drive/bms/bms.db          # host directory (create it once)
        ↕  bms_data (named volume, bind driver)
/data                              # inside the container
```

```bash
mkdir -p ~/docker/drive/bms        # required once, before the first `up`
```

Override the host directory with `BMS_DATA_DIR` (absolute path) in `.env`. Because the directory is on internal disk, the service no longer depends on an external drive being mounted, and `docker compose down` never deletes your watches (that would need `-v`).

### Configuration

| Variable | Default | Purpose |
|---|---|---|
| `APP_TOKEN` | *(empty)* | Shared token protecting the UI/API. Empty disables auth — localhost / trusted LAN only. |
| `PUSHBULLET_TOKEN` | *(empty)* | Optional extra recipient for headless setups. Not needed — add recipients in the UI instead. |
| `BMS_DB_PATH` | `/data/bms.db` | SQLite file inside the container. `/data` is the `bms_data` volume. |
| `BMS_DATA_DIR` | `~/docker/drive/bms` | Host directory backing the `bms_data` volume. Must exist and be on internal disk. |
| `BMS_TIMEZONE` | `Asia/Kolkata` | Timezone used to resolve "today" / "tomorrow". |
| `BMS_DEFAULT_INTERVAL` | `60` | Default poll interval in seconds. |
| `BMS_POLL_TICK` | `5` | How often the scheduler wakes up. |
| `PORT` | `7654` | Host port published by compose (the container always listens on 7654). Local `python -m app` runs honour it too. |

Get a Pushbullet token from pushbullet.com → Settings → Access Tokens, then add it under **Settings → Pushbullet recipients** in the UI. No environment variable is required — add one entry per person who wants alerts.

### Recipients

Add one entry per person in **Settings → Pushbullet recipients**; no environment variable is needed. Tokens are stored server-side in SQLite and only ever shown masked (`••••1234`).

Delivery is **per watch**: when you create or edit a watch you tick which recipients get that watch's alerts, so different people can follow different movies. Inside the wizard you can also paste a new token and it is added to the recipient list and selected for that watch in one step.

A recipient that fails (revoked token, network) is skipped; the others still get the alert. If every recipient for a watch fails, the watch stays **watching** and retries on the next tick, with the error shown on the card — so a transient failure never silently loses an alert.

### Start on boot (macOS)

The container uses `restart: unless-stopped`, so if Docker Desktop is running at login the notifier comes back by itself. Also enable Docker Desktop → Settings → General → *Start Docker Desktop when you sign in*.

The LaunchAgent is the belt-and-braces option: it starts Docker Desktop if needed and brings the container back.

```bash
./deploy/install-launchagent.sh     # publishes the bundle, starts the service, installs + loads the agent
./deploy/uninstall-launchagent.sh   # removes the agent and bundle
```

`install-launchagent.sh` does everything, so a fresh machine only needs that one command after the first `docker compose up -d --build`.

#### Why there is a bundle

macOS denies launchd-spawned processes access to **external volumes**, so an agent cannot read a repo stored on one (it exits 126 with "Operation not permitted"). The scripts therefore publish a self-contained bundle to internal disk:

```
~/Library/Application Support/bms-notifier/
├── docker-compose.yml     # copy of the repo compose file (project/volume names pinned)
├── .env                   # resolved values, absolute paths, chmod 600
└── autostart.sh           # the runner launchd executes
```

`deploy/start-bms.sh` builds and starts from the repo, then refreshes that bundle. The agent runs the bundle, so at login it can **recreate** the container even if Docker Desktop lost all container definitions — the `bms_data` volume keeps your watches.

Re-run `./deploy/start-bms.sh` after editing `docker-compose.yml` or `.env` so the bundle picks up the change. Code changes need a rebuild, which only the repo path does.

#### Verify

```bash
launchctl print "gui/$(id -u)/com.local.bms-notifier" | grep -E "state|last exit code"
docker stop bms-notifier
launchctl kickstart "gui/$(id -u)/com.local.bms-notifier"   # restart path
curl -s http://localhost:7654/healthz
```

Logs: `/tmp/bms-notifier.log`, `/tmp/bms-notifier.err`, and `~/Library/Application Support/bms-notifier/compose.log` when the agent has to recreate the container.

### Notification rules

- A watch notifies **once**, on the transition from "no showtimes" to "showtimes listed", then stops polling and shows the match. **Pause/Resume** watches again; **Check now** probes without sending a push.
- Tickets count as available when the cinema lists at least one showtime for a title matching the watch (and the chosen format, if any). This mirrors the CLI's substring matching.
- Failed upstream requests are recorded on the card (`last error`) and retried on the next tick; they never stop the watch.
- Alerts go only to the recipients ticked on that watch; one failing token does not block the others.

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
| `GET` | `/api/settings` | Configured recipients (tokens always masked). |
| `POST` | `/api/settings/pushbullet` | Add a recipient `{token, label?, device?}`. |
| `PATCH` | `/api/settings/pushbullet/{id}` | Update a recipient's label/device/token. |
| `DELETE` | `/api/settings/pushbullet/{id}` | Remove a recipient. |
| `POST` | `/api/notifications/test` | Send a test push (`{recipient_ids}` to target, omit for all). |

### Development

```bash
python3.13 -m venv .venv
./.venv/bin/pip install -r requirements-server.txt pytest httpx
./.venv/bin/python -m pytest tests/test_service.py
APP_TOKEN=dev ./.venv/bin/python -m app     # http://localhost:7654
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
