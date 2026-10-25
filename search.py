from typing import List

from bmsTypes import City, Venue


class RegionFinder:
    """Finds regions/cities matching a query."""

    def search(self, api, query: str) -> List[City]:
        regions = api.fetch_regions()
        results = []
        for item in regions.BookMyShow.TopCities + regions.BookMyShow.OtherCities:
            if (
                query.lower() in item.RegionCode.lower()
                or query.lower() in item.RegionName.lower()
                or any(query.lower() in alias.lower() for alias in item.Alias)
            ):
                results.append(item)
        return results


class VenueFinder:
    """Finds venues/cinemas matching a query within a region."""

    def search(self, api, region_code: str, query: str) -> List[Venue]:
        venues = api.fetch_venues(region_code)
        results = []
        for item in venues.BookMyShow.arrVenue:
            if query.lower() in item.VenueCode.lower() or query.lower() in item.VenueName.lower():
                results.append(item)
        return results
