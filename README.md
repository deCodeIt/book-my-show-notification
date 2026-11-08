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
./deploy/start-bms.sh         # build the image and start the container
open http://localhost:7654
```

Create a watch in the UI: city → cinema → movie (or type a title for an upcoming release) → dates → format → save. When a showtime appears you get a Pushbullet push and the card flips to **found** with a deep link.

### Data location

State lives in a Docker **named volume** (`book-my-show-notification_bms_data`, referred to as `bms_data` in the compose file) backed by a plain directory on the internal SSD:

```
~/docker/drive/bms/bms.db                        # host directory (internal disk)
        ↕  book-my-show-notification_bms_data     # named volume, bind driver
/data                                            # inside the container
```

```bash
mkdir -p ~/docker/drive/bms        # required once, before the first start
```

`./deploy/start-bms.sh` creates the directory and the volume for you. Override the host directory with `BMS_DATA_DIR` (absolute path) in `.env`. Because it is on internal disk, the service never depends on an external drive being mounted, and neither `docker compose down` nor recreating the container deletes your watches (only `down -v` or `docker volume rm` would).

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
| `PORT` | `7654` | Host port published by the container (the app always listens on 7654 inside). Read by `./deploy/start-bms.sh` and baked into the launch agent. |

Get a Pushbullet token from pushbullet.com → Settings → Access Tokens, then add it under **Settings → Pushbullet recipients** in the UI. No environment variable is required — add one entry per person who wants alerts.

### Recipients

Add one entry per person in **Settings → Pushbullet recipients**; no environment variable is needed. Tokens are stored server-side in SQLite and only ever shown masked (`••••1234`).

Delivery is **per watch**: when you create or edit a watch you tick which recipients get that watch's alerts, so different people can follow different movies. Inside the wizard you can also paste a new token and it is added to the recipient list and selected for that watch in one step.

A recipient that fails (revoked token, network) is skipped; the others still get the alert. If every recipient for a watch fails, the watch stays **watching** and retries on the next tick, with the error shown on the card — so a transient failure never silently loses an alert.

### macOS: run it on this machine

Requirements: macOS with [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed (`/Applications/Docker.app`) and `/usr/local/bin/docker` available. Nothing else — no Python, no compose plugin, no Homebrew packages.

#### One-time setup

```bash
cp .env.example .env                 # 1. set APP_TOKEN, optionally change PORT
./deploy/install-launchagent.sh      # 2. build image, start container, install login agent
open http://localhost:7654           # 3. add watches + Pushbullet recipients in the UI
```

Then, so the service survives a reboot without you touching anything:

| Setting | Where | Why |
|---|---|---|
| *Start Docker Desktop when you sign in* | Docker Desktop → Settings → General | the daemon must be running for the container to come back |
| *Automatically log in as …* | System Settings → Users & Groups | launch agents only run after a user logs in |
| FileVault **off** | System Settings → Privacy & Security | with FileVault on, someone must unlock the disk before anything auto-starts |

#### What happens at login

`~/Library/LaunchAgents/com.local.bms-notifier.plist` runs one inline shell command:

1. if the Docker daemon is not up, start Docker Desktop and wait (up to 5 minutes);
2. if the container exists → `docker start bms-notifier`;
3. if the container is gone → recreate it from the local image `bms-notifier:latest` with `docker run` (port, volume and env inline);
4. the database is in the `bms_data` volume, so recreating never loses watches.

Nothing is copied outside the project: the image lives in Docker's local store, the data in the volume, and the specs in the plist. The plist is `chmod 600` because `APP_TOKEN` is embedded in it.

#### Why the plist holds the command

macOS blocks launchd-spawned processes from reading **external volumes** (`Operation not permitted`, exit `126`). This project can live on an external drive, so the agent cannot read a script or compose file from the repo — the command must be self-contained. That is also why the data volume and Docker itself must stay on the internal disk.

#### Everyday commands

```bash
./deploy/start-bms.sh                # rebuild image + recreate container (after code or .env changes)
./deploy/install-launchagent.sh      # same, plus re-write the plist (after .env changes or moving the project)
./deploy/uninstall-launchagent.sh    # remove the login agent; container keeps running
```

#### Verify

```bash
launchctl print "gui/$(id -u)/com.local.bms-notifier" | grep -E "state|last exit code"
curl -s http://localhost:7654/healthz

docker stop bms-notifier                                               # restart path
launchctl kickstart "gui/$(id -u)/com.local.bms-notifier"

docker rm -f bms-notifier                                              # recreate path
launchctl kickstart "gui/$(id -u)/com.local.bms-notifier"
```

Expected after each kickstart: `last exit code = 0` and `{"status":"ok"}`.

Logs: `/tmp/bms-notifier.log` (success lines) and `/tmp/bms-notifier.err` (failures). Both are wiped on reboot, so they only describe the current boot.

#### Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `last exit code = 126`, log says `Operation not permitted` | the agent tried to read the external-drive repo | you are running an old setup; re-run `./deploy/install-launchagent.sh` |
| `No such container: bms-notifier` | the container was deleted (Docker Desktop lost its state) | the current agent recreates it; run `launchctl kickstart "gui/$(id -u)/com.local.bms-notifier"` |
| Nothing in `/tmp/bms-notifier.log` | the agent never ran — no login, or the plist is not loaded | log in, then `launchctl bootstrap "gui/$(id -u)" ~/Library/LaunchAgents/com.local.bms-notifier.plist` |
| `ERROR: docker daemon unavailable` | Docker Desktop did not start in 5 minutes | open Docker Desktop manually and check *Start Docker Desktop when you sign in* |
| Browser shows a connection error | container stopped, or Docker is not running | `docker ps -a --filter name=bms-notifier`, then `./deploy/start-bms.sh` |
| UI login rejects the token | `APP_TOKEN` changed but the container was not recreated | `./deploy/start-bms.sh` |
| Watches look empty | container is using a different volume | `docker volume inspect book-my-show-notification_bms_data` should show `~/docker/drive/bms` |

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
