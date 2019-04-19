# BookMyShow notification
A python script to notify as soon as tickets for a given show are available on BookMyShow

---

### Dependencies

Install dependencies using:<br />
`pip3 install -r requirements.txt`

There are multiple fields required while running the script:
```
usage: ./BookMyShow.py [-h] -m MOVIE -c CINEMA -d DATE -r REGIONCODE [-i INTERVAL]

A script to check if tickets are available for the movie in the specified cinema at a given date

optional arguments:
  -h, --help            show this help message and exit
  -m MOVIE, --movie MOVIE
                        The movie you're looking to book tickets for
  -c CINEMA, --cinema CINEMA
                        The cinema in which you want to watch the movie
  -d DATE, --date DATE  Format: YYYYMMDD | The date on which you want to book tickets.
  -r REGIONCODE, --regionCode REGIONCODE
                        The region code of your area; BANG for Bengaluru
  -i INTERVAL, --interval INTERVAL
                        BMS server will be queried every interval seconds

And you will be the first one to be notified as soon as the show is available
```

To check for shows one can run similar commands:<br />
`./BookMyShow.py --movie "Avengers: Endgame" --cinema "PVR Forum Mall Koramangala" --date "20190426" --regionCode "BANG"`

---

### Caveats
There are known issues when using desktop notification with `tmux`. It's highly recommended *not* to run this script inside tmux if you want desktop notifications.

Hope you get your tickets for the movie as soon as possible
