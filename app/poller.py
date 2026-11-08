import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .dates import resolve_dates
from .matcher import ShowtimeMatch, find_matches

logger = logging.getLogger("bms.poller")

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

MAX_MATCHES_IN_DETAIL = 20


def _date_display(date_code: str) -> str:
    try:
        parsed = datetime.strptime(date_code, "%Y%m%d").date()
    except ValueError:
        return date_code
    return f"{WEEKDAYS[parsed.weekday()]}, {parsed.day} {MONTHS[parsed.month - 1]}"


def _showtime_sort_key(showtime: str):
    for fmt in ("%I:%M %p", "%I:%M%p", "%H:%M"):
        try:
            return (0, datetime.strptime(showtime.strip(), fmt).time())
        except ValueError:
            continue
    return (1, showtime)


def cinema_url(region_code: str, venue_name: str, venue_code: str, date_code: str) -> str:
    import re

    slug = re.sub("[^0-9a-zA-Z ]+", "", venue_name or "").lower().replace(" ", "-")
    return (
        f"https://in.bookmyshow.com/buytickets/{slug}"
        f"/cinema-{region_code.lower()}-{venue_code}-MT/{date_code}"
    )


def _build_message(watch: Dict[str, Any], match: ShowtimeMatch) -> str:
    lines = [f"{match.movie} at {watch['venue_name'] or watch['venue_code']}"]
    detail = f"{_date_display(match.date)} · {match.showtime}"
    if match.format:
        detail += f" · {match.format}"
    lines.append(detail)
    if match.price:
        lines.append(match.price)
    lines.append(cinema_url(watch["region_code"], watch["venue_name"], watch["venue_code"], match.date))
    return "\n".join(line for line in lines if line)


class Poller:
    def __init__(self, db, api, settings, notifier, tick_seconds: Optional[float] = None):
        self.db = db
        self.api = api
        self.settings = settings
        self.notifier = notifier
        self.tick_seconds = tick_seconds or settings.poll_tick_seconds
        self._lock: Optional[asyncio.Lock] = None
        self._task: Optional[asyncio.Task] = None

    @property
    def lock(self) -> asyncio.Lock:
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run(), name="bms-poller")

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _run(self) -> None:
        while True:
            try:
                await self.tick()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("poll tick failed")
            await asyncio.sleep(self.tick_seconds)

    async def tick(self) -> None:
        now = datetime.now(timezone.utc)
        for watch in self.db.watching_watches():
            if self._is_due(watch, now):
                await self.check_watch(watch["id"], notify=True)

    @staticmethod
    def _is_due(watch: Dict[str, Any], now: datetime) -> bool:
        last_raw = watch.get("last_checked_at")
        if not last_raw:
            return True
        try:
            last = datetime.fromisoformat(last_raw)
        except ValueError:
            return True
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        return (now - last).total_seconds() >= int(watch.get("interval_seconds") or 60)

    async def check_watch(self, watch_id: int, notify: bool = True) -> Optional[Dict[str, Any]]:
        async with self.lock:
            watch = self.db.get_watch(watch_id)
            if watch is None:
                return None
            return await asyncio.to_thread(self._run_check, watch, notify)

    def _run_check(self, watch: Dict[str, Any], notify: bool) -> Dict[str, Any]:
        date_codes, date_error = resolve_dates(
            watch["date_mode"], watch["date_start"], watch["date_end"], self.settings.timezone
        )

        matches: List[ShowtimeMatch] = []
        errors: List[str] = []

        if date_error:
            errors.append(date_error)

        for date_code in date_codes:
            try:
                response = self.api.fetch_cinema_showtimes(
                    watch["venue_code"], watch["region_code"], date_code
                )
            except Exception as exc:  # network / BMS rejection
                errors.append(f"{date_code}: {type(exc).__name__}: {exc}")
                continue
            matches.extend(
                find_matches(response, watch["movie_title"], watch["formats"], date_code)
            )

        matches.sort(key=lambda m: (m.date, _showtime_sort_key(m.showtime)))
        error_text = "; ".join(errors) if errors else None
        now = datetime.now(timezone.utc).isoformat()

        self.db.add_check(
            watch["id"],
            found=bool(matches),
            detail={
                "matches": [m.to_dict() for m in matches[:MAX_MATCHES_IN_DETAIL]],
                "dates_checked": date_codes,
                "errors": errors,
            },
        )

        if not matches:
            self.db.update_watch(
                watch["id"], {"last_checked_at": now, "last_error": error_text}
            )
            return {
                "watch": self.db.get_watch(watch["id"]),
                "matches": [],
                "notified": False,
                "error": error_text,
            }

        best = matches[0]
        matched_detail = {
            "date": best.date,
            "date_display": _date_display(best.date),
            "venue": watch["venue_name"] or watch["venue_code"],
            "movie": best.movie,
            "format": best.format,
            "showtime": best.showtime,
            "price": best.price,
            "url": cinema_url(
                watch["region_code"], watch["venue_name"], watch["venue_code"], best.date
            ),
            "matches": [m.to_dict() for m in matches[:MAX_MATCHES_IN_DETAIL]],
        }

        notified = False
        notify_error = None
        if notify:
            try:
                self.notifier.send(
                    f"🎬 {best.movie} tickets are live!",
                    _build_message(watch, best),
                    recipient_ids=watch.get("recipient_ids") or [],
                )
                notified = True
            except Exception as exc:
                notify_error = f"notification failed: {type(exc).__name__}: {exc}"
                logger.warning("notification failed for watch %s: %s", watch["id"], exc)

        # Only mark the watch as found once the alert actually went out, so a
        # delivery failure is retried on the next tick instead of being lost.
        reached_found = notify_error is None
        self.db.update_watch(
            watch["id"],
            {
                "state": "found" if reached_found else watch["state"],
                "last_checked_at": now,
                "last_error": notify_error or error_text,
                "matched_at": now,
                "matched_detail": matched_detail,
            },
        )

        return {
            "watch": self.db.get_watch(watch["id"]),
            "matches": [m.to_dict() for m in matches[:MAX_MATCHES_IN_DETAIL]],
            "notified": notified,
            "error": notify_error or error_text,
        }
