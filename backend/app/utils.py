from __future__ import annotations

from datetime import datetime, time as dtime
import hashlib
from typing import Any, Iterable

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


def is_magdalenka_group(
    group_value: str,
    *,
    exact_groups: Iterable[str] | None = None,
    prefixes: Iterable[str] | None = None,
) -> bool:
    normalized = (group_value or "").strip().lower()

    if not normalized:
        return False

    exact_set = {
        str(item).strip().lower()
        for item in (exact_groups or ("---", "rok", "wszyscy", "all", "year", "cały rok", "caly rok", "d"))
    }
    if normalized in exact_set:
        return True

    prefix_values = tuple(str(item).strip().lower() for item in (prefixes or ("11", "wsz")) if str(item).strip())
    for prefix in prefix_values:
        if normalized.startswith(prefix):
            return True

    return False


def normalize_text(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()
