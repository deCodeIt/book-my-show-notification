import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS watches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    enabled INTEGER NOT NULL DEFAULT 1,
    region_code TEXT NOT NULL,
    region_slug TEXT NOT NULL DEFAULT '',
    lat TEXT,
    lon TEXT,
    venue_code TEXT NOT NULL,
    venue_name TEXT NOT NULL DEFAULT '',
    movie_title TEXT NOT NULL,
    movie_event_code TEXT,
    formats TEXT NOT NULL DEFAULT '[]',
    date_mode TEXT NOT NULL DEFAULT 'range',
    date_start TEXT,
    date_end TEXT,
    interval_seconds INTEGER NOT NULL DEFAULT 60,
    recipient_ids TEXT NOT NULL DEFAULT '[]',
    state TEXT NOT NULL DEFAULT 'watching',
    last_checked_at TEXT,
    last_error TEXT,
    matched_at TEXT,
    matched_detail TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    watch_id INTEGER NOT NULL REFERENCES watches(id) ON DELETE CASCADE,
    checked_at TEXT NOT NULL,
    found INTEGER NOT NULL,
    detail TEXT
);
CREATE INDEX IF NOT EXISTS idx_checks_watch ON checks(watch_id, id DESC);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""

CHECK_HISTORY_LIMIT = 200

WATCH_COLUMNS = [
    "enabled",
    "region_code",
    "region_slug",
    "lat",
    "lon",
    "venue_code",
    "venue_name",
    "movie_title",
    "movie_event_code",
    "formats",
    "date_mode",
    "date_start",
    "date_end",
    "interval_seconds",
    "recipient_ids",
    "state",
    "last_checked_at",
    "last_error",
    "matched_at",
    "matched_detail",
]


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_list(raw: Any) -> List[Any]:
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except ValueError:
        return []
    return value if isinstance(value, list) else []


def _watch_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    watch = dict(row)
    watch["enabled"] = bool(watch["enabled"])
    watch["formats"] = _load_list(watch.get("formats"))
    watch["recipient_ids"] = _load_list(watch.get("recipient_ids"))
    watch["matched_detail"] = (
        json.loads(watch["matched_detail"]) if watch["matched_detail"] else None
    )
    return watch


class Database:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    @contextmanager
    def session(self):
        conn = self._connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init(self) -> None:
        with self.session() as conn:
            conn.executescript(SCHEMA)

    def migrate(self) -> None:
        """Bring older databases up to the current schema."""
        self.migrate_legacy_pushbullet()
        recipients = self.get_json_setting("pushbullet_recipients", []) or []
        former_ids = [item.get("id") for item in recipients if item.get("id")]
        with self.session() as conn:
            columns = {row["name"] for row in conn.execute("PRAGMA table_info(watches)")}
            if "recipient_ids" not in columns:
                conn.execute(
                    "ALTER TABLE watches ADD COLUMN recipient_ids TEXT NOT NULL DEFAULT '[]'"
                )
            # Watches created before per-watch routing keep notifying everyone
            # who is configured at migration time.
            if former_ids:
                conn.execute(
                    "UPDATE watches SET recipient_ids = ? WHERE recipient_ids = '[]'",
                    (json.dumps(former_ids),),
                )

    def remove_recipient_from_watches(self, receiver_id: str) -> None:
        """Drop a recipient from every watch that referenced it."""
        with self.session() as conn:
            rows = conn.execute("SELECT id, recipient_ids FROM watches").fetchall()
            for row in rows:
                current = _load_list(row["recipient_ids"])
                if receiver_id not in current:
                    continue
                remaining = [item for item in current if item != receiver_id]
                conn.execute(
                    "UPDATE watches SET recipient_ids = ?, updated_at = ? WHERE id = ?",
                    (json.dumps(remaining), utcnow_iso(), row["id"]),
                )

    # -- watches ----------------------------------------------------------
    def create_watch(self, data: Dict[str, Any]) -> Dict[str, Any]:
        now = utcnow_iso()
        values = {
            "enabled": 1 if data.get("enabled", True) else 0,
            "region_code": data["region_code"],
            "region_slug": data.get("region_slug") or "",
            "lat": data.get("lat"),
            "lon": data.get("lon"),
            "venue_code": data["venue_code"],
            "venue_name": data.get("venue_name") or "",
            "movie_title": data["movie_title"],
            "movie_event_code": data.get("movie_event_code"),
            "formats": json.dumps(data.get("formats") or []),
            "date_mode": data.get("date_mode") or "range",
            "date_start": data.get("date_start"),
            "date_end": data.get("date_end"),
            "interval_seconds": int(data.get("interval_seconds") or 60),
            "recipient_ids": json.dumps(data.get("recipient_ids") or []),
            "state": "watching",
            "last_checked_at": None,
            "last_error": None,
            "matched_at": None,
            "matched_detail": None,
        }
        columns = ", ".join(values)
        placeholders = ", ".join("?" for _ in values)
        with self.session() as conn:
            cursor = conn.execute(
                f"INSERT INTO watches ({columns}, created_at, updated_at) "
                f"VALUES ({placeholders}, ?, ?)",
                (*values.values(), now, now),
            )
            watch_id = cursor.lastrowid
        return self.get_watch(watch_id)

    def get_watch(self, watch_id: int) -> Optional[Dict[str, Any]]:
        with self.session() as conn:
            row = conn.execute("SELECT * FROM watches WHERE id = ?", (watch_id,)).fetchone()
        return _watch_to_dict(row) if row else None

    def list_watches(self) -> List[Dict[str, Any]]:
        with self.session() as conn:
            rows = conn.execute("SELECT * FROM watches ORDER BY id DESC").fetchall()
        return [_watch_to_dict(row) for row in rows]

    def watching_watches(self) -> List[Dict[str, Any]]:
        with self.session() as conn:
            rows = conn.execute(
                "SELECT * FROM watches WHERE enabled = 1 AND state = 'watching' ORDER BY id"
            ).fetchall()
        return [_watch_to_dict(row) for row in rows]

    def update_watch(self, watch_id: int, fields: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        clean = {k: v for k, v in fields.items() if k in WATCH_COLUMNS}
        if not clean:
            return self.get_watch(watch_id)
        if "formats" in clean and not isinstance(clean["formats"], str):
            clean["formats"] = json.dumps(clean["formats"] or [])
        if "recipient_ids" in clean and not isinstance(clean["recipient_ids"], str):
            clean["recipient_ids"] = json.dumps(list(clean["recipient_ids"] or []))
        if "matched_detail" in clean and not isinstance(clean["matched_detail"], (str, type(None))):
            clean["matched_detail"] = json.dumps(clean["matched_detail"])
        if "enabled" in clean:
            clean["enabled"] = 1 if clean["enabled"] else 0
        assignments = ", ".join(f"{column} = ?" for column in clean)
        with self.session() as conn:
            conn.execute(
                f"UPDATE watches SET {assignments}, updated_at = ? WHERE id = ?",
                (*clean.values(), utcnow_iso(), watch_id),
            )
        return self.get_watch(watch_id)

    def delete_watch(self, watch_id: int) -> bool:
        with self.session() as conn:
            conn.execute("DELETE FROM checks WHERE watch_id = ?", (watch_id,))
            cursor = conn.execute("DELETE FROM watches WHERE id = ?", (watch_id,))
        return cursor.rowcount > 0

    # -- check history ----------------------------------------------------
    def add_check(self, watch_id: int, found: bool, detail: Any) -> None:
        with self.session() as conn:
            conn.execute(
                "INSERT INTO checks (watch_id, checked_at, found, detail) VALUES (?, ?, ?, ?)",
                (watch_id, utcnow_iso(), 1 if found else 0, json.dumps(detail)),
            )
            conn.execute(
                "DELETE FROM checks WHERE watch_id = ? AND id NOT IN "
                "(SELECT id FROM checks WHERE watch_id = ? ORDER BY id DESC LIMIT ?)",
                (watch_id, watch_id, CHECK_HISTORY_LIMIT),
            )

    def check_history(self, watch_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        with self.session() as conn:
            rows = conn.execute(
                "SELECT * FROM checks WHERE watch_id = ? ORDER BY id DESC LIMIT ?",
                (watch_id, limit),
            ).fetchall()
        history = []
        for row in rows:
            item = dict(row)
            item["found"] = bool(item["found"])
            item["detail"] = json.loads(item["detail"]) if item["detail"] else None
            history.append(item)
        return history

    # -- settings ---------------------------------------------------------
    def get_setting(self, key: str) -> Optional[str]:
        with self.session() as conn:
            row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None

    def set_setting(self, key: str, value: Optional[str]) -> None:
        with self.session() as conn:
            if value is None:
                conn.execute("DELETE FROM settings WHERE key = ?", (key,))
            else:
                conn.execute(
                    "INSERT INTO settings (key, value) VALUES (?, ?) "
                    "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                    (key, value),
                )

    def get_json_setting(self, key: str, default: Any = None) -> Any:
        raw = self.get_setting(key)
        if not raw:
            return default
        try:
            return json.loads(raw)
        except ValueError:
            return default

    def set_json_setting(self, key: str, value: Any) -> None:
        self.set_setting(key, json.dumps(value) if value is not None else None)

    def migrate_legacy_pushbullet(self) -> None:
        """Fold the old single-token settings into the recipients list."""
        if self.get_setting("pushbullet_recipients") is not None:
            return
        legacy_token = (self.get_setting("pushbullet_token") or "").strip()
        if not legacy_token:
            return
        recipient = {
            "id": "legacy",
            "label": "Migrated token",
            "token": legacy_token,
            "device": self.get_setting("pushbullet_device") or "",
        }
        self.set_json_setting("pushbullet_recipients", [recipient])
        self.set_setting("pushbullet_token", None)
        self.set_setting("pushbullet_device", None)
