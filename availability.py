from typing import List, Optional

from alarm import Alarm
from bms_api import BookMyShowApi
from bmsTypes import CinemaPageApiResponse
from notifier import NotificationService


class AvailabilityChecker:
    """Decides whether the requested movie/format is available and reacts.

    Depends on abstractions (``BookMyShowApi``, ``NotificationService``,
    ``Alarm``) rather than the old God-class, so the parsing logic is isolated
    and can be swapped without touching the rest of the program.
    """

    def __init__(
        self,
        api: BookMyShowApi,
        notification_service: NotificationService,
        alarm: Alarm,
        movie: str,
        movie_format: Optional[str] = None,
        title: str = "",
    ):
        self.api = api
        self.notification_service = notification_service
        self.alarm = alarm
        self.movie = movie
        self.movie_format = movie_format
        self.title = title

    def check(self, venue_code: str, region_code: str, date: Optional[str] = None) -> bool:
        show_details = self.api.fetch_cinema_showtimes(venue_code, region_code, date)

        format_available = " in " + self.movie_format if self.movie_format else ""

        if self._is_movie_available(show_details):
            print("HURRAY! Movie tickets are now available" + format_available)
            message = "Tickets for " + self.movie + " at " + self.title + " are now available" + format_available
            self.notification_service.notify("Hurray!", message)
            self.alarm.sound()
            return True

        if show_details is None or not show_details.ShowDetails:
            print("Movie tickets aren't available yet, retrying...")
            return False

        available_formats = self._available_formats(show_details)
        if available_formats:
            print("The available format(s) : " + ", ".join(available_formats))
            print("Movie is not available in requested " + self.movie_format + " format, will retry...")
            return False

        print("Movie tickets aren't available yet, retrying....")
        return False

    def _is_movie_available(self, show_details: Optional[CinemaPageApiResponse]) -> bool:
        if show_details is None or len(show_details.ShowDetails) == 0:
            return False
        for event in show_details.ShowDetails[0].Event:
            if self.movie.lower() in event.EventTitle.lower():
                for child in event.ChildEvents:
                    if self.movie_format is None or child.EventDimension == self.movie_format:
                        return True
        return False

    def _available_formats(self, show_details: CinemaPageApiResponse) -> List[str]:
        formats = []
        for event in show_details.ShowDetails[0].Event:
            if self.movie.lower() in event.EventTitle.lower():
                for child in event.ChildEvents:
                    if child.EventDimension not in formats:
                        formats.append(child.EventDimension)
        return formats

