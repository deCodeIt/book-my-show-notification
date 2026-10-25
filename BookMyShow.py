#!/usr/bin/env python3
import sys
from argparse import ArgumentParser
from time import sleep, time

from alarm import BellAlarm, SineBellAlarm, create_alarm
from availability import AvailabilityChecker
from bms_api import BookMyShowApi
from bmsTypes import BMSRegion, City, Venue
from http_client import CurlCffiHttpClient
from notifier import DesktopNotifier, NotificationService, PushbulletNotifier
from search import RegionFinder, VenueFinder
from ui import Selector


class BMS:
    """Facade that wires the SOLID services together.

    Kept as the public entry point/state holder for backward compatibility;
    every behaviour is delegated to a focused collaborator injected through
    the constructor (dependency inversion).
    """

    def __init__(
        self,
        args,
        http=None,
        api=None,
        notification_service=None,
        alarm=None,
        availability_checker=None,
        region_finder=None,
        venue_finder=None,
        selector=None,
    ):
        self.args = args
        self.region_code = args.regionCode.upper()
        self.date = args.date
        self.movie = args.movie
        self.format = args.format
        self.title = ""
        self.city: City = None
        self.cinema: Venue = None

        self.http = http or CurlCffiHttpClient()
        self.api = api or BookMyShowApi(self.http)
        self.region_finder = region_finder or RegionFinder()
        self.venue_finder = venue_finder or VenueFinder()
        self.selector = selector or Selector()

        pushbullet_arg = getattr(args, "pushBullet", None)
        pushbullet_notifiers = []
        if pushbullet_arg:
            token = pushbullet_arg[0]
            devices = pushbullet_arg[1:] if len(pushbullet_arg) > 1 else [None]
            pushbullet_notifiers = [PushbulletNotifier(token, device) for device in devices]

        self.notification_service = notification_service or NotificationService(
            desktop_notifier=DesktopNotifier(), pushbullet_notifiers=pushbullet_notifiers
        )
        self.alarm = alarm or create_alarm(args.alarm)
        self.availability_checker = availability_checker or AvailabilityChecker(
            api=self.api,
            notification_service=self.notification_service,
            alarm=self.alarm,
            movie=self.movie,
            movie_format=self.format,
            title=self.title,
        )

    # -- data access ------------------------------------------------------
    def fetchRegions(self) -> BMSRegion:
        return self.api.fetch_regions()

    def fetchVenues(self):
        return self.api.fetch_venues(self.city.RegionCode)

    def fetchCinemaPage(self):
        return self.api.fetch_cinema_page(self.getCinemaUrl())

    # -- search -----------------------------------------------------------
    def searchRegion(self, region: str):
        return self.region_finder.search(self.api, region)

    def searchVenue(self, region: str):
        return self.venue_finder.search(self.api, self.city.RegionCode, region)

    # -- selection --------------------------------------------------------
    def chooseRegion(self, regions) -> City:
        city = self.selector.choose_region(regions)
        self.setRegion(city)
        return city

    def chooseVenue(self, venues) -> Venue:
        cinema = self.selector.choose_venue(venues)
        self.setVenue(cinema)
        return cinema

    def setRegion(self, city: City) -> None:
        self.city = city

    def setVenue(self, cinema: Venue) -> None:
        self.cinema = cinema

    # -- availability -----------------------------------------------------
    def getCinemaUrl(self) -> str:
        url = self.api.build_cinema_url(self.city, self.cinema, self.date)
        print(f"Cinema Url {url}")
        return url

    def checkCinemaAvailability(self) -> bool:
        return self.availability_checker.check(
            self.cinema.VenueCode, self.city.RegionCode, self.date
        )

    # -- notifications & alarm (backward-compatible wrappers) -------------
    def notification(self, title: str, message: str) -> None:
        self.notification_service.notify(title, message)

    def soundAlarm(self) -> None:
        self.alarm.sound()

    def ringBell(self) -> None:
        BellAlarm().sound()

    def ringSineBell(self) -> None:
        SineBellAlarm().sound()


def parser():
    parser = ArgumentParser(
        prog=sys.argv[0],
        description="A script to check if tickets are available for the movie in the specified cinema at a given date",
        epilog="And you will be the first one to be notified as soon as the show is available",
    )
    parser.add_argument("-m", "--movie", required=True, action="store", type=str,
                        help="The movie you're looking to book tickets for")
    parser.add_argument("-c", "--cinema", required=True, action="store", type=str,
                        help="The cinema in which you want to watch the movie")
    parser.add_argument("-f", "--format", action="store",
                        choices=["2D", "3D", "IMAX 2D", "IMAX 3D"], type=str,
                        help="Preferred format, if any")
    parser.add_argument("-d", "--date", action="store", type=str,
                        help="Format: YYYYMMDD | The date on which you want to book tickets.")
    parser.add_argument("-r", "--regionCode", required=True, action="store", type=str,
                        help="The region code of your area; BANG for Bengaluru")
    parser.add_argument("-i", "--interval", action="store", type=int,
                        help="BMS server will be queried every interval seconds", default=60)
    parser.add_argument("-a", "--alarm", action="store", type=str,
                        help="Path to audio file that will play as an alarm when notified ( optional )")
    parser.add_argument("-b", "--pushBullet", action="store", metavar=("ACCESS_TOKEN", "DEVICE_ID"),
                        type=str, nargs="+", help="Send notification to your device using pushbullet")
    return parser.parse_args()


def main():
    args = parser()
    interval = args.interval
    status = False
    bms = BMS(args)

    regions = bms.searchRegion(args.regionCode)
    bms.chooseRegion(regions)
    venues = bms.searchVenue(args.cinema)
    bms.chooseVenue(venues)
    print(f"Selected {bms.cinema.VenueName} in region {bms.city.RegionName}")

    while not status:
        start = time()
        retry = 0
        while retry < 60:
            try:
                status = bms.checkCinemaAvailability()
                break
            except AssertionError:
                print("Seems like we lost the connection mid-way, will retry...")
                retry += 1
            except KeyboardInterrupt:
                sys.exit(1)
            except Exception as e:
                print("Something unexpected happened; Recommended to re-run this script with correct values")
                print("Printing traceback:")
                print(e)
                break
        if not status:
            try:
                stop = time()
                time_remaining = interval - (stop - start)
                time_remaining = int(round(time_remaining if time_remaining > 0 else 0))
                sleep(time_remaining)
            except KeyboardInterrupt:
                sys.exit(1)
            except Exception as e:
                print("Something unexpected happened; Recommended to re-run this script with correct values")
                break


if __name__ == "__main__":
    main()
