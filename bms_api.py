from datetime import datetime
from re import sub as reSub
from typing import Optional

from bs4 import BeautifulSoup

from bmsTypes import BMSRegion, BMSVenue, City, Venue
from http_client import HttpClient


class BookMyShowApi:
    """Data access for the BookMyShow endpoints.

    This is the only class that should change when BookMyShow's API changes
    (single responsibility). It depends on the ``HttpClient`` abstraction
    rather than a concrete implementation (dependency inversion).
    """

    REGIONS_URL = "https://in.bookmyshow.com/api/explore/v1/discover/regions"
    VENUES_URL = "https://in.bookmyshow.com/pwa/api/de/venues?regionCode={region_code}&eventType=MT"

    def __init__(self, http: HttpClient):
        self.http = http

    def fetch_regions(self) -> BMSRegion:
        return BMSRegion.parse_raw(self.http.get(self.REGIONS_URL))

    def fetch_venues(self, region_code: str) -> BMSVenue:
        url = self.VENUES_URL.format(region_code=region_code)
        return BMSVenue.parse_raw(self.http.get(url))

    def build_cinema_url(self, city: City, cinema: Venue, date: Optional[str] = None) -> str:
        current_date = datetime.now().strftime("%Y%m%d") if date is None else date
        venue_name = reSub("[^0-9a-zA-Z ]+", "", cinema.VenueName).lower().replace(" ", "-")
        return (
            f"https://in.bookmyshow.com/buytickets/{venue_name}"
            f"/cinema-{city.RegionCode.lower()}-{cinema.VenueCode}-MT/{current_date}"
        )

    def fetch_cinema_page(self, cinema_url: str) -> BeautifulSoup:
        return BeautifulSoup(self.http.get(cinema_url), "html5lib")
