from __future__ import annotations

from collections import Counter
from datetime import date, time
import json

import pytest

from app.model import KIND_MAIN, KIND_PRACTICAL, PlanParseError
from app.parsers import parse_workbook
from app.parsers.practical import initials_score
from app.textutil import date_from_filename, find_time_range, parse_date, parse_time

from .conftest import FIXTURES, MAIN_II, MAIN_III, PRACTICAL_II, PRACTICAL_III


def _by(events, group, day):
    return [event for event in events if event.group == group and event.date == date.fromisoformat(day)]


def test_main_plan_iii_is_read_completely() -> None:
    parsed = parse_workbook(MAIN_III)
    assert parsed.kind == KIND_MAIN
    assert len(parsed.events) == 210  # every data row of the sheet (rows 5-214)
    assert parsed.warnings == []
    assert parsed.as_of == date(2026, 9, 29)
    assert Counter(event.type for event in parsed.events) == {"CW-CSM": 76, "WYK": 75, "LEK": 45, "CW-A": 12, "SZK": 2}

    lektorat = [e for e in parsed.events if e.date == date(2026, 10, 6) and e.group == "A"]
    assert len(lektorat) == 1
    assert (lektorat[0].start, lektorat[0].end, lektorat[0].room) == (time(8, 0), time(9, 30), "303")
    assert lektorat[0].instructor == "mgr Mariusz Kurzak"

    bhp = [e for e in parsed.events if e.type == "SZK" and e.date == date(2026, 10, 1)][0]
    assert bhp.note == "obecność obowiązkowa"
    assert {e.group for e in parsed.events} == {"cały rok", "A", "B", "C", "I", "II", *(str(n) for n in range(1, 11))}


def test_practical_matrix_matches_design_reference_data() -> None:
    """The design project ships a hand-checked extraction of this file - match it exactly."""
    parsed = parse_workbook(PRACTICAL_III)
    assert parsed.kind == KIND_PRACTICAL
    assert parsed.warnings == []
    reference = json.loads((FIXTURES / "design_plan_data.json").read_text(encoding="utf-8"))

    mine = {}
    for event in parsed.events:
        mine.setdefault((event.group, event.date.isoformat()), []).append(event)
    expected_total = sum(len(items) for items in reference["groups"].values())
    assert len(parsed.events) == expected_total == 430

    prefixes = {"chir": "chirurg", "polo": "położ", "ped": "pediatr", "psy": "psychiatr", "anest": "anestez"}
    for group, items in reference["groups"].items():
        for item in items:
            found = mine[(group, item["d"])]
            assert len(found) == 1, (group, item)
            event = found[0]
            assert event.subject.lower().startswith(prefixes[item["s"]]), (group, item, event.subject)
            assert event.csm == (item["k"] == "csm")
            assert (f"{event.start.hour}:{event.start.minute:02d}", f"{event.end.hour}:{event.end.minute:02d}") == tuple(item["t"])
            assert event.instructor == item["who"]
            assert event.code == str(item["code"])


def test_merged_cells_apply_to_both_subgroups_and_year_follows_academic_year() -> None:
    parsed = parse_workbook(PRACTICAL_III)
    first = _by(parsed.events, "1a", "2026-10-19")
    second = _by(parsed.events, "1b", "2026-10-19")
    assert len(first) == len(second) == 1  # C6:C7 is merged over subgroups a and b
    assert first[0].room == second[0].room == "CSM1"
    years = {event.date.year for event in parsed.events}
    assert years == {2026, 2027}
    assert min(event.date for event in parsed.events) == date(2026, 10, 19)
    assert max(event.date for event in parsed.events) == date(2027, 1, 22)


def test_practical_hours_follow_underline_and_legend() -> None:
    parsed = parse_workbook(PRACTICAL_III)
    double_underline = _by(parsed.events, "1a", "2026-10-21")[0]
    plain = _by(parsed.events, "1a", "2026-10-23")[0]
    soteria = _by(parsed.events, "1a", "2026-12-11")[0]
    assert (double_underline.start, double_underline.end) == (time(7, 0), time(18, 15))
    assert (plain.start, plain.end) == (time(7, 0), time(14, 30))
    assert (soteria.start, soteria.end) == (time(8, 45), time(20, 0))
    assert soteria.instructor == "Yaroslav Bahriy"
    assert any("8:45–20:00" in note for note in parsed.notes)


def test_previous_year_files_still_parse() -> None:
    main = parse_workbook(MAIN_II)
    practical = parse_workbook(PRACTICAL_II)
    assert main.kind == KIND_MAIN and len(main.events) == 258
    assert practical.kind == KIND_PRACTICAL and len(practical.events) == 366
    assert practical.warnings == []  # every date agrees with its weekday header
    assert {event.date.year for event in practical.events} == {2026}

    kornek = _by(practical.events, "1b", "2026-03-23")[0]  # "33 K"
    assert kornek.instructor == "Paulina Kornek"
    unresolved = [event for event in practical.events if event.note.startswith("Wpis w harmonogramie")]
    assert unresolved == []


def test_non_excel_payload_is_rejected() -> None:
    with pytest.raises(PlanParseError):
        parse_workbook(b"<html>Error</html>")


@pytest.mark.parametrize(
    ("token", "person", "score"),
    [
        ("PZ", "Paulina Zalejska", 2),
        ("JSz", "Joanna Szaporów", 2),
        ("ES-C", "Elżbieta Szlenk-Czyczerska", 2),
        ("ES", "Elżbieta Szlenk-Czyczerska", 1),
        ("ES", "Elżbieta Sobaszek", 2),
        ("ZŁ", "Zuzanna Łazar-Chylińska", 1),
        ("KKB", "Katarzyna Kurkiewicz-Buks", 2),
        ("K", "Paulina Kornek", 1),
        ("MJ", "Jolanta Nawara", 0),
    ],
)
def test_initials(token: str, person: str, score: int) -> None:
    assert initials_score(token, person) == score


def test_text_helpers() -> None:
    assert parse_time("8:00") == time(8, 0)
    assert parse_time("8.15") == time(8, 15)
    assert parse_time(0.5) == time(12, 0)
    assert parse_time(8) == time(8, 0)
    assert parse_time("abc") is None
    start, end, _ = find_time_range("CSM1 SP   8:00 – 15:30")  # type: ignore[misc]
    assert (start, end) == (time(8, 0), time(15, 30))
    assert parse_date("05.10.2026") == date(2026, 10, 5)
    assert date_from_filename("PI_s_III_sem.zimowy_05.10.2026-1.xlsx") == date(2026, 10, 5)
    assert date_from_filename("PI_s_III_29_09_2026.xlsx") == date(2026, 9, 29)
