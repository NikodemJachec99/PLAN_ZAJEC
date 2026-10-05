"""Row-based plan ("plan zajęć"): one row per class block, columns located by header text."""

from __future__ import annotations

from datetime import date, datetime, timedelta
import re
from typing import Callable

from ..model import KIND_MAIN, ParsedFile, PlanParseError, RawEvent
from ..textutil import clean_multiline, find_time_range, fold, parse_date, parse_time, to_minutes
from ..xlsx import SheetGrid

_Rule = tuple[str, Callable[[str], bool]]

HEADER_RULES: list[_Rule] = [
    ("date", lambda h: h.startswith("data")),
    ("weekday", lambda h: h.startswith("dzien")),
    ("combined", lambda h: "laczon" in h),
    ("notes", lambda h: h.startswith(("dodatkowe", "uwagi", "informacje"))),
    ("start", lambda h: re.search(r"(?<![a-z])od(?![a-z])", h) is not None),
    ("end", lambda h: re.search(r"(?<![a-z])do(?![a-z])", h) is not None),
    ("time", lambda h: h.startswith(("godz", "czas"))),
    ("subject", lambda h: h.startswith(("przedmiot", "nazwa przedmiotu", "zajecia"))),
    ("type", lambda h: h.startswith(("rodzaj", "forma", "typ"))),
    ("degree", lambda h: h.startswith(("stopien", "tytul"))),
    ("first_name", lambda h: h.startswith("imie")),
    ("last_name", lambda h: h.startswith("nazwisk")),
    ("instructor", lambda h: h.startswith("prowadz")),
    ("room", lambda h: h.startswith(("sala", "miejsce"))),
    ("field", lambda h: h.startswith("kierunek")),
    ("group", lambda h: h.startswith("grup")),
]

# Layout used by WNoZ for years; only used when header detection fails.
LEGACY_COLUMNS = {
    "date": 1,
    "start": 3,
    "end": 4,
    "subject": 5,
    "type": 6,
    "degree": 7,
    "first_name": 8,
    "last_name": 9,
    "room": 10,
    "field": 11,
    "group": 12,
    "combined": 13,
    "notes": 14,
}
LEGACY_HEADER_ROW = 4

DEFAULT_BLOCK_MIN = 90


def _map_header(grid: SheetGrid, row: int) -> dict[str, int]:
    columns: dict[str, int] = {}
    for col, text in grid.row_texts(row):
        header = fold(text)
        for key, rule in HEADER_RULES:
            if key not in columns and rule(header):
                columns[key] = col
                break
    return columns


def find_header(grid: SheetGrid) -> tuple[int, dict[str, int]] | None:
    for row in range(1, min(grid.max_row, 40) + 1):
        columns = _map_header(grid, row)
        if "date" in columns and "subject" in columns and ("start" in columns or "time" in columns):
            return row, columns
    return None


def looks_like_main_plan(grid: SheetGrid) -> bool:
    return find_header(grid) is not None


def _title(grid: SheetGrid, header_row: int) -> str:
    parts: list[str] = []
    for row in range(1, header_row):
        for col, text in grid.row_texts(row, origins_only=True):
            if not isinstance(grid.value(row, col), str) or text.startswith("=") or len(text) < 6:
                continue
            parts.append(clean_multiline(text))
    return " · ".join(parts)


def _as_of(grid: SheetGrid, header_row: int) -> date | None:
    for row in range(1, header_row + 1):
        for col in range(1, grid.max_col + 1):
            value = grid.value(row, col)
            if isinstance(value, (datetime, date)):
                found = value.date() if isinstance(value, datetime) else value
                if found.year >= 2000:
                    return found
    return None


def _instructor(grid: SheetGrid, row: int, columns: dict[str, int]) -> str:
    if "instructor" in columns:
        return clean_multiline(grid.value(row, columns["instructor"]))
    parts = [clean_multiline(grid.value(row, columns[key])) for key in ("degree", "first_name", "last_name") if key in columns]
    return " ".join(part for part in parts if part)


def _get(grid: SheetGrid, row: int, columns: dict[str, int], key: str) -> str:
    return clean_multiline(grid.value(row, columns[key])) if key in columns else ""


def parse_sheet(grid: SheetGrid, header_row: int, columns: dict[str, int]) -> tuple[list[RawEvent], list[str]]:
    events: list[RawEvent] = []
    warnings: list[str] = []
    last_date: date | None = None

    for row in range(header_row + 1, grid.max_row + 1):
        subject = _get(grid, row, columns, "subject")
        raw_start = grid.value(row, columns["start"]) if "start" in columns else None
        raw_end = grid.value(row, columns["end"]) if "end" in columns else None
        start = parse_time(raw_start)
        end = parse_time(raw_end)
        if (start is None or end is None) and "time" in columns:
            found = find_time_range(_get(grid, row, columns, "time"))
            if found:
                start, end = start or found[0], end or found[1]

        if not subject and start is None and end is None:
            continue  # empty line / footer

        day = parse_date(grid.value(row, columns["date"]))
        if day is None:
            day = last_date
        if day is None:
            warnings.append(f"{grid.title}: wiersz {row} pominięty – brak daty ({subject or 'bez nazwy'}).")
            continue
        last_date = day

        if start is None:
            warnings.append(
                f"{grid.title}: wiersz {row} pominięty – brak godziny rozpoczęcia ({subject or 'bez nazwy'}, {day.isoformat()})."
            )
            continue

        time_uncertain = False
        if end is None or to_minutes(end) <= to_minutes(start):
            fallback = datetime.combine(day, start) + timedelta(minutes=DEFAULT_BLOCK_MIN)
            end = fallback.time() if fallback.date() == day else end
            time_uncertain = True
            warnings.append(
                f"{grid.title}: wiersz {row} – niepoprawna godzina zakończenia, przyjęto {DEFAULT_BLOCK_MIN} min ({subject}, {day.isoformat()})."
            )
            if end is None or to_minutes(end) <= to_minutes(start):
                continue

        notes = [_get(grid, row, columns, "notes")]
        combined = _get(grid, row, columns, "combined")
        if combined:
            notes.append(f"Łączone: {combined}")
        note = " · ".join(part for part in notes if part)

        subject_style = grid.style(row, columns["subject"])
        cancelled = subject_style.strike or "odwolan" in fold(note)

        events.append(
            RawEvent(
                date=day,
                start=start,
                end=end,
                subject=subject or "Zajęcia (bez nazwy w planie)",
                kind="class",
                type=_get(grid, row, columns, "type"),
                instructor=_instructor(grid, row, columns),
                room=_get(grid, row, columns, "room"),
                group=_get(grid, row, columns, "group"),
                note=note,
                cancelled=cancelled,
                time_uncertain=time_uncertain,
                origin=f"{grid.title}!{row}",
            )
        )
    return events, warnings


def parse_main_plan(grids: list[SheetGrid]) -> ParsedFile:
    events: list[RawEvent] = []
    warnings: list[str] = []
    title = ""
    as_of: date | None = None

    candidates = [grid for grid in grids if not grid.hidden] or grids
    for grid in candidates:
        found = find_header(grid)
        if found is None:
            continue
        header_row, columns = found
        sheet_events, sheet_warnings = parse_sheet(grid, header_row, columns)
        events.extend(sheet_events)
        warnings.extend(sheet_warnings)
        title = title or _title(grid, header_row)
        as_of = as_of or _as_of(grid, header_row)

    if not events:
        # Last resort: the historical fixed layout (header in row 4, columns A-N).
        for grid in candidates:
            if grid.max_col < 12:
                continue
            sheet_events, sheet_warnings = parse_sheet(grid, LEGACY_HEADER_ROW, LEGACY_COLUMNS)
            if sheet_events:
                events.extend(sheet_events)
                warnings.extend(sheet_warnings)
                title = title or _title(grid, LEGACY_HEADER_ROW)

    if not events:
        raise PlanParseError("Nie znaleziono żadnych zajęć w planie (nie rozpoznano nagłówków kolumn).")

    return ParsedFile(kind=KIND_MAIN, events=events, title=title, as_of=as_of, warnings=warnings)
