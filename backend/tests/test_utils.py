from datetime import datetime, time as dtime

from app.utils import is_magdalenka_group, parse_time_value, to_minutes


def test_parse_time_value_accepts_multiple_formats() -> None:
    assert parse_time_value("08:15") == dtime(8, 15)
    assert parse_time_value("08:15:30") == dtime(8, 15, 30)


def test_parse_time_value_from_datetime() -> None:
    value = datetime(2025, 1, 3, 9, 45, 0)
    assert parse_time_value(value) == dtime(9, 45)


def test_to_minutes() -> None:
    assert to_minutes(dtime(10, 30)) == 630


def test_magdalenka_group_rule() -> None:
    assert is_magdalenka_group("11") is True
    assert is_magdalenka_group("d2") is False
    assert is_magdalenka_group("rok") is True
    assert is_magdalenka_group("12") is False
