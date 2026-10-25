# BookMyShow notification
A python script to notify as soon as tickets for a given show are available on BookMyShow

---

### Dependencies

Install dependencies using:<br />
`pip3 install -r requirements.txt`

---

### Usage

There are multiple fields required while running the script:
```
usage: ./BookMyShow.py [-h] -m MOVIE -c CINEMA [-f {2D,3D,IMAX 2D,IMAX 3D}] -d
                       DATE -r REGIONCODE [-i INTERVAL] [-a ALARM]
                       [-b ACCESS_TOKEN [DEVICE_ID ...]]

A script to check if tickets are available for the movie in the specified cinema at a given date

optional arguments:
  -h, --help            show this help message and exit
  -m MOVIE, --movie MOVIE
                        The movie you're looking to book tickets for
  -c CINEMA, --cinema CINEMA
                        The cinema in which you want to watch the movie
  -f {2D,3D,IMAX 2D,IMAX 3D}, --format {2D,3D,IMAX 2D,IMAX 3D}
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
python bms_cli.py venue BANG pvr
python bms_cli.py notify "Test" "Hello from bms_cli"
python bms_cli.py notify "Test" "Hello" --pushbullet TOKEN
python bms_cli.py alarm --kind bell --duration 2
python bms_cli.py alarm --kind file --path /path/to/alarm.mp3
```

- `region <query>` — search regions/cities by code, name, or alias.
- `venue <region_code> <query>` — search venues/cinemas within a region.
- `notify <title> <message>` — show a native macOS desktop notification (no CLI required). Add `--pushbullet TOKEN [DEVICE_ID]` to push via the Pushbullet API.
- `alarm --kind bell|sine|file [--path PATH] [--duration SECONDS]` — trigger a bounded test alarm.

Note: the venue endpoint is currently blocked by BookMyShow and returns HTTP 400.

---

### Notifications
Desktop notifications use the native macOS Notification Center (`osascript`), and Pushbullet pushes use the Pushbullet REST API directly — no `ntfy` CLI is required.

---

#### Hope you will be the first one to grab a ticket
