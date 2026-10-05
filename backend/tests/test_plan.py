from __future__ import annotations

from datetime import date, time

import pytest

from app.calendar import build_ics, event_matches, filter_events, resolve_selection
from app.model import KIND_MAIN, ParsedFile, RawEvent
from app.parsers import parse_workbook
from app.plan import SourceFile, build_plan, group_tokens

from .conftest import MAIN_III, PRACTICAL_III


@pytest.fixture(scope="module")
def plan() -> dict:
    sources = []
    for index, path in enumerate((MAIN_III, PRACTICAL_III)):
        parsed = parse_workbook(path)
        sources.append(SourceFile(id=f"s{index}", kind=parsed.kind, name=path.name, sha256=str(index), parsed=parsed))
    return build_plan(sources, version="test")


def test_nothing_is_lost_when_combining(plan: dict) -> None:
    raw_main = len(parse_workbook(MAIN_III).events)
    raw_practical = len(parse_workbook(PRACTICAL_III).events)
    assert sum(len(event["parts"]) for event in plan["events"]) == raw_main + raw_practical == 640
    assert len({event["id"] for event in plan["events"]}) == len(plan["events"])
    assert [event["date"] for event in plan["events"]] == sorted(event["date"] for event in plan["events"])


def test_consecutive_blocks_are_merged_with_parts(plan: dict) -> None:
    first = next(event for event in plan["events"] if event["date"] == "2026-10-01")
    assert (first["start"], first["end"]) == ("08:00", "13:00")
    assert first["parts"] == [["08:00", "09:30"], ["09:45", "11:15"], ["11:30", "13:00"]]
    # Same subject in a different room stays a separate card (as in the design).
    on_6th = [event for event in plan["events"] if event["date"] == "2026-10-06" and event["type"] == "WYK"]
    assert [(event["start"], event["end"], event["room"]) for event in on_6th] == [
        ("13:15", "14:45", "O45"),
        ("15:00", "17:30", "A1"),
    ]


def test_subject_typos_are_unified(plan: dict) -> None:
    names = {event["subject"] for event in plan["events"]}
    assert "Chirurgia i pielęgniatrstwo chirurgiczne" not in names
    shorts = {subject["name"]: subject["short"] for subject in plan["subjects"]}
    assert shorts["Chirurgia i pielęgniarstwo chirurgiczne"] == "Chirurgia"
    assert shorts["Język obcy (angielski)"] == "Język angielski"


def test_dimensions_and_meta(plan: dict) -> None:
    dims = {dim["id"]: dim for dim in plan["dimensions"]}
    assert dims["group"]["options"][:4] == ["1a", "1b", "2c", "2d"]
    assert len(dims["group"]["options"]) == 20
    assert dims["lek"]["options"] == ["A", "B", "C"]
    assert dims["lek"]["label"] == "Lektorat – język angielski"
    assert dims["cw-a"]["options"] == ["I", "II"]
    assert plan["meta"]["year"] == "III"
    assert plan["meta"]["academic_year"] == "2026/2027"
    assert plan["meta"]["semester"] == "zimowy"


def test_modes_and_locations(plan: dict) -> None:
    remote = next(event for event in plan["events"] if event["room"] == "MsTeams")
    assert (remote["mode"], remote["where"], remote["where_short"]) == ("remote", "Online – MS Teams", "Teams")
    csm = next(event for event in plan["events"] if event["kind"] == "class" and event["room"] == "CSM1")
    assert csm["where"] == "Centrum Symulacji Medycznej · CSM1"
    practical = next(event for event in plan["events"] if event["kind"] == "practical" and event["code"] == "OCO")
    assert practical["where"] == "Oddział Chirurgii onkologicznej"
    assert practical["place"] == "Opolskie Centrum Onkologii"


@pytest.mark.parametrize(
    ("raw", "tokens"),
    [
        ("cały rok", ["*"]),
        ("", ["*"]),
        ("1", ["1"]),
        (1, ["1"]),
        ("A", ["A"]),
        ("II", ["II"]),
        ("1a", ["1a"]),
        ("1-3", ["1", "2", "3"]),
        ("gr. 2, 4", ["2", "4"]),
        ("1a i 1b", ["1a", "1b"]),
    ],
)
def test_group_tokens(raw: object, tokens: list[str]) -> None:
    assert group_tokens(str(raw)) == tokens


def test_selection_filters_exactly_my_groups(plan: dict) -> None:
    selection = resolve_selection(plan, {"group": "1a", "lek": "a", "cw-a": "I"})
    assert selection == {"group": "1a", "lek": "A", "cw-a": "I"}
    mine = filter_events(plan, selection)
    groups = {event["group"] for event in mine}
    assert groups == {"cały rok", "1", "A", "I", "1a"}
    assert not event_matches({"groups": ["1b"]}, selection)
    assert event_matches({"groups": ["1"]}, selection)

    fallback = resolve_selection(plan, {"group": "nie-ma", "lek": ""})
    assert fallback["group"] == "1a" and fallback["lek"] == "A"


def test_ics_export(plan: dict) -> None:
    body = build_ics(plan, {"group": "1a", "lek": "A", "cw-a": "I"})
    assert body.startswith("BEGIN:VCALENDAR\r\n") and body.endswith("END:VCALENDAR\r\n")
    assert "BEGIN:VTIMEZONE" in body
    assert "DTSTART;TZID=Europe/Warsaw:20261001T080000" in body
    assert all(len(line.encode("utf-8")) <= 75 for line in body.split("\r\n"))
    assert body.count("BEGIN:VEVENT") == len(filter_events(plan, {"group": "1a", "lek": "A", "cw-a": "I"}))


def test_cancelled_and_uncertain_flags_survive() -> None:
    event = RawEvent(
        date=date(2026, 10, 1), start=time(8), end=time(9), subject="Test", kind="class", type="WYK",
        group="cały rok", cancelled=True,
    )
    parsed = ParsedFile(kind=KIND_MAIN, events=[event])
    built = build_plan([SourceFile(id="x", kind=KIND_MAIN, name="x.xlsx", sha256="x", parsed=parsed)], version="v")
    assert built["events"][0]["cancelled"] is True
    assert "STATUS:CANCELLED" in build_ics(built, {})
