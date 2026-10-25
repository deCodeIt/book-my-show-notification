#!/usr/bin/env python3
"""Alternate CLI to exercise the individual components directly.

Examples:
    python bms_cli.py region bang
    python bms_cli.py venue BANG pvr
    python bms_cli.py movie bang
    python bms_cli.py movie bang --languages hindi
    python bms_cli.py notify "Test" "Hello from bms_cli"
    python bms_cli.py notify "Test" "Hello" --pushbullet TOKEN
    python bms_cli.py alarm --kind bell --duration 2
    python bms_cli.py alarm --kind file --path /path/to/alarm.mp3
"""
import sys
from argparse import ArgumentParser
from shutil import which

from curl_cffi.requests.exceptions import HTTPError

from bms_api import BookMyShowApi
from http_client import CurlCffiHttpClient
from search import RegionFinder, VenueFinder


def build_components():
    api = BookMyShowApi(CurlCffiHttpClient())
    return api, RegionFinder(), VenueFinder()


def print_regions(results):
    for index, region in enumerate(results, start=1):
        aliases = ", ".join(region.Alias) if region.Alias else ""
        suffix = f"  [aliases: {aliases}]" if aliases else ""
        print(f"{index}. {region.RegionCode}: {region.RegionName}{suffix}")


def print_venues(results):
    for index, venue in enumerate(results, start=1):
        print(f"{index}. {venue.VenueCode}: {venue.VenueName}")


def cmd_region(args):
    api, region_finder, _ = build_components()
    results = region_finder.search(api, args.query)
    if not results:
        print(f"No regions found for '{args.query}'")
        return 1
    print(f"Matching regions for '{args.query}':")
    print_regions(results)
    return 0


def cmd_venue(args):
    api, _, venue_finder = build_components()
    try:
        results = venue_finder.search(api, args.region_code, args.query)
    except HTTPError as exc:
        print(f"Venue endpoint rejected the request ({exc}).")
        print("It is currently blocked by BookMyShow; try a different endpoint/params.")
        return 1
    if not results:
        print(f"No venues found for '{args.query}' in {args.region_code}")
        return 1
    print(f"Matching venues for '{args.query}' in {args.region_code}:")
    print_venues(results)
    return 0


def cmd_movie(args):
    api, region_finder, _ = build_components()
    cities = region_finder.search(api, args.region)
    if not cities:
        print(f"No region found for '{args.region}'")
        return 1
    city = cities[0]

    try:
        movies = api.fetch_movies(city.RegionCode, city.RegionSlug, args.languages, city.Lat, city.Long)
    except HTTPError as exc:
        print(f"Movies endpoint rejected the request ({exc}).")
        return 1

    if not movies:
        print("No movies found.")
        return 1

    language_note = f", language: {args.languages}" if args.languages else ""
    print(f"Movies in {city.RegionName} ({city.RegionCode}){language_note}:")
    for index, movie in enumerate(movies, start=1):
        extra = ", ".join(part for part in (movie.language, movie.genre) if part)
        suffix = f"  [{extra}]" if extra else ""
        print(f"{index}. {movie.name}{suffix}  ({movie.event_code})")
    return 0


def cmd_notify(args):
    from notifier import DesktopNotifier, PushbulletNotifier

    try:
        if args.pushbullet:
            token = args.pushbullet[0]
            devices = args.pushbullet[1:] if len(args.pushbullet) > 1 else [None]
            for device in devices:
                PushbulletNotifier(token, device).send(args.title, args.message)
        else:
            if which("osascript") is None:
                print("'osascript' is not available (macOS only) — cannot show desktop notification.")
                return 1
            DesktopNotifier().send(args.title, args.message)
    except Exception as exc:
        print(f"Notification failed: {type(exc).__name__}: {exc}")
        if args.pushbullet:
            print("Hint: check your pushbullet access token and network connection.")
        return 1
    print(f"Sent '{args.title}' — check your desktop/pushbullet for the notification.")
    return 0


def cmd_alarm(args):
    from alarm import AudioFileAlarm, BellAlarm, SineBellAlarm

    if args.kind == "sine" and which("play") is None:
        print("'play' (sox) is not installed. Install it first, e.g.: brew install sox")
        return 1
    if args.kind == "file" and not args.path:
        print("--path is required when --kind file is used")
        return 1

    if args.kind == "bell":
        alarm = BellAlarm()
    elif args.kind == "sine":
        alarm = SineBellAlarm()
    else:
        alarm = AudioFileAlarm(args.path)

    print(f"Sounding {args.kind} alarm for {args.duration}s... (Ctrl-C to stop)")
    try:
        alarm.sound(max_seconds=args.duration)
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        print(f"Alarm failed: {type(exc).__name__}: {exc}")
        if args.kind == "file":
            print("Hint: playsound on macOS needs PyObjC -> pip install PyObjC")
        return 1
    return 0


def main(argv=None):
    parser = ArgumentParser(
        prog="bms_cli.py",
        description="Search BookMyShow regions and venues directly (for testing/debugging)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    region_parser = subparsers.add_parser("region", help="search regions/cities")
    region_parser.add_argument("query", help="region code, name, or alias (e.g. bang)")
    region_parser.set_defaults(func=cmd_region)

    venue_parser = subparsers.add_parser("venue", help="search venues/cinemas within a region")
    venue_parser.add_argument("region_code", help="region code (e.g. BANG)")
    venue_parser.add_argument("query", help="venue code or name (e.g. pvr)")
    venue_parser.set_defaults(func=cmd_venue)

    movie_parser = subparsers.add_parser("movie", help="list movies in a region")
    movie_parser.add_argument("region", help="region code, name, or alias (e.g. bang)")
    movie_parser.add_argument("--languages", help="language filter (e.g. hindi,english)")
    movie_parser.set_defaults(func=cmd_movie)

    notify_parser = subparsers.add_parser("notify", help="send a test notification")
    notify_parser.add_argument("title", help="notification title")
    notify_parser.add_argument("message", help="notification message")
    notify_parser.add_argument("--pushbullet", nargs="+", metavar=("TOKEN", "DEVICE_ID"),
                               help="send via pushbullet (optionally to a specific device id)")
    notify_parser.set_defaults(func=cmd_notify)

    alarm_parser = subparsers.add_parser("alarm", help="trigger a test alarm")
    alarm_parser.add_argument("--kind", choices=["bell", "sine", "file"], default="bell",
                              help="alarm type (default: bell)")
    alarm_parser.add_argument("--path", help="audio file path (required for --kind file)")
    alarm_parser.add_argument("--duration", type=float, default=2.0,
                              help="seconds to sound the alarm (default: 2)")
    alarm_parser.set_defaults(func=cmd_alarm)

    args = parser.parse_args(argv)
    try:
        sys.exit(args.func(args))
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as exc:
        print(f"error: {type(exc).__name__}: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
