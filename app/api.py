from datetime import datetime
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field

from .auth import COOKIE_NAME
from .bms_service import city_summary, movie_summary, venue_summary
from .config import DATE_MODES, MIN_INTERVAL_SECONDS, SUPPORTED_FORMATS


class LoginRequest(BaseModel):
    token: str = ""


class WatchCreate(BaseModel):
    region_code: str
    venue_code: str
    movie_title: str
    region_slug: Optional[str] = None
    lat: Optional[str] = None
    lon: Optional[str] = None
    venue_name: Optional[str] = None
    movie_event_code: Optional[str] = None
    formats: List[str] = Field(default_factory=list)
    date_mode: str = "range"
    date_start: Optional[str] = None
    date_end: Optional[str] = None
    interval_seconds: int = 60
    recipient_ids: List[str] = Field(default_factory=list)


class WatchUpdate(BaseModel):
    enabled: Optional[bool] = None
    region_code: Optional[str] = None
    venue_code: Optional[str] = None
    movie_title: Optional[str] = None
    region_slug: Optional[str] = None
    lat: Optional[str] = None
    lon: Optional[str] = None
    venue_name: Optional[str] = None
    movie_event_code: Optional[str] = None
    formats: Optional[List[str]] = None
    date_mode: Optional[str] = None
    date_start: Optional[str] = None
    date_end: Optional[str] = None
    interval_seconds: Optional[int] = None
    recipient_ids: Optional[List[str]] = None


class RecipientCreate(BaseModel):
    token: str
    label: str = ""
    device: str = ""


class RecipientUpdate(BaseModel):
    token: Optional[str] = None
    label: Optional[str] = None
    device: Optional[str] = None


class TestNotification(BaseModel):
    recipient_ids: Optional[List[str]] = None


def _valid_date_code(value: Optional[str]) -> bool:
    if not value:
        return True
    try:
        datetime.strptime(value.strip(), "%Y%m%d")
        return True
    except ValueError:
        return False


def _mask(token: Optional[str]) -> Optional[str]:
    if not token:
        return None
    return "••••" + token[-4:] if len(token) > 4 else "••••"


SEARCH_FIELDS = {
    "region_code",
    "venue_code",
    "movie_title",
    "movie_event_code",
    "formats",
    "date_mode",
    "date_start",
    "date_end",
}


def build_router(db, bms, poller, notifier, settings) -> APIRouter:
    router = APIRouter(prefix="/api")

    def known_recipient_ids() -> set:
        stored = db.get_json_setting("pushbullet_recipients", []) or []
        ids = {item.get("id") for item in stored if item.get("id")}
        if settings.env_pushbullet_token:
            ids.add("env")
        return ids

    def mask_recipient(recipient: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": recipient["id"],
            "label": recipient.get("label") or "",
            "device": recipient.get("device") or "",
            "token_hint": _mask(recipient["token"]),
            "source": recipient.get("source", "database"),
        }

    def enrich(data: Dict[str, Any]) -> Dict[str, Any]:
        region_code = data.get("region_code")
        if not region_code:
            return data

        city = None
        try:
            city = bms.get_city(region_code)
        except Exception:
            city = None
        if city is not None:
            data["region_slug"] = data.get("region_slug") or city.RegionSlug
            data["lat"] = data.get("lat") or city.Lat
            data["lon"] = data.get("lon") or city.Long

        venue_code = data.get("venue_code")
        if venue_code and not data.get("venue_name"):
            venue = None
            try:
                venue = bms.get_venue(region_code, venue_code)
            except Exception:
                venue = None
            if venue is not None:
                data["venue_name"] = venue.VenueName
        return data

    def validate(data: Dict[str, Any]) -> None:
        if not (data.get("movie_title") or "").strip():
            raise HTTPException(400, "movie_title is required")
        if not (data.get("region_code") or "").strip():
            raise HTTPException(400, "region_code is required")
        if not (data.get("venue_code") or "").strip():
            raise HTTPException(400, "venue_code is required")
        mode = (data.get("date_mode") or "range").lower()
        if mode not in DATE_MODES:
            raise HTTPException(400, f"date_mode must be one of {DATE_MODES}")
        for key in ("date_start", "date_end"):
            if not _valid_date_code(data.get(key)):
                raise HTTPException(400, f"{key} must be YYYYMMDD")
        interval = int(data.get("interval_seconds") or 0)
        if interval < MIN_INTERVAL_SECONDS:
            raise HTTPException(400, f"interval_seconds must be >= {MIN_INTERVAL_SECONDS}")

        wanted = list(dict.fromkeys(data.get("recipient_ids") or []))
        if not wanted:
            raise HTTPException(
                400, "recipient_ids must contain at least one Pushbullet recipient"
            )
        known = known_recipient_ids()
        unknown = [item for item in wanted if item not in known]
        if unknown:
            raise HTTPException(400, f"unknown recipient(s): {', '.join(unknown)}")

    def normalise(data: Dict[str, Any]) -> Dict[str, Any]:
        out = dict(data)
        if out.get("region_code"):
            out["region_code"] = out["region_code"].strip().upper()
        if out.get("venue_code"):
            out["venue_code"] = out["venue_code"].strip().upper()
        if out.get("movie_title"):
            out["movie_title"] = out["movie_title"].strip()
        if out.get("formats") is not None:
            out["formats"] = [f.strip() for f in out["formats"] if f and f.strip()]
        if out.get("date_mode"):
            out["date_mode"] = out["date_mode"].strip().lower()
        if out.get("recipient_ids") is not None:
            out["recipient_ids"] = list(
                dict.fromkeys(item.strip() for item in out["recipient_ids"] if item and item.strip())
            )
        return out

    # -- auth -------------------------------------------------------------
    @router.post("/login")
    def login(payload: LoginRequest, response: Response):
        if not settings.app_token:
            return {"ok": True, "auth": "disabled"}
        if not payload.token or payload.token != settings.app_token:
            raise HTTPException(401, "invalid token")
        response.set_cookie(
            COOKIE_NAME,
            settings.app_token,
            httponly=True,
            samesite="lax",
            max_age=60 * 60 * 24 * 365,
            path="/",
        )
        return {"ok": True}

    @router.post("/logout")
    def logout(response: Response):
        response.delete_cookie(COOKIE_NAME, path="/")
        return {"ok": True}

    # -- catalogue --------------------------------------------------------
    @router.get("/meta")
    def meta():
        return {
            "formats": SUPPORTED_FORMATS,
            "date_modes": DATE_MODES,
            "min_interval_seconds": MIN_INTERVAL_SECONDS,
            "auth_enabled": bool(settings.app_token),
        }

    @router.get("/regions")
    def regions(q: str = ""):
        try:
            return [city_summary(city) for city in bms.search_regions(q)]
        except Exception as exc:
            raise HTTPException(502, f"BookMyShow request failed: {exc}")

    @router.get("/venues")
    def venues(region: str, q: str = ""):
        try:
            return [venue_summary(v) for v in bms.search_venues(region, q)]
        except Exception as exc:
            raise HTTPException(502, f"BookMyShow request failed: {exc}")

    @router.get("/movies")
    def movies(region: str, q: str = "", languages: Optional[str] = None):
        try:
            found = bms.search_movies(region, q, languages)
        except LookupError as exc:
            raise HTTPException(404, str(exc))
        except Exception as exc:
            raise HTTPException(502, f"BookMyShow request failed: {exc}")
        return [movie_summary(movie) for movie in found]

    # -- watches ----------------------------------------------------------
    @router.get("/watches")
    def list_watches():
        return db.list_watches()

    @router.get("/watches/{watch_id}")
    def get_watch(watch_id: int):
        watch = db.get_watch(watch_id)
        if watch is None:
            raise HTTPException(404, "watch not found")
        return watch

    @router.post("/watches", status_code=201)
    def create_watch(payload: WatchCreate):
        data = normalise(payload.dict())
        validate(data)
        data = enrich(data)
        return db.create_watch(data)

    @router.patch("/watches/{watch_id}")
    def update_watch(watch_id: int, payload: WatchUpdate):
        current = db.get_watch(watch_id)
        if current is None:
            raise HTTPException(404, "watch not found")

        changes = payload.dict(exclude_unset=True)
        if not changes:
            return current

        enabled = changes.pop("enabled", None)
        normalised = normalise(changes)

        if normalised:
            merged = {**current, **normalised}
            validate(merged)

            if any(key in normalised for key in ("region_code", "venue_code")):
                probe = enrich(
                    {
                        "region_code": merged["region_code"],
                        "venue_code": merged["venue_code"],
                        "venue_name": normalised.get("venue_name"),
                    }
                )
                for key in ("region_slug", "lat", "lon", "venue_name"):
                    if key not in normalised and probe.get(key):
                        normalised[key] = probe[key]

            # Only a change to what we search for starts a fresh search.
            if SEARCH_FIELDS & set(normalised):
                normalised.update(
                    {"state": "watching", "matched_at": None, "matched_detail": None,
                     "last_checked_at": None, "last_error": None}
                )

        if enabled is not None:
            normalised["enabled"] = enabled
            normalised["state"] = "watching" if enabled else "paused"
            if enabled:
                normalised.update({"last_checked_at": None, "last_error": None})

        return db.update_watch(watch_id, normalised)

    @router.delete("/watches/{watch_id}")
    def delete_watch(watch_id: int):
        if not db.delete_watch(watch_id):
            raise HTTPException(404, "watch not found")
        return {"ok": True}

    @router.post("/watches/{watch_id}/check")
    async def check_watch(watch_id: int):
        result = await poller.check_watch(watch_id, notify=False)
        if result is None:
            raise HTTPException(404, "watch not found")
        return result

    @router.get("/watches/{watch_id}/history")
    def watch_history(watch_id: int, limit: int = 50):
        if db.get_watch(watch_id) is None:
            raise HTTPException(404, "watch not found")
        return db.check_history(watch_id, limit=min(max(limit, 1), 200))

    # -- settings ---------------------------------------------------------
    @router.get("/settings")
    def get_settings():
        recipients = notifier.recipients()
        return {
            "pushbullet_recipients": [mask_recipient(item) for item in recipients],
            "token_configured": bool(recipients),
            "auth_enabled": bool(settings.app_token),
        }

    @router.post("/settings/pushbullet", status_code=201)
    def add_recipient(payload: RecipientCreate):
        token = payload.token.strip()
        if not token:
            raise HTTPException(400, "token is required")

        stored = db.get_json_setting("pushbullet_recipients", []) or []
        if token == settings.env_pushbullet_token or any(
            (item.get("token") or "").strip() == token for item in stored
        ):
            raise HTTPException(409, "this token is already configured")

        recipient = {
            "id": uuid.uuid4().hex[:8],
            "label": payload.label.strip(),
            "token": token,
            "device": payload.device.strip(),
        }
        stored.append(recipient)
        db.set_json_setting("pushbullet_recipients", stored)
        return mask_recipient({**recipient, "source": "database"})

    @router.patch("/settings/pushbullet/{recipient_id}")
    def update_recipient(recipient_id: str, payload: RecipientUpdate):
        if recipient_id == "env":
            raise HTTPException(400, "this recipient comes from PUSHBULLET_TOKEN")

        stored = db.get_json_setting("pushbullet_recipients", []) or []
        for item in stored:
            if item.get("id") != recipient_id:
                continue
            if payload.label is not None:
                item["label"] = payload.label.strip()
            if payload.device is not None:
                item["device"] = payload.device.strip()
            if payload.token is not None and payload.token.strip():
                item["token"] = payload.token.strip()
            db.set_json_setting("pushbullet_recipients", stored)
            return mask_recipient({**item, "source": "database"})
        raise HTTPException(404, "recipient not found")

    @router.delete("/settings/pushbullet/{recipient_id}")
    def remove_recipient(recipient_id: str):
        if recipient_id == "env":
            raise HTTPException(400, "this recipient comes from PUSHBULLET_TOKEN")

        stored = db.get_json_setting("pushbullet_recipients", []) or []
        remaining = [item for item in stored if item.get("id") != recipient_id]
        if len(remaining) == len(stored):
            raise HTTPException(404, "recipient not found")
        db.set_json_setting("pushbullet_recipients", remaining)
        db.remove_recipient_from_watches(recipient_id)
        return {"ok": True}

    @router.post("/notifications/test")
    def test_notification(payload: TestNotification = None):
        target = payload.recipient_ids if payload else None
        try:
            result = notifier.send(
                "BMS watcher test",
                "If you can read this, Pushbullet notifications are wired up.",
                recipient_ids=target,
            )
        except Exception as exc:
            raise HTTPException(400, str(exc))
        return {"ok": True, "result": result}

    return router
