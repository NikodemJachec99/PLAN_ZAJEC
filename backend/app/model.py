from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, time

KIND_MAIN = "main"
KIND_PRACTICAL = "practical"

KIND_LABELS = {
    KIND_MAIN: "Plan zajęć",
    KIND_PRACTICAL: "Zajęcia praktyczne",
}


@dataclass
class RawEvent:
    """One entry exactly as found in a source file (before merging/decoration)."""

    date: date
    start: time
    end: time
    subject: str
    kind: str  # "class" (row-based plan) or "practical" (matrix)
    type: str
    instructor: str = ""
    room: str = ""
    dept: str = ""
    place: str = ""
    code: str = ""
    group: str = ""
    note: str = ""
    cancelled: bool = False
    time_uncertain: bool = False
    csm: bool = False
    origin: str = ""  # "sheet!C6" - where the entry came from, for debugging


@dataclass
class ParsedFile:
    kind: str
    events: list[RawEvent]
    title: str = ""
    as_of: date | None = None
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


class PlanParseError(ValueError):
    """The workbook is not a plan we know how to read."""


class UnknownLayoutError(PlanParseError):
    """The workbook looks like neither a plan nor a practical schedule (probably unrelated)."""
