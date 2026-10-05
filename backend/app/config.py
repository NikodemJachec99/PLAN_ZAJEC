from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import os

DEFAULT_SOURCE_PAGE_URL = "https://wnoz.uni.opole.pl/plan-pielegniarstwo-i-stopnia-iii-rok-stacjonarne-1/"


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    seed_dir: Path
    timezone: str
    allowed_origins: list[str]
    settings_password: str
    source_page_url: str
    sync_enabled: bool
    sync_interval_seconds: int
    min_forced_check_seconds: int
    missing_grace_hours: float
    http_timeout_seconds: float
    max_file_bytes: int
    cache_bust: bool


def _parse_origins(raw: str) -> list[str]:
    origins = [item.strip() for item in raw.split(",") if item.strip()]
    return origins or ["http://localhost:5173"]


def _int(name: str, default: int, minimum: int) -> int:
    try:
        return max(int(os.getenv(name, str(default))), minimum)
    except ValueError:
        return default


def _float(name: str, default: float, minimum: float) -> float:
    try:
        return max(float(os.getenv(name, str(default))), minimum)
    except ValueError:
        return default


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on", "tak"}


@lru_cache
def get_settings() -> Settings:
    default_data_dir = Path(__file__).resolve().parents[1] / "data"
    data_dir = Path(os.getenv("DATA_DIR", str(default_data_dir))).resolve()
    seed_dir = Path(os.getenv("SEED_DIR", str(data_dir / "seed"))).resolve()

    # Strip tracking parameters people tend to paste along with the link (?fbclid=...).
    page_url = (os.getenv("SOURCE_PAGE_URL") or DEFAULT_SOURCE_PAGE_URL).strip()
    page_url = page_url.split("?fbclid=")[0].split("&fbclid=")[0]

    return Settings(
        data_dir=data_dir,
        seed_dir=seed_dir,
        timezone=os.getenv("TZ", "Europe/Warsaw"),
        allowed_origins=_parse_origins(os.getenv("ALLOWED_ORIGINS", "http://localhost:5173")),
        settings_password=os.getenv("SETTINGS_PASSWORD", "").strip(),
        source_page_url=page_url,
        sync_enabled=_bool("SYNC_ENABLED", True),
        sync_interval_seconds=_int("SYNC_INTERVAL_SECONDS", 300, 30),
        min_forced_check_seconds=_int("SYNC_MIN_FORCED_SECONDS", 30, 5),
        missing_grace_hours=_float("SYNC_MISSING_GRACE_HOURS", 12.0, 0.0),
        http_timeout_seconds=_float("SYNC_HTTP_TIMEOUT_SECONDS", 30.0, 5.0),
        max_file_bytes=_int("SYNC_MAX_FILE_BYTES", 20 * 1024 * 1024, 1024),
        cache_bust=_bool("SYNC_CACHE_BUST", True),
    )
