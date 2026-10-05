"""Practical-classes matrix ("harmonogram zajęć praktycznych").

Layout (positions are discovered, never hard-coded):

    GRUPA | PAŹDZIERNIK ............ | LISTOPAD ...   <- month row (merged across its days)
          | pn  | śr  | czw | pt ... |                <- weekday row
          | 19  | 21  | 22  | 23 ... |                <- day-of-month row
    1 | a | CSM1 SP 8:00-15:30 | OCO | ...             <- one row per subgroup;
      | b |   (merged with a)  |     |                    a cell merged over a+b applies to both
    ...
    A godz. 7:00-14:30   A(double underline) godz. 7:00-18:15   <- hour profiles by font style
    Przedmiot | Oddział | Miejsce | Prowadzący          <- legend header
    ZP | 12 | 50 | Chirurgia ... | Chirurgii | USK Opole | Paulina Zalejska

A grid cell is resolved against the legend by code ("12", "OCO"), by fill colour of the
legend's code cell, and by instructor initials ("PZ", "JSz", "ES-C"). Working hours come
from (in order) the cell text, the legend row, the cell's font style, a default.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import date, time
import re

from ..model import KIND_PRACTICAL, ParsedFile, PlanParseError, RawEvent
from ..textutil import (
    as_code,
    clean_multiline,
    find_time_range,
    fold,
    month_from_text,
    weekday_from_text,
)
from ..xlsx import CellStyle, SheetGrid

DEFAULT_HOURS = (time(7, 0), time(14, 30))
TYPE_RE = re.compile(r"^(zp|pz|csm)(?:[\s-]*\(?csm\)?)?$")
INITIALS_RE = re.compile(r"^[A-ZĄĆĘŁŃÓŚŹŻ][A-Za-ząćęłńóśźżĄĆĘŁŃÓŚŹŻ]{0,2}(?:-?[A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]{0,2})*$")


@dataclass
class LegendEntry:
    row: int
    type: str
    code: str
    fill: str | None
    subject: str = ""
    dept: str = ""
    place: str = ""
    instructors: list[str] = field(default_factory=list)
    hours: tuple[time, time] | None = None

    @property
    def is_csm(self) -> bool:
        return "csm" in fold(self.type)


@dataclass
class HourProfile:
    row: int
    col: int
    key: tuple[str, bool, bool]
    start: time
    end: time


@dataclass
class Layout:
    group_num_col: int
    group_sub_col: int
    month_row: int
    weekday_row: int | None
    day_row: int
    date_columns: list[tuple[int, date]]
    group_rows: list[tuple[int, str]]


# --------------------------------------------------------------------------- detection


def _find_group_header(grid: SheetGrid) -> tuple[int, int] | None:
    for row in range(1, min(grid.max_row, 15) + 1):
        for col in range(1, min(grid.max_col, 6) + 1):
            if fold(grid.text(row, col)) in {"grupa", "grupy", "gr", "gr."}:
                return row, col
    return None


def _find_month_row(grid: SheetGrid, start_row: int) -> int | None:
    for row in range(max(1, start_row - 1), min(grid.max_row, start_row + 4) + 1):
        months = sum(1 for col, text in grid.row_texts(row) if col > 1 and month_from_text(text) and len(text) >= 3)
        if months:
            return row
    return None


def looks_like_practical(grid: SheetGrid) -> bool:
    header = _find_group_header(grid)
    return header is not None and _find_month_row(grid, header[0]) is not None


# --------------------------------------------------------------------------- dates


def _academic_years(grid: SheetGrid, last_row: int) -> tuple[int, int] | None:
    for row in range(1, last_row + 1):
        for _, text in grid.row_texts(row):
            match = re.search(r"(20\d{2})\s*/\s*(20\d{2})", text)
            if match and int(match.group(2)) == int(match.group(1)) + 1:
                return int(match.group(1)), int(match.group(2))
    return None


def _any_year(grid: SheetGrid, last_row: int) -> int | None:
    for row in range(1, last_row + 1):
        for _, text in grid.row_texts(row):
            match = re.search(r"\b(20\d{2})\b", text)
            if match:
                return int(match.group(1))
    return None


def _resolve_dates(
    grid: SheetGrid,
    columns: list[tuple[int, int, int, int | None]],
    header_row: int,
    reference: date | None,
) -> tuple[list[tuple[int, date]], list[str]]:
    """columns: (col, month, day, weekday or None). Years are chosen so weekdays line up."""
    warnings: list[str] = []
    academic = _academic_years(grid, header_row)

    def guess(month: int, base: int) -> int:
        if academic:
            return academic[0] if month >= 8 else academic[1]
        return base

    # Candidate base years; pick the one giving the best weekday agreement.
    if academic:
        bases = [academic[0]]
    else:
        anchor = _any_year(grid, header_row) or (reference.year if reference else date.today().year)
        bases = [anchor - 1, anchor, anchor + 1]

    def build(base: int, shift: int) -> tuple[list[tuple[int, date]], int, int]:
        result: list[tuple[int, date]] = []
        matches = checked = 0
        year = base
        previous_month: int | None = None
        for col, month, day, weekday in columns:
            if academic:
                year = guess(month, base) + shift
            elif previous_month is not None and month < previous_month:
                year += 1
            previous_month = month
            try:
                current = date(year, month, day)
            except ValueError:
                continue
            result.append((col, current))
            if weekday is not None:
                checked += 1
                matches += int(current.weekday() == weekday)
        return result, matches, checked

    best: tuple[list[tuple[int, date]], int, int] | None = None
    for base in bases:
        for shift in ((0, -1, 1) if academic else (0,)):
            candidate = build(base, shift)
            if best is None or candidate[1] > best[1]:
                best = candidate
    assert best is not None
    resolved, matches, checked = best
    if checked and matches < checked:
        warnings.append(
            f"{grid.title}: {checked - matches} z {checked} dat nie zgadza się z dniem tygodnia w nagłówku – sprawdź harmonogram."
        )
    return resolved, warnings


def _find_layout(grid: SheetGrid, reference: date | None) -> tuple[Layout, list[str]]:
    header = _find_group_header(grid)
    if header is None:
        raise PlanParseError("Brak nagłówka GRUPA w harmonogramie zajęć praktycznych.")
    header_row, group_col = header
    month_row = _find_month_row(grid, header_row)
    if month_row is None:
        raise PlanParseError("Nie znaleziono wiersza z nazwami miesięcy w harmonogramie.")

    # Day-of-month row: the first row under the months with mostly integers 1..31.
    day_row = None
    weekday_row = None
    for row in range(month_row + 1, min(grid.max_row, month_row + 5) + 1):
        numbers = 0
        weekdays = 0
        for col, text in grid.row_texts(row):
            if col <= group_col:
                continue
            if re.fullmatch(r"\d{1,2}", text) and 1 <= int(text) <= 31:
                numbers += 1
            elif weekday_from_text(text) is not None:
                weekdays += 1
        if weekdays and weekday_row is None and numbers == 0:
            weekday_row = row
        if numbers >= 1:
            day_row = row
            break
    if day_row is None:
        raise PlanParseError("Nie znaleziono wiersza z numerami dni w harmonogramie.")

    first_date_col = group_col + 1
    if grid.origin(header_row, group_col + 1) == grid.origin(header_row, group_col):
        first_date_col = group_col + 2  # "GRUPA" merged over the number + subgroup columns
    group_sub_col = group_col + 1

    columns: list[tuple[int, int, int, int | None]] = []
    current_month: int | None = None
    for col in range(first_date_col, grid.max_col + 1):
        month = month_from_text(grid.text(month_row, col))
        if month:
            current_month = month
        day_text = grid.text(day_row, col)
        if current_month is None or not re.fullmatch(r"\d{1,2}", day_text):
            continue
        day = int(day_text)
        if not 1 <= day <= 31:
            continue
        weekday = weekday_from_text(grid.text(weekday_row, col)) if weekday_row else None
        columns.append((col, current_month, day, weekday))

    if not columns:
        raise PlanParseError("Nie rozpoznano kolumn dat w harmonogramie zajęć praktycznych.")

    date_columns, warnings = _resolve_dates(grid, columns, header_row, reference)

    group_rows: list[tuple[int, str]] = []
    seen_group = False
    for row in range(day_row + 1, grid.max_row + 1):
        number = grid.text(row, group_col)
        sub = grid.text(row, group_sub_col)
        is_number = bool(re.fullmatch(r"\d{1,2}", number))
        is_sub = bool(re.fullmatch(r"[a-zA-Z]{1,2}", sub))
        if is_number or is_sub:
            label = f"{number if is_number else ''}{sub.lower() if is_sub else ''}"
            group_rows.append((row, label))
            seen_group = True
            continue
        if seen_group and not grid.is_row_empty(row):
            break
    if not group_rows:
        raise PlanParseError("Nie znaleziono wierszy grup w harmonogramie zajęć praktycznych.")

    return (
        Layout(
            group_num_col=group_col,
            group_sub_col=group_sub_col,
            month_row=month_row,
            weekday_row=weekday_row,
            day_row=day_row,
            date_columns=date_columns,
            group_rows=group_rows,
        ),
        warnings,
    )


# --------------------------------------------------------------------------- legend


_LEGEND_HEADERS = {
    "przedmiot": "subject",
    "oddzial": "dept",
    "odzial": "dept",
    "miejsce": "place",
    "miejsce realizacji": "place",
    "prowadzacy": "instructors",
    "prowadzacy zajecia": "instructors",
    "opiekun": "instructors",
}


def _type_column(grid: SheetGrid, row: int) -> int | None:
    for col in range(1, min(grid.max_col, 6) + 1):
        text = fold(grid.text(row, col))
        if text and TYPE_RE.match(text):
            return col
    return None


def _split_people(text: str) -> list[str]:
    people = [part.strip() for part in re.split(r"[,;\n]|\s+i\s+", text) if part.strip()]
    return [re.sub(r"\s+", " ", person) for person in people]


def _parse_legend(grid: SheetGrid, after_row: int) -> list[LegendEntry]:
    entries: list[LegendEntry] = []
    headers: dict[int, str] = {}
    for row in range(after_row + 1, grid.max_row + 1):
        row_headers = {col: _LEGEND_HEADERS[fold(text)] for col, text in grid.row_texts(row) if fold(text) in _LEGEND_HEADERS}
        if len(row_headers) >= 2:
            headers = row_headers
            continue
        type_col = _type_column(grid, row)
        if type_col is None or not headers:
            continue

        code_col = type_col + 1
        entry = LegendEntry(
            row=row,
            type=clean_multiline(grid.text(row, type_col)).upper().replace("  ", " "),
            code=as_code(grid.value(row, code_col)),
            fill=grid.style(row, code_col).fill,
        )
        values: dict[str, list[str]] = {}
        for col, text in grid.row_texts(row):
            if col <= code_col:
                continue
            if col == code_col + 1 and re.fullmatch(r"\d+(?:[.,]\d+)?", text):
                continue  # number of hours
            found = find_time_range(text)
            if found:
                entry.hours = (found[0], found[1])
                text = re.sub(r"(?i)\bgodz\.?", "", text[: found[2][0]] + " " + text[found[2][1] :])
                text = re.sub(r"\s+", " ", text).strip(" ,;:-()")
                if len(re.findall(r"[^\W\d_]", text)) < 3:
                    continue
            target = min(headers, key=lambda header_col: abs(header_col - col))
            values.setdefault(headers[target], []).append(clean_multiline(text))
        entry.subject = " ".join(values.get("subject", []))
        entry.dept = ", ".join(values.get("dept", []))
        entry.place = ", ".join(values.get("place", []))
        entry.instructors = [person for text in values.get("instructors", []) for person in _split_people(text)]
        if entry.subject or entry.code:
            entries.append(entry)
    return entries


def _legend_start(grid: SheetGrid, layout: Layout) -> int:
    return layout.group_rows[-1][0]


def _hour_profiles(grid: SheetGrid, layout: Layout, legend_rows: set[int]) -> list[HourProfile]:
    grid_rows = {row for row, _ in layout.group_rows}
    profiles: list[HourProfile] = []
    for row in range(layout.day_row + 1, grid.max_row + 1):
        if row in grid_rows or row in legend_rows:
            continue
        for col, text in grid.row_texts(row):
            if "godz" not in fold(text):
                continue
            found = find_time_range(text)
            if not found:
                continue
            key: tuple[str, bool, bool] | None = None
            for marker_col in range(col - 1, 0, -1):
                marker = grid.text(row, marker_col)
                if not marker:
                    continue
                if find_time_range(marker):
                    break
                key = grid.style(row, marker_col).time_key
                break
            if key is None:
                key = grid.style(row, col).time_key
            profiles.append(HourProfile(row=row, col=col, key=key, start=found[0], end=found[1]))
    profiles.sort(key=lambda profile: (profile.row, profile.col))
    return profiles


# --------------------------------------------------------------------------- cells


def _name_parts(person: str) -> list[str]:
    words = [word for word in re.split(r"\s+", person.strip()) if word]
    # Drop academic titles that sometimes appear in the legend.
    words = [word for word in words if fold(word).rstrip(".") not in {"dr", "mgr", "prof", "hab", "lek", "inz", "pielegn"}]
    parts: list[str] = []
    for word in words:
        parts.extend(piece for piece in word.split("-") if piece)
    return parts


def _initial_segments(token: str) -> list[str]:
    return [segment for segment in re.findall(r"[A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]*", token) if segment]


def initials_score(token: str, person: str) -> int:
    """How well "PZ", "JSz", "ES-C", "K" abbreviate a person.

    2 = every name part matched in order, 1 = a partial match: leading parts ("ZŁ" for
    Zuzanna Łazar-Chylińska) or surname-only ("K" for Paulina Kornek), 0 = no match.
    """
    segments = _initial_segments(token)
    parts = _name_parts(person)
    if not segments or not parts or len(segments) > len(parts):
        return 0

    def aligned(names: list[str]) -> bool:
        return all(fold(part).startswith(fold(segment)) for segment, part in zip(segments, names))

    if aligned(parts):
        return 2 if len(segments) == len(parts) else 1
    if len(parts) > 1 and aligned(parts[1:]):
        return 1
    return 0


def _match_people(tokens: list[str], people: list[str]) -> list[str]:
    best: list[str] = []
    best_score = 0
    for token in tokens:
        if not INITIALS_RE.match(token):
            continue
        for person in people:
            score = initials_score(token, person)
            if score > best_score:
                best, best_score = [person], score
            elif score and score == best_score and person not in best:
                best.append(person)
    return best


def _prettify_dept(dept: str) -> str:
    text = dept.strip()
    if not text:
        return ""
    first = text.split(" ")[0]
    if first.isupper() or fold(first).startswith(("oddzial", "odzial", "klinika", "zaklad")):
        return text
    if re.search(r"(ii|ji|yi|czy|ny|wy)$", fold(first)):
        return f"Oddział {text[0].upper()}{text[1:]}"
    return text


@dataclass
class _Resolved:
    entry: LegendEntry | None
    room: str
    people: list[str]
    leftovers: list[str]


def _resolve(text: str, style: CellStyle, legend: list[LegendEntry]) -> _Resolved:
    tokens = text.split()
    first = fold(tokens[0]) if tokens else ""
    whole = fold(text)

    scored: list[tuple[int, int, LegendEntry, list[str]]] = []
    for order, entry in enumerate(legend):
        code = fold(entry.code)
        code_match = bool(code) and (code == first or code == whole or whole.startswith(code + " "))
        fill_match = bool(style.fill) and style.fill == entry.fill
        people = _match_people(tokens[1:] if code_match else tokens, entry.instructors)
        score = 4 * code_match + 3 * fill_match + 2 * bool(people)
        if score:
            scored.append((score, -order, entry, people))
    if not scored:
        return _Resolved(entry=None, room="", people=[], leftovers=tokens)

    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    best_score = scored[0][0]
    if best_score < 2:
        return _Resolved(entry=None, room="", people=[], leftovers=tokens)
    _, _, entry, people = scored[0]

    consumed: set[int] = set()
    room = ""
    code = fold(entry.code)
    code_tokens = len(entry.code.split()) if code and (whole == code or whole.startswith(code + " ")) else 0
    if code_tokens:
        consumed.update(range(code_tokens))
    elif tokens and (re.search(r"\d", tokens[0]) or fold(tokens[0]).startswith("csm") or not INITIALS_RE.match(tokens[0])):
        room = tokens[0]  # e.g. "CSM1", "606", "0004"
        consumed.add(0)
    for index, token in enumerate(tokens):
        if index in consumed:
            continue
        if any(initials_score(token, person) for person in people):
            consumed.add(index)
    leftovers = [token for index, token in enumerate(tokens) if index not in consumed]
    return _Resolved(entry=entry, room=room, people=people, leftovers=leftovers)


def _hours_for(style: CellStyle, profiles: list[HourProfile]) -> tuple[time, time] | None:
    if not profiles:
        return None
    for profile in profiles:
        if profile.key == style.time_key:
            return profile.start, profile.end
    underlined = style.time_key[0] != "none"
    for profile in profiles:
        if (profile.key[0] != "none") == underlined:
            return profile.start, profile.end
    return profiles[0].start, profiles[0].end


def _cell_events(
    *,
    grid: SheetGrid,
    row: int,
    col: int,
    group: str,
    day: date,
    legend: list[LegendEntry],
    profiles: list[HourProfile],
) -> list[RawEvent]:
    raw = grid.text(row, col)
    if not raw or not raw.strip():
        return []
    style = grid.style(row, col)
    events: list[RawEvent] = []
    for line in [part.strip() for part in re.split(r"\n+", raw) if part.strip()]:
        text = re.sub(r"\s+", " ", line)
        explicit = find_time_range(text)
        if explicit:
            span = explicit[2]
            text = (text[: span[0]] + " " + text[span[1] :]).strip()
            text = re.sub(r"\bgodz\.?\s*$", "", text).strip()
        resolved = _resolve(text, style, legend)
        entry = resolved.entry

        time_uncertain = False
        if explicit:
            start, end = explicit[0], explicit[1]
        elif entry is not None and entry.hours:
            start, end = entry.hours
        else:
            hours = _hours_for(style, profiles)
            if hours is None:
                hours = DEFAULT_HOURS
                time_uncertain = True
            start, end = hours

        notes: list[str] = []
        if entry is None:
            subject = "Zajęcia praktyczne"
            notes.append(f"Wpis w harmonogramie: {line}")
            dept = place = who = code = room = ""
            csm = False
            entry_type = "ZP"
        else:
            subject = entry.subject or "Zajęcia praktyczne"
            csm = entry.is_csm or fold(resolved.room).startswith("csm")
            room = resolved.room
            code = entry.code
            people = resolved.people or entry.instructors
            who = ", ".join(people)
            entry_type = entry.type or "ZP"
            if csm:
                dept = "Centrum Symulacji Medycznej"
                location = room if fold(room).startswith("csm") or not room else f"sala {room}"
                place = " · ".join(part for part in ("Uniwersytet Opolski", location) if part)
                if not room:
                    room = entry.place or "CSM"
                code = code or room
            else:
                dept = _prettify_dept(entry.dept)
                place = entry.place
                if code:
                    notes.append(f"Kod w harmonogramie: {code}")
            if resolved.leftovers:
                notes.append(" ".join(resolved.leftovers))

        if time_uncertain:
            notes.append("Godziny do potwierdzenia")
        if end <= start:
            continue

        events.append(
            RawEvent(
                date=day,
                start=start,
                end=end,
                subject=subject,
                kind="practical",
                type=entry_type,
                instructor=who,
                room=room,
                dept=dept,
                place=place,
                code=code,
                group=group,
                note=" · ".join(notes),
                cancelled=style.strike,
                time_uncertain=time_uncertain,
                csm=csm,
                origin=f"{grid.title}!R{row}C{col}",
            )
        )
    return events


# --------------------------------------------------------------------------- entry point


def _sheet_title(grid: SheetGrid, before_row: int) -> str:
    parts = [
        clean_multiline(text)
        for row in range(1, before_row)
        for _, text in grid.row_texts(row, origins_only=True)
        if len(text) > 6
    ]
    return " · ".join(parts)


def parse_practical_sheet(grid: SheetGrid, reference: date | None = None) -> ParsedFile:
    layout, warnings = _find_layout(grid, reference)
    legend = _parse_legend(grid, _legend_start(grid, layout))
    legend_rows = {entry.row for entry in legend}
    profiles = _hour_profiles(grid, layout, legend_rows)
    if not legend:
        warnings.append(f"{grid.title}: brak legendy przedmiotów – wpisy pokazane bez opisu.")

    events: list[RawEvent] = []
    unresolved: Counter[str] = Counter()
    used: set[tuple[str, str]] = set()
    for row, group in layout.group_rows:
        for col, day in layout.date_columns:
            for event in _cell_events(
                grid=grid, row=row, col=col, group=group, day=day, legend=legend, profiles=profiles
            ):
                if event.subject == "Zajęcia praktyczne" and event.note.startswith("Wpis w harmonogramie"):
                    unresolved[grid.text(row, col)] += 1
                used.add((event.type, fold(event.code)))
                events.append(event)

    for text, count in unresolved.items():
        warnings.append(f"{grid.title}: nie rozpoznano wpisu „{text}” ({count}×) – pokazano jako zajęcia praktyczne.")

    notes: list[str] = []
    distinct = []
    used_hours = {(event.start, event.end) for event in events if not event.csm}
    for profile in profiles:
        label = f"{profile.start.hour}:{profile.start.minute:02d}–{profile.end.hour}:{profile.end.minute:02d}"
        if label not in distinct and (profile.start, profile.end) in used_hours:
            distinct.append(label)
    if distinct:
        notes.append("Godziny na oddziałach wg harmonogramu: " + ", ".join(distinct) + ".")
    for entry in legend:
        if entry.hours and not entry.is_csm and (entry.type, fold(entry.code)) in used:
            name = entry.place or entry.dept or entry.code
            notes.append(
                f"{name}: {entry.hours[0].hour}:{entry.hours[0].minute:02d}–{entry.hours[1].hour}:{entry.hours[1].minute:02d}."
            )

    return ParsedFile(
        kind=KIND_PRACTICAL,
        events=events,
        title=_sheet_title(grid, layout.month_row),
        warnings=warnings,
        notes=notes,
    )


def parse_practical(grids: list[SheetGrid], reference: date | None = None) -> ParsedFile:
    parsed: list[ParsedFile] = []
    errors: list[str] = []
    candidates = [grid for grid in grids if not grid.hidden and looks_like_practical(grid)]
    candidates = candidates or [grid for grid in grids if looks_like_practical(grid)]
    for grid in candidates:
        try:
            parsed.append(parse_practical_sheet(grid, reference))
        except PlanParseError as exc:
            errors.append(str(exc))
    if not parsed:
        raise PlanParseError(errors[0] if errors else "Nie rozpoznano harmonogramu zajęć praktycznych.")
    first = parsed[0]
    for extra in parsed[1:]:
        first.events.extend(extra.events)
        first.warnings.extend(extra.warnings)
        first.notes.extend(note for note in extra.notes if note not in first.notes)
    if not first.events:
        first.warnings.append("Harmonogram nie zawiera jeszcze żadnych wpisów.")
    return first
