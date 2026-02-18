from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import os


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    cache_ttl_seconds: int
    timezone: str
    allowed_origins: list[str]


def _parse_origins(raw: str) -> list[str]:
    origins = [item.strip() for item in raw.split(",") if item.strip()]
    return origins or ["http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    default_data_dir = Path(__file__).resolve().parents[1] / "data"
    data_dir = Path(os.getenv("DATA_DIR", str(default_data_dir))).resolve()

    try:
        cache_ttl_seconds = int(os.getenv("CACHE_TTL_SECONDS", "60"))
    except ValueError:
        cache_ttl_seconds = 60

    timezone = os.getenv("TZ", "Europe/Warsaw")
    allowed_origins = _parse_origins(os.getenv("ALLOWED_ORIGINS", "http://localhost:5173"))

    return Settings(
        data_dir=data_dir,
        cache_ttl_seconds=max(cache_ttl_seconds, 1),
        timezone=timezone,
        allowed_origins=allowed_origins,
    )
