"""Small, dependency-free helpers for normalising text, dates and times found in the Excel plans."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
import math
import re
from typing import Any

_POLISH_FOLD = str.maketrans(
    {
        "ą": "a",
        "ć": "c",
        "ę": "e",
        "ł": "l",
        "ń": "n",
        "ó": "o",
        "ś": "s",
        "ź": "z",
        "ż": "z",
        "Ą": "a",
        "Ć": "c",
        "Ę": "e",
        "Ł": "l",
        "Ń": "n",
        "Ó": "o",
        "Ś": "s",
        "Ź": "z",
        "Ż": "z",
    }
)

MONTHS = {
    "styczen": 1,
    "stycznia": 1,
    "luty": 2,
    "lutego": 2,
    "marzec": 3,
    "marca": 3,
    "kwiecien": 4,
    "kwietnia": 4,
    "maj": 5,
    "maja": 5,
    "czerwiec": 6,
    "czerwca": 6,
    "lipiec": 7,
    "lipca": 7,
    "sierpien": 8,
    "sierpnia": 8,
    "wrzesien": 9,
    "wrzesnia": 9,
    "pazdziernik": 10,
    "pazdziernika": 10,
    "listopad": 11,
    "listopada": 11,
    "grudzien": 12,
    "grudnia": 12,
}

# Monday == 0, matching date.weekday().
WEEKDAYS = {
    "pn": 0,
    "pon": 0,
    "poniedzialek": 0,
    "wt": 1,
    "wto": 1,
    "wtorek": 1,
    "sr": 2,
    "sro": 2,
    "sroda": 2,
    "cz": 3,
    "czw": 3,
    "czwartek": 3,
    "pt": 4,
    "pia": 4,
    "piatek": 4,
    "sb": 5,
    "so": 5,
    "sob": 5,
    "sobota": 5,
    "nd": 6,
    "ndz": 6,
    "niedz": 6,
    "niedziela": 6,
}

TIME_RANGE_RE = re.compile(r"(\d{1,2})\s*[:.]\s*(\d{2})\s*[-–—]\s*(\d{1,2})\s*[:.]\s*(\d{2})")


def fold(value: Any) -> str:
    """Lower-case, strip Polish diacritics and collapse whitespace (for comparisons only)."""
    return re.sub(r"\s+", " ", clean(value).translate(_POLISH_FOLD).lower()).strip()


def clean(value: Any) -> str:
    """Convert a cell value to a trimmed single-spaced string ("" for empty cells)."""
    if value is None:
        return ""
    if isinstance(value, float):
        if math.isnan(value):
            return ""
        if value.is_integer():
            return str(int(value))
    if isinstance(value, datetime):
        return value.isoformat(sep=" ")
    text = str(value).replace("\xa0", " ")
    return re.sub(r"[ \t\r\f\v]+", " ", text).strip()


def clean_multiline(value: Any) -> str:
    return re.sub(r"\s*\n\s*", " ", clean(value)).strip()


def as_code(value: Any) -> str:
    """Normalise legend codes: 116.0 -> "116", " Oz " -> "Oz"."""
    return clean_multiline(value)


def parse_time(value: Any) -> time | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.time().replace(second=0, microsecond=0)
    if isinstance(value, time):
        return value.replace(second=0, microsecond=0)
    if isinstance(value, timedelta):
        minutes = int(round(value.total_seconds() / 60))
        return _minutes_to_time(minutes)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        number = float(value)
        if math.isnan(number) or number < 0:
            return None
        if number.is_integer():
            # A bare hour such as 8 -> 08:00.
            return _minutes_to_time(int(number) * 60) if number <= 24 else None
        # Excel stores times as a fraction of a day (optionally on top of a serial date).
        return _minutes_to_time(int(round((number % 1) * 24 * 60)))
    text = clean(value)
    match = re.fullmatch(r"(\d{1,2})\s*[:.]\s*(\d{2})(?:\s*[:.]\s*\d{2})?", text)
    if not match:
        match = re.fullmatch(r"(\d{1,2})", text)
        if not match:
            return None
        hours, minutes = int(match.group(1)), 0
    else:
        hours, minutes = int(match.group(1)), int(match.group(2))
    if hours > 24 or minutes > 59:
        return None
    return _minutes_to_time(hours * 60 + minutes)


def _minutes_to_time(minutes: int) -> time | None:
    if minutes < 0:
        return None
    minutes = min(minutes, 24 * 60 - 1)
    return time(minutes // 60, minutes % 60)


def find_time_range(text: str) -> tuple[time, time, tuple[int, int]] | None:
    """Return (start, end, span) for the first "8:00-15:30" style range in text."""
    match = TIME_RANGE_RE.search(text or "")
    if not match:
        return None
    h1, m1, h2, m2 = (int(group) for group in match.groups())
    if h1 > 24 or h2 > 24 or m1 > 59 or m2 > 59:
        return None
    start = _minutes_to_time(h1 * 60 + m1)
    end = _minutes_to_time(h2 * 60 + m2)
    if start is None or end is None:
        return None
    return start, end, match.span()


def parse_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        number = float(value)
        if math.isnan(number) or not (20000 < number < 80000):
            return None
        # Excel serial date (1900 system).
        return (datetime(1899, 12, 30) + timedelta(days=int(number))).date()
    text = clean(value)
    for pattern, order in (
        (r"(\d{4})[-./](\d{1,2})[-./](\d{1,2})", "ymd"),
        (r"(\d{1,2})[-./](\d{1,2})[-./](\d{4})", "dmy"),
    ):
        match = re.search(pattern, text)
        if match:
            parts = [int(part) for part in match.groups()]
            year, month, day = parts if order == "ymd" else (parts[2], parts[1], parts[0])
            try:
                return date(year, month, day)
            except ValueError:
                return None
    return None


def date_from_filename(name: str) -> date | None:
    """Pick the planner's "stan na" date out of names like PI_s_III_sem.zimowy_05.10.2026-1.xlsx."""
    for pattern, order in (
        (r"(?<!\d)(\d{4})[-_.](\d{1,2})[-_.](\d{1,2})(?!\d)", "ymd"),
        (r"(?<!\d)(\d{1,2})[-_.](\d{1,2})[-_.](\d{4})(?!\d)", "dmy"),
    ):
        for match in re.finditer(pattern, name or ""):
            parts = [int(part) for part in match.groups()]
            year, month, day = parts if order == "ymd" else (parts[2], parts[1], parts[0])
            try:
                return date(year, month, day)
            except ValueError:
                continue
    return None


MONTH_ABBREVIATIONS = {"sty": 1, "lut": 2, "mar": 3, "kwi": 4, "cze": 6, "lip": 7, "sie": 8, "wrz": 9, "paz": 10, "lis": 11, "gru": 12}


def month_from_text(text: str) -> int | None:
    """"PAŹDZIERNIK", "październik 2026", "paź." -> 10. Anything else (e.g. a surname) -> None."""
    folded = fold(text)
    if not folded:
        return None
    words = folded.split(" ")
    word = re.sub(r"[^a-z]", "", words[0])
    rest_is_year = all(re.fullmatch(r"20\d{2}|r\.?", item) for item in words[1:])
    if not rest_is_year:
        return None
    if word in MONTHS:
        return MONTHS[word]
    if word in MONTH_ABBREVIATIONS and (len(words) > 1 or folded.endswith(".")):
        return MONTH_ABBREVIATIONS[word]
    return None


def weekday_from_text(text: str) -> int | None:
    word = re.sub(r"[^a-z]", "", fold(text))
    return WEEKDAYS.get(word)


def hhmm(value: time) -> str:
    return f"{value.hour:02d}:{value.minute:02d}"


def to_minutes(value: time) -> int:
    return value.hour * 60 + value.minute


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", fold(value)).strip("-") or "x"
