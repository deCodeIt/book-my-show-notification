from dataclasses import dataclass
from typing import List, Optional, Sequence

from bmsTypes import CinemaPageApiResponse


@dataclass
class ShowtimeMatch:
    date: str
    movie: str
    format: str
    showtime: str
    price: str
    avail_status: str

    def to_dict(self) -> dict:
        return {
            "date": self.date,
            "movie": self.movie,
            "format": self.format,
            "showtime": self.showtime,
            "price": self.price,
            "avail_status": self.avail_status,
        }


def _price_range(show) -> str:
    low = (show.MinPrice or "").strip()
    high = (show.MaxPrice or "").strip()
    if not low and not high:
        return ""
    if not high or low == high:
        return f"₹{low}"
    return f"₹{low}–₹{high}"


def find_matches(
    response: Optional[CinemaPageApiResponse],
    movie_title: str,
    formats: Optional[Sequence[str]],
    date_code: str,
) -> List[ShowtimeMatch]:
    """Return every showtime whose movie title contains ``movie_title``.

    ``formats`` empty/None means "any format". A match requires at least one
    listed showtime, which is what "tickets are available" actually means.
    """
    if response is None or not response.ShowDetails:
        return []

    needle = (movie_title or "").strip().lower()
    if not needle:
        return []

    wanted = {f.strip().upper() for f in (formats or []) if f and f.strip()}

    matches: List[ShowtimeMatch] = []
    for detail in response.ShowDetails:
        for event in detail.Event or []:
            if needle not in (event.EventTitle or "").lower():
                continue
            for child in event.ChildEvents or []:
                dimension = (child.EventDimension or "").strip()
                if wanted and dimension.upper() not in wanted:
                    continue
                for show in child.ShowTimes or []:
                    matches.append(
                        ShowtimeMatch(
                            date=date_code,
                            movie=event.EventTitle,
                            format=dimension,
                            showtime=(show.ShowTime or "").strip(),
                            price=_price_range(show),
                            avail_status=(show.AvailStatus or "").strip(),
                        )
                    )
    return matches
