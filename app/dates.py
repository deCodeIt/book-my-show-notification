from datetime import date, datetime, timedelta
from typing import List, Optional, Tuple
from zoneinfo import ZoneInfo

from .config import MAX_WINDOW_DAYS


def _parse_date_code(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return datetime.strptime(value.strip(), "%Y%m%d").date()
    except ValueError:
        return None


def resolve_dates(
    date_mode: str,
    date_start: Optional[str],
    date_end: Optional[str],
    tz_name: str,
    window_days: int = MAX_WINDOW_DAYS,
) -> Tuple[List[str], Optional[str]]:
    """Turn a watch's date settings into concrete BookMyShow date codes.

    Returns ``(date_codes, error)``. An empty list with an error explains why
    there is nothing to check (e.g. the window is in the past).
    """
    today = datetime.now(ZoneInfo(tz_name)).date()
    mode = (date_mode or "range").lower()

    if mode == "today":
        return [today.strftime("%Y%m%d")], None
    if mode == "tomorrow":
        return [(today + timedelta(days=1)).strftime("%Y%m%d")], None

    start = _parse_date_code(date_start)
    if mode == "exact":
        if start is None:
            return [], "date_start is required for 'exact' mode (YYYYMMDD)"
        return [start.strftime("%Y%m%d")], None

    end = _parse_date_code(date_end)
    start = start or today
    end = end or start + timedelta(days=window_days)

    if end < start:
        return [], "date_end is before date_start"

    if end < today:
        return [], "the date window has already passed"

    if start < today:
        start = today

    span = min((end - start).days, window_days)
    codes = [(start + timedelta(days=offset)).strftime("%Y%m%d") for offset in range(span + 1)]
    return codes, None
