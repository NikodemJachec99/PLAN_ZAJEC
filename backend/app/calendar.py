"""Filtering events for a student's groups and exporting them as iCalendar."""

from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any, Mapping

VTIMEZONE_WARSAW = [
    "BEGIN:VTIMEZONE",
    "TZID:Europe/Warsaw",
    "BEGIN:DAYLIGHT",
    "TZOFFSETFROM:+0100",
    "TZOFFSETTO:+0200",
    "TZNAME:CEST",
    "DTSTART:19700329T020000",
    "RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU",
    "END:DAYLIGHT",
    "BEGIN:STANDARD",
    "TZOFFSETFROM:+0200",
    "TZOFFSETTO:+0100",
    "TZNAME:CET",
    "DTSTART:19701025T030000",
    "RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU",
    "END:STANDARD",
    "END:VTIMEZONE",
]


def resolve_selection(plan: Mapping[str, Any], requested: Mapping[str, str]) -> dict[str, str]:
    """Use the requested option per dimension, falling back to the first available one."""
    selection: dict[str, str] = {}
    for dim in plan.get("dimensions", []):
        options = dim.get("options", [])
        wanted = (requested.get(dim["id"]) or "").strip()
        match = next((option for option in options if option.lower() == wanted.lower()), None)
        if match is None and options:
            match = options[0]
        if match is not None:
            selection[dim["id"]] = match
    return selection


def event_matches(event: Mapping[str, Any], selection: Mapping[str, str]) -> bool:
    tokens = event.get("groups") or ["*"]
    if "*" in tokens:
        return True
    group = selection.get("group")
    if group:
        if group in tokens:
            return True
        number = re.match(r"\d+", group)
        if number and number.group(0) in tokens:
            return True
    return any(value in tokens for key, value in selection.items() if key != "group")


def filter_events(plan: Mapping[str, Any], selection: Mapping[str, str]) -> list[dict[str, Any]]:
    return [event for event in plan.get("events", []) if event_matches(event, selection)]


def _escape(text: str) -> str:
    return (
        (text or "")
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
    )


def _fold(line: str) -> str:
    raw = line.encode("utf-8")
    if len(raw) <= 75:
        return line
    pieces: list[str] = []
    current = b""
    for char in line:
        encoded = char.encode("utf-8")
        limit = 75 if not pieces else 74
        if len(current) + len(encoded) > limit:
            pieces.append(current.decode("utf-8"))
            current = b""
        current += encoded
    pieces.append(current.decode("utf-8"))
    return "\r\n ".join(pieces)


def _stamp(day: str, hhmm: str) -> str:
    return day.replace("-", "") + "T" + hhmm.replace(":", "") + "00"


def build_ics(plan: Mapping[str, Any], selection: Mapping[str, str]) -> str:
    subjects = {subject["name"]: subject for subject in plan.get("subjects", [])}
    label = " · ".join(value for value in selection.values())
    now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Plan zajec WNoZ UO//PL",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{_escape('Plan zajęć ' + label if label else 'Plan zajęć')}",
        "X-WR-TIMEZONE:Europe/Warsaw",
        "REFRESH-INTERVAL;VALUE=DURATION:PT1H",
        "X-PUBLISHED-TTL:PT1H",
        *VTIMEZONE_WARSAW,
    ]
    group_key = re.sub(r"[^A-Za-z0-9]+", "-", label).strip("-") or "all"
    for event in filter_events(plan, selection):
        short = subjects.get(event["subject"], {}).get("short") or event["subject"]
        location = ", ".join(part for part in (event.get("where"), event.get("place")) if part)
        description = [
            event["subject"],
            event.get("type_label") or event.get("type") or "",
            event.get("instructor") or "",
            {"remote": "Zdalnie", "unassigned": "Sala nieprzypisana"}.get(event.get("mode", ""), "Stacjonarnie"),
        ]
        if len(event.get("parts", [])) > 1:
            description.append("Bloki: " + ", ".join(f"{start}–{end}" for start, end in event["parts"]))
        if event.get("note"):
            description.append(event["note"])
        lines += [
            "BEGIN:VEVENT",
            f"UID:{event['id']}-{group_key}@plan-zajec",
            f"DTSTAMP:{now}",
            f"DTSTART;TZID=Europe/Warsaw:{_stamp(event['date'], event['start'])}",
            f"DTEND;TZID=Europe/Warsaw:{_stamp(event['date'], event['end'])}",
            f"SUMMARY:{_escape(('ODWOŁANE: ' if event.get('cancelled') else '') + short + ' – ' + (event.get('type_label') or ''))}",
            f"LOCATION:{_escape(location)}",
            f"DESCRIPTION:{_escape(chr(10).join(part for part in description if part))}",
            f"STATUS:{'CANCELLED' if event.get('cancelled') else 'CONFIRMED'}",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    return "\r\n".join(_fold(line) for line in lines) + "\r\n"
