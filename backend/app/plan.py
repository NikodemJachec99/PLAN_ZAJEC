"""Combine parsed source files into the single plan served to the browser."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from difflib import SequenceMatcher
import hashlib
import re
from typing import Any

from .model import KIND_LABELS, ParsedFile, RawEvent
from .textutil import fold, hhmm, slugify, to_minutes

MERGE_GAP_MIN = 20

WHOLE_YEAR = {"", "*", "-", "--", "---", "rok", "caly rok", "cały rok", "wszyscy", "wszystkie grupy", "all", "year", "calosc", "kierunek", "caly kierunek"}

# Hues (oklch) taken from the design; unknown subjects get free hues from SPARE_HUES.
KNOWN_SUBJECTS: list[tuple[str, str | None, int | None]] = [
    ("chirurg", "Chirurgia", 245),
    ("poloznictwo", "Położnictwo i ginekologia", 355),
    ("pediatr", "Pediatria", 300),
    ("psychiatr", "Psychiatria", 80),
    ("anestez", "Anestezjologia", 30),
    ("badania naukowe", "Badania naukowe", 165),
    ("zakazenia", "Zakażenia szpitalne", 125),
    ("jezyk", None, 210),
    ("szkoleni", None, None),
]
SPARE_HUES = [265, 15, 330, 100, 190, 55, 225, 145, 280, 5, 315, 60, 175, 235, 340, 110]

TYPE_LABELS = {
    "WYK": ("Wykład", "WYK"),
    "W": ("Wykład", "WYK"),
    "CW": ("Ćwiczenia", "ĆW"),
    "CW-CSM": ("Ćwiczenia w CSM", "ĆW CSM"),
    "CW-A": ("Ćwiczenia audytoryjne", "ĆW"),
    "CW-L": ("Ćwiczenia laboratoryjne", "ĆW LAB"),
    "CW-P": ("Ćwiczenia praktyczne", "ĆW P"),
    "CW-PR": ("Ćwiczenia praktyczne", "ĆW PR"),
    "CW-S": ("Ćwiczenia seminaryjne", "ĆW S"),
    "CW-K": ("Ćwiczenia kliniczne", "ĆW K"),
    "LEK": ("Lektorat", "LEK"),
    "SEM": ("Seminarium", "SEM"),
    "LAB": ("Laboratorium", "LAB"),
    "SZK": ("Szkolenie", "SZK"),
    "E-L": ("E-learning", "E-L"),
    "EL": ("E-learning", "E-L"),
    "KONS": ("Konsultacje", "KONS"),
    "EGZ": ("Egzamin", "EGZ"),
    "ZAL": ("Zaliczenie", "ZAL"),
    "ZP": ("Zajęcia praktyczne", "ZP"),
    "ZP CSM": ("Zajęcia praktyczne · CSM", "ZP CSM"),
    "PZ": ("Praktyka zawodowa", "PZ"),
}


@dataclass
class SourceFile:
    id: str
    kind: str
    name: str
    sha256: str
    parsed: ParsedFile
    url: str = ""
    origin: str = "site"  # "site" | "seed" | "manual"
    fetched_at: str | None = None
    last_modified: str | None = None
    as_of: date | None = None
    stale: bool = False
    extra_warnings: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------- helpers


def type_labels(code: str) -> tuple[str, str]:
    normalized = re.sub(r"\s+", " ", (code or "").strip().upper()).replace("Ć", "C")
    if normalized in TYPE_LABELS:
        return TYPE_LABELS[normalized]
    match = re.fullmatch(r"CW[- ]?(.+)", normalized)
    if match:
        return f"Ćwiczenia ({match.group(1)})", f"ĆW {match.group(1)}"
    label = (code or "").strip() or "Zajęcia"
    return label, label


def group_tokens(raw: str) -> list[str]:
    text = re.sub(r"\s+", " ", (raw or "").strip())
    if fold(text) in WHOLE_YEAR:
        return ["*"]
    tokens: list[str] = []
    for part in re.split(r"[,;/+&]|\s+i\s+|\s+oraz\s+", text):
        part = re.sub(r"(?i)^\s*(gr\.?|grupa|grupy)\s*", "", part).strip()
        if not part:
            continue
        if fold(part) in WHOLE_YEAR:
            tokens.append("*")
            continue
        range_match = re.fullmatch(r"(\d{1,2})\s*[-–]\s*(\d{1,2})", part)
        if range_match:
            first, last = int(range_match.group(1)), int(range_match.group(2))
            if first <= last and last - first < 40:
                tokens.extend(str(number) for number in range(first, last + 1))
                continue
        sub_match = re.fullmatch(r"(\d{1,2})\s*([a-zA-Z])", part)
        if sub_match:
            tokens.append(f"{int(sub_match.group(1))}{sub_match.group(2).lower()}")
            continue
        if re.fullmatch(r"\d{1,2}", part):
            tokens.append(str(int(part)))
            continue
        tokens.append(part.upper())
    return list(dict.fromkeys(tokens)) or ["*"]


def _roman_value(token: str) -> int | None:
    values = {"I": 1, "V": 5, "X": 10}
    if not token or any(char not in values for char in token):
        return None
    total = 0
    for index, char in enumerate(token):
        value = values[char]
        if index + 1 < len(token) and values[token[index + 1]] > value:
            total -= value
        else:
            total += value
    return total


def _option_sort_key(token: str) -> tuple[int, int, str]:
    sub = re.fullmatch(r"(\d+)([a-z]*)", token)
    if sub:
        return (0, int(sub.group(1)), sub.group(2))
    roman = _roman_value(token)
    if roman is not None:
        return (1, roman, token)
    return (2, 0, token)


def _canonical_subjects(events: list[RawEvent]) -> dict[str, str]:
    counts = Counter(event.subject for event in events)
    ordered = [name for name, _ in counts.most_common()]
    mapping: dict[str, str] = {}
    for index, name in enumerate(ordered):
        mapping.setdefault(name, name)
        for other in ordered[index + 1 :]:
            if other in mapping and mapping[other] != other:
                continue
            ratio = SequenceMatcher(None, fold(name), fold(other)).ratio()
            if ratio >= 0.93:
                mapping[other] = mapping[name]
    return mapping


def _subject_meta(names: list[str], hours: dict[str, float]) -> dict[str, dict[str, Any]]:
    meta: dict[str, dict[str, Any]] = {}
    used_hues: list[int] = []
    unknown: list[str] = []
    for name in names:
        folded = fold(name)
        for prefix, short, hue in KNOWN_SUBJECTS:
            if folded.startswith(prefix):
                if prefix == "jezyk":
                    language = re.search(r"\(([^)]+)\)", name)
                    short = f"Język {language.group(1)}" if language else "Język obcy"
                if prefix == "szkoleni":
                    short = re.split(r"\s+[-–]\s+", name)[0]
                meta[name] = {"short": short or name, "hue": hue}
                if hue is not None:
                    used_hues.append(hue)
                break
        else:
            unknown.append(name)

    spare = [hue for hue in SPARE_HUES if all(min(abs(hue - used), 360 - abs(hue - used)) >= 18 for used in used_hues)]
    spare = spare or SPARE_HUES
    for index, name in enumerate(sorted(unknown, key=lambda item: (-hours.get(item, 0), item))):
        short = name
        if len(name) > 26:
            short = re.split(r"\s+i\s+|,\s+|\s+[-–]\s+", name)[0]
        meta[name] = {"short": short, "hue": spare[index % len(spare)]}
    return meta


def _merge_blocks(events: list[tuple[str, RawEvent]]) -> list[tuple[str, RawEvent, list[tuple[str, str]]]]:
    buckets: dict[tuple, list[tuple[str, RawEvent]]] = defaultdict(list)
    passthrough: list[tuple[str, RawEvent, list[tuple[str, str]]]] = []
    for source_id, event in events:
        if event.kind != "class":
            passthrough.append((source_id, event, [(hhmm(event.start), hhmm(event.end))]))
            continue
        key = (
            event.date,
            event.subject,
            event.type,
            event.instructor,
            event.room,
            event.group,
            event.note,
            event.cancelled,
        )
        buckets[key].append((source_id, event))

    merged: list[tuple[str, RawEvent, list[tuple[str, str]]]] = []
    for items in buckets.values():
        items.sort(key=lambda item: (item[1].start, item[1].end))
        current_source, current = items[0]
        parts = [(hhmm(current.start), hhmm(current.end))]
        current = RawEvent(**{**current.__dict__})
        for source_id, event in items[1:]:
            gap = to_minutes(event.start) - to_minutes(current.end)
            if 0 <= gap <= MERGE_GAP_MIN:
                current.end = max(current.end, event.end)
                current.time_uncertain = current.time_uncertain or event.time_uncertain
                parts.append((hhmm(event.start), hhmm(event.end)))
                continue
            if gap < 0 and event.end <= current.end:
                continue  # fully contained duplicate
            merged.append((current_source, current, parts))
            current_source, current = source_id, RawEvent(**{**event.__dict__})
            parts = [(hhmm(event.start), hhmm(event.end))]
        merged.append((current_source, current, parts))
    return merged + passthrough


def _mode(event: RawEvent) -> str:
    if event.kind == "practical":
        return "onsite"
    room = fold(event.room)
    if any(word in room for word in ("teams", "online", "zdaln", "e-learning", "elearning", "moodle", "zoom")):
        return "remote"
    if not room or room.startswith("brak") or room in {"-", "--", "?"}:
        return "unassigned"
    return "onsite"


def _location(event: RawEvent, mode: str) -> tuple[str, str, str]:
    """(where, where_short, place) as shown on cards."""
    if event.kind == "practical":
        where = event.dept or event.place or "Zajęcia praktyczne"
        place = event.place if event.dept else ""
        short = event.code if event.csm and event.code else (event.dept or event.place or event.code)
        return where, short, place
    room = event.room.strip()
    if mode == "remote":
        teams = "teams" in fold(room)
        return ("Online – MS Teams" if teams else f"Online – {room}"), ("Teams" if teams else "online"), ""
    if mode == "unassigned":
        return "Brak sali w planie", "bez sali", ""
    if fold(room).startswith("csm"):
        return f"Centrum Symulacji Medycznej · {room}", room, "Uniwersytet Opolski"
    if re.match(r"(?i)^(sala|s\.)\s", room):
        return room, room, "Uniwersytet Opolski"
    return f"Sala {room}", f"s. {room}", "Uniwersytet Opolski"


def _event_id(*parts: Any) -> str:
    return hashlib.sha1("|".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:16]


def _parse_titles(titles: list[str], first_day: date | None) -> dict[str, str]:
    text = " · ".join(titles)
    folded = fold(text)
    year = ""
    match = re.search(r"\b(i{1,3}|iv|v)\s+rok\b", folded)
    if match:
        year = match.group(1).upper()
    level = ""
    match = re.search(r"\b(i{1,2})\s*(?:st\b|st\.|stop)", folded)
    if match:
        level = match.group(1).upper()
    academic = ""
    match = re.search(r"(20\d{2})\s*/\s*(20\d{2})", text)
    if match:
        academic = f"{match.group(1)}/{match.group(2)}"
    semester = "zimowy" if "zimow" in folded else "letni" if "letni" in folded else ""
    if first_day and not academic:
        start_year = first_day.year if first_day.month >= 8 else first_day.year - 1
        academic = f"{start_year}/{start_year + 1}"
    if first_day and not semester:
        semester = "zimowy" if first_day.month >= 8 or first_day.month <= 1 else "letni"
    return {"year": year, "level": level, "academic_year": academic, "semester": semester}


# --------------------------------------------------------------------------- build


def build_plan(sources: list[SourceFile], *, version: str, generated_at: str | None = None) -> dict[str, Any]:
    tagged: list[tuple[str, RawEvent]] = [(source.id, event) for source in sources for event in source.parsed.events]
    subject_map = _canonical_subjects([event for _, event in tagged])
    for _, event in tagged:
        event.subject = subject_map.get(event.subject, event.subject)

    merged = _merge_blocks(tagged)

    seen: set[str] = set()
    events: list[dict[str, Any]] = []
    hours: Counter[str] = Counter()
    token_types: dict[str, Counter[str]] = defaultdict(Counter)
    token_subjects: dict[str, Counter[str]] = defaultdict(Counter)
    subgroup_tokens: set[str] = set()
    number_tokens: set[str] = set()

    for source_id, event, parts in merged:
        start, end = hhmm(event.start), hhmm(event.end)
        identity = _event_id(
            event.date.isoformat(), start, end, fold(event.subject), event.type, event.group,
            fold(event.room), fold(event.instructor), event.kind, fold(event.dept),
        )
        if identity in seen:
            continue
        seen.add(identity)

        groups = group_tokens(event.group)
        for token in groups:
            if token == "*":
                continue
            if re.fullmatch(r"\d+[a-z]", token):
                subgroup_tokens.add(token)
            elif token.isdigit():
                number_tokens.add(token)
            else:
                token_types[token][event.type.upper()] += 1
                token_subjects[token][event.subject] += 1

        mode = _mode(event)
        where, where_short, place = _location(event, mode)
        type_label, type_short = type_labels(event.type)
        duration = to_minutes(event.end) - to_minutes(event.start)
        hours[event.subject] += duration / 60

        events.append(
            {
                "id": identity,
                "date": event.date.isoformat(),
                "start": start,
                "end": end,
                "parts": [list(part) for part in parts],
                "subject": event.subject,
                "kind": event.kind,
                "type": event.type,
                "type_label": type_label,
                "type_short": type_short,
                "instructor": event.instructor,
                "room": event.room,
                "code": event.code,
                "dept": event.dept,
                "place_raw": event.place,
                "where": where,
                "where_short": where_short,
                "place": place,
                "mode": mode,
                "group": event.group,
                "groups": groups,
                "note": event.note,
                "cancelled": event.cancelled,
                "time_uncertain": event.time_uncertain,
                "csm": event.csm,
                "source": source_id,
            }
        )

    events.sort(key=lambda item: (item["date"], item["start"], item["end"], item["subject"]))

    subject_names = sorted({item["subject"] for item in events}, key=lambda name: (-hours[name], name))
    subject_meta = _subject_meta(subject_names, hours)
    subjects = []
    for name in subject_names:
        key = slugify(name)[:48]
        subjects.append({"key": key, "name": name, **subject_meta[name]})
    key_by_name = {subject["name"]: subject["key"] for subject in subjects}
    for item in events:
        item["subject_key"] = key_by_name[item["subject"]]

    dimensions = _dimensions(subgroup_tokens, number_tokens, token_types, token_subjects)

    first_day = date.fromisoformat(events[0]["date"]) if events else None
    titles = [source.parsed.title for source in sources if source.parsed.title]
    header = _parse_titles(titles, first_day)
    notes: list[str] = []
    for source in sources:
        notes.extend(note for note in source.parsed.notes if note not in notes)

    return {
        "version": version,
        "generated_at": generated_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "meta": {**header, "notes": notes},
        "sources": [_source_payload(source, events) for source in sources],
        "subjects": subjects,
        "dimensions": dimensions,
        "events": events,
    }


def _dimensions(
    subgroups: set[str],
    numbers: set[str],
    token_types: dict[str, Counter[str]],
    token_subjects: dict[str, Counter[str]],
) -> list[dict[str, Any]]:
    dims: list[dict[str, Any]] = []
    covered_numbers = {re.match(r"\d+", token).group(0) for token in subgroups}  # type: ignore[union-attr]
    options = sorted(subgroups, key=_option_sort_key) + sorted(numbers - covered_numbers, key=_option_sort_key)
    if options:
        dims.append(
            {
                "id": "group",
                "label": "Grupa ćwiczeniowa i praktyki" if subgroups else "Grupa ćwiczeniowa",
                "options": options,
            }
        )

    by_type: dict[str, list[str]] = defaultdict(list)
    for token, types in token_types.items():
        by_type[types.most_common(1)[0][0]].append(token)
    for type_code in sorted(by_type, key=lambda code: (code != "LEK", code != "CW-A", code)):
        tokens = sorted(by_type[type_code], key=_option_sort_key)
        label, _ = type_labels(type_code)
        if type_code == "LEK":
            subjects = Counter()
            for token in tokens:
                subjects.update(token_subjects[token])
            language = re.search(r"\(([^)]+)\)", subjects.most_common(1)[0][0]) if subjects else None
            label = f"Lektorat – język {language.group(1)}" if language else "Lektorat"
        dims.append({"id": slugify(type_code), "label": label, "options": tokens})
    return dims


def _source_payload(source: SourceFile, events: list[dict[str, Any]]) -> dict[str, Any]:
    count = sum(1 for event in events if event["source"] == source.id)
    return {
        "id": source.id,
        "kind": source.kind,
        "label": KIND_LABELS.get(source.kind, source.kind),
        "name": source.name,
        "url": source.url,
        "origin": source.origin,
        "sha256": source.sha256,
        "as_of": source.as_of.isoformat() if source.as_of else None,
        "fetched_at": source.fetched_at,
        "last_modified": source.last_modified,
        "events": count,
        "stale": source.stale,
        "warnings": [*source.parsed.warnings, *source.extra_warnings],
    }


def plan_version(parser_version: str, shas: list[str]) -> str:
    digest = hashlib.sha256((parser_version + "|" + "|".join(sorted(shas))).encode()).hexdigest()
    return digest[:20]
