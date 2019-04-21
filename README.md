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
`./BookMyShow.py --movie "Avengers: Endgame" --cinema "PVR Forum Mall Koramangala" --date "20190426" --regionCode "BANG" --format "IMAX 3D"`

---

### Caveats
There are known issues when using desktop notification with `tmux`. It's highly recommended **not** to run this script inside tmux if you want desktop notifications.

---

#### Hope you will be the first one to grab a ticket
