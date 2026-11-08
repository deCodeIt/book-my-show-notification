import threading
import time
from typing import Any, Dict, List, Optional

from bms_api import BookMyShowApi
from bmsTypes import City, Movie, Venue


def city_summary(city: City) -> Dict[str, Any]:
    return {
        "code": city.RegionCode,
        "name": city.RegionName,
        "slug": city.RegionSlug,
        "lat": city.Lat,
        "lon": city.Long,
        "aliases": city.Alias or [],
    }


def venue_summary(venue: Venue) -> Dict[str, Any]:
    return {
        "code": venue.VenueCode,
        "name": venue.VenueName,
        "address": venue.VenueAddress,
        "region_code": venue.RegionCode,
    }


def movie_summary(movie: Movie) -> Dict[str, Any]:
    return {
        "title": movie.name,
        "event_code": movie.event_code,
        "event_group": movie.event_group,
        "language": movie.language,
        "genre": movie.genre,
        "poster": movie.poster_url,
        "url": movie.url,
    }


class BmsService:
    """Cached, thread-safe facade over ``BookMyShowApi``.

    BookMyShow responses change slowly relative to UI typing, so a short TTL
    keeps the search boxes instant without hammering upstream.
    """

    def __init__(
        self,
        api: BookMyShowApi,
        regions_ttl: float = 3600,
        venues_ttl: float = 600,
        movies_ttl: float = 300,
    ):
        self.api = api
        self.regions_ttl = regions_ttl
        self.venues_ttl = venues_ttl
        self.movies_ttl = movies_ttl
        self._lock = threading.Lock()
        self._regions: Optional[List[City]] = None
        self._regions_at = 0.0
        self._venues: Dict[str, tuple] = {}
        self._movies: Dict[str, tuple] = {}

    def _cache_get(self, store: Dict[str, tuple], key: str, ttl: float):
        with self._lock:
            entry = store.get(key)
        if entry and time.monotonic() - entry[0] < ttl:
            return entry[1]
        return None

    def _cache_put(self, store: Dict[str, tuple], key: str, value):
        with self._lock:
            store[key] = (time.monotonic(), value)
        return value

    def clear_cache(self) -> None:
        with self._lock:
            self._regions = None
            self._regions_at = 0.0
            self._venues.clear()
            self._movies.clear()

    def regions(self) -> List[City]:
        with self._lock:
            if self._regions is not None and time.monotonic() - self._regions_at < self.regions_ttl:
                return self._regions
        payload = self.api.fetch_regions()
        cities = list(payload.BookMyShow.TopCities) + list(payload.BookMyShow.OtherCities)
        with self._lock:
            self._regions = cities
            self._regions_at = time.monotonic()
        return cities

    def search_regions(self, query: str = "", limit: int = 25) -> List[City]:
        needle = (query or "").strip().lower()
        results = []
        for city in self.regions():
            if not needle:
                results.append(city)
            elif (
                needle in city.RegionCode.lower()
                or needle in city.RegionName.lower()
                or any(needle in alias.lower() for alias in (city.Alias or []))
            ):
                results.append(city)
            if len(results) >= limit:
                break
        return results

    def get_city(self, region_code: str) -> Optional[City]:
        needle = (region_code or "").strip().upper()
        for city in self.regions():
            if city.RegionCode.upper() == needle:
                return city
        return None

    def venues(self, region_code: str) -> List[Venue]:
        key = (region_code or "").upper()
        cached = self._cache_get(self._venues, key, self.venues_ttl)
        if cached is not None:
            return cached
        return self._cache_put(self._venues, key, self.api.fetch_venues(key))

    def search_venues(self, region_code: str, query: str = "", limit: int = 50) -> List[Venue]:
        needle = (query or "").strip().lower()
        results = []
        for venue in self.venues(region_code):
            if not needle or needle in venue.VenueCode.lower() or needle in venue.VenueName.lower():
                results.append(venue)
            if len(results) >= limit:
                break
        return results

    def get_venue(self, region_code: str, venue_code: str) -> Optional[Venue]:
        needle = (venue_code or "").strip().upper()
        for venue in self.venues(region_code):
            if venue.VenueCode.upper() == needle:
                return venue
        return None

    def movies(self, region_code: str, languages: Optional[str] = None) -> List[Movie]:
        city = self.get_city(region_code)
        if city is None:
            raise LookupError(f"unknown region '{region_code}'")
        key = f"{city.RegionCode}:{languages or ''}"
        cached = self._cache_get(self._movies, key, self.movies_ttl)
        if cached is not None:
            return cached
        movies = self.api.fetch_movies(
            city.RegionCode, city.RegionSlug, languages, city.Lat, city.Long
        )
        return self._cache_put(self._movies, key, movies)

    def search_movies(
        self, region_code: str, query: str = "", languages: Optional[str] = None, limit: int = 40
    ) -> List[Movie]:
        needle = (query or "").strip().lower()
        results = []
        for movie in self.movies(region_code, languages):
            if not needle or needle in movie.name.lower():
                results.append(movie)
            if len(results) >= limit:
                break
        return results
