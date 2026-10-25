import json
from datetime import datetime
from random import randint
from re import sub as reSub
from time import time
from typing import List, Optional

from bs4 import BeautifulSoup

from bmsTypes import BMSRegion, BMSVenue, City, Movie, Venue
from http_client import HttpClient


class BookMyShowApi:
    """Data access for the BookMyShow endpoints.

    This is the only class that should change when BookMyShow's API changes
    (single responsibility). It depends on the ``HttpClient`` abstraction
    rather than a concrete implementation (dependency inversion).
    """

    REGIONS_URL = "https://in.bookmyshow.com/api/explore/v1/discover/regions"
    VENUES_URL = "https://in.bookmyshow.com/pwa/api/de/venues?regionCode={region_code}&eventType=MT"
    MOVIES_URL = "https://in.bookmyshow.com/api/explore/v1/discover/movies-{region_slug}"

    def __init__(self, http: HttpClient):
        self.http = http

    def fetch_regions(self) -> BMSRegion:
        return BMSRegion.parse_raw(self.http.get(self.REGIONS_URL))

    def fetch_venues(self, region_code: str) -> BMSVenue:
        url = self.VENUES_URL.format(region_code=region_code)
        return BMSVenue.parse_raw(self.http.get(url))

    def fetch_movies(
        self,
        region_code: str,
        region_slug: str,
        languages: Optional[str] = None,
        lat: Optional[str] = None,
        lon: Optional[str] = None,
    ) -> List[Movie]:
        """Returns movies currently listed for a region (optionally filtered)."""
        url = self.MOVIES_URL.format(region_slug=region_slug)
        params = {"region": region_code, "embedded": "true"}
        if languages:
            params["languages"] = languages
        if lat:
            params["lat"] = lat
        if lon:
            params["lon"] = lon

        headers = {
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://in.bookmyshow.com/explore/movies-{slug}{query}".format(
                slug=region_slug, query="?languages=" + languages if languages else ""
            ),
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.6.2 Safari/605.1.15",
            "x-region-code": region_code,
            "x-region-slug": region_slug,
            "x-app-code": "WEB",
            "x-platform-code": "DESKTOP-WEB",
            "x-platform": "WEB",
            "x-bms-id": f"1.{randint(100000000, 999999999)}.{int(time() * 1000)}",
            "x-location-selection": "manual",
        }
        if lat:
            headers["x-latitude"] = lat
        if lon:
            headers["x-longitude"] = lon

        payload = json.loads(self.http.get(url, params=params, headers=headers))
        return self._extract_movies(payload)

    def _extract_movies(self, payload: dict) -> List[Movie]:
        movies = []
        for listing in payload.get("listings", []):
            for card in listing.get("cards", []):
                analytics = card.get("analytics") or {}
                event_code = analytics.get("event_code") or ""
                if not event_code:
                    continue  # skip non-movie cards (e.g. "Coming Soon")
                image = card.get("image") or {}
                movies.append(
                    Movie.parse_obj(
                        {
                            "name": analytics.get("title") or card.get("seoText") or "",
                            "event_code": event_code,
                            "event_group": analytics.get("event_group") or "",
                            "genre": analytics.get("genre") or "",
                            "language": analytics.get("language") or "",
                            "poster_url": image.get("url"),
                            "url": card.get("ctaUrl"),
                        }
                    )
                )
        return movies

    def build_cinema_url(self, city: City, cinema: Venue, date: Optional[str] = None) -> str:
        current_date = datetime.now().strftime("%Y%m%d") if date is None else date
        venue_name = reSub("[^0-9a-zA-Z ]+", "", cinema.VenueName).lower().replace(" ", "-")
        return (
            f"https://in.bookmyshow.com/buytickets/{venue_name}"
            f"/cinema-{city.RegionCode.lower()}-{cinema.VenueCode}-MT/{current_date}"
        )

    def fetch_cinema_page(self, cinema_url: str) -> BeautifulSoup:
        return BeautifulSoup(self.http.get(cinema_url), "html5lib")
