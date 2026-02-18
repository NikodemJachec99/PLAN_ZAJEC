import pandas as pd

from app.filters import apply_filters, build_filters


def _fixture() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "subject": ["Anatomia", "Biologia", "Anatomia"],
            "instructor": ["A", "B", "C"],
            "room": ["101", "202", "303"],
            "group": ["11", "12", "3"],
            "oddzial": ["", "Oddzial A", ""],
            "type": ["Wyklad", "Laboratorium", "Praktyki"],
            "source": ["main", "main", "praktyki"],
            "date": pd.to_datetime(["2026-02-10", "2026-02-10", "2026-02-10"]),
            "start_time_obj": [None, None, None],
            "end_time_obj": [None, None, None],
        }
    )


def test_category_filter_or_within_group() -> None:
    frame = _fixture()
    filters = build_filters(subject=["Anatomia"], room=["101", "303"])

    result = apply_filters(frame, filters)

    assert len(result) == 2
    assert set(result["room"]) == {"101", "303"}


def test_only_magdalenka_keeps_praktyki_rows() -> None:
    frame = _fixture()
    filters = build_filters(only_magdalenka=True)

    result = apply_filters(frame, filters)

    assert len(result) == 2
    assert "12" not in result["group"].tolist()
    assert "praktyki" in result["source"].tolist()
