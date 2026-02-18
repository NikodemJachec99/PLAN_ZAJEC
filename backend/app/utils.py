from __future__ import annotations

from datetime import datetime, time as dtime
import hashlib
from typing import Any

import pandas as pd


def parse_time_value(value: Any) -> dtime | None:
    if value is None:
        return None

    if isinstance(value, dtime):
        return value.replace(microsecond=0)

    if isinstance(value, datetime):
        return value.time().replace(microsecond=0)

    if pd.isna(value):
        return None

    raw = str(value).strip()
    if not raw:
        return None

    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(raw, fmt).time()
        except ValueError:
            continue

    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return None

    parsed_dt = parsed.to_pydatetime() if hasattr(parsed, "to_pydatetime") else None
    return parsed_dt.time().replace(microsecond=0) if parsed_dt else None


def normalize_time_series(series: pd.Series) -> pd.Series:
    return series.apply(parse_time_value)


def to_minutes(value: dtime) -> int:
    return value.hour * 60 + value.minute


def hue_for_subject(subject: str) -> int:
    normalized = (subject or "").strip()
    if not normalized:
        return 210
    return int(hashlib.md5(normalized.encode("utf-8")).hexdigest(), 16) % 360


def subject_color_hsl(subject: str) -> str:
    hue = hue_for_subject(subject)
    return f"hsl({hue} 74% 44%)"


def is_magdalenka_group(group_value: str) -> bool:
    normalized = (group_value or "").strip().lower()

    if normalized in {"---", "rok", "wszyscy", "all", "year"}:
        return True
    if "rok" in normalized or "wsz" in normalized:
        return True

    if any(char.isdigit() for char in normalized):
        return normalized == "11" or normalized.startswith("11")

    return normalized == "d" or normalized.startswith("d")


def normalize_text(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()
