import os
from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SUPPORTED_FORMATS = [
    "2D",
    "3D",
    "4DX",
    "DOLBY CINEMA 2D",
    "2D SCREEN X",
    "4DX 3D",
    "IMAX 2D",
    "IMAX 3D",
    "ICE",
    "3D SCREEN X",
    "EPIQ 3D",
    "DOLBY CINEMA 3D",
    "MX4D 3D",
    "HDR By Barco",
    "ICE 3D",
]

DATE_MODES = ["today", "tomorrow", "exact", "range"]

MAX_WINDOW_DAYS = 14
MIN_INTERVAL_SECONDS = 30


@dataclass(frozen=True)
class Settings:
    app_token: str = ""
    database_path: Path = BASE_DIR / "data" / "bms.db"
    poll_tick_seconds: float = 5.0
    default_interval_seconds: int = 60
    timezone: str = "Asia/Kolkata"
    host: str = "0.0.0.0"
    port: int = 8080
    env_pushbullet_token: str = ""

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            app_token=os.getenv("APP_TOKEN", "").strip(),
            database_path=Path(os.getenv("BMS_DB_PATH", str(BASE_DIR / "data" / "bms.db"))),
            poll_tick_seconds=float(os.getenv("BMS_POLL_TICK", "5")),
            default_interval_seconds=int(os.getenv("BMS_DEFAULT_INTERVAL", "60")),
            timezone=os.getenv("BMS_TIMEZONE", "Asia/Kolkata"),
            host=os.getenv("HOST", "0.0.0.0"),
            port=int(os.getenv("PORT", "8080")),
            env_pushbullet_token=os.getenv("PUSHBULLET_TOKEN", "").strip(),
        )
