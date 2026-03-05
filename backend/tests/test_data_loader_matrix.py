from __future__ import annotations

import pandas as pd

from app.data_loader import _build_praktyki_from_matrix


def test_build_praktyki_from_matrix_uses_full_day_fallback() -> None:
    matrix = pd.DataFrame([[None] * 35 for _ in range(40)])
    matrix.iat[1, 0] = "Semestr 2025/2026"
    matrix.iat[2, 2] = "MARZEC"
    matrix.iat[4, 2] = 16

    matrix.iat[5, 0] = 1
    matrix.iat[5, 1] = "a"
    matrix.iat[5, 2] = "33 K"

    matrix.iat[32, 5] = "Przedmiot"
    matrix.iat[33, 0] = "ZP"
    matrix.iat[33, 1] = "33"
    matrix.iat[33, 3] = "Podstawowa opieka zdrowotna"
    matrix.iat[33, 16] = "POZ"
    matrix.iat[33, 22] = "Przychodnia"
    matrix.iat[33, 31] = "Prowadzacy Test"

    frame = _build_praktyki_from_matrix(matrix)

    assert len(frame) == 1
    row = frame.iloc[0]
    assert row["date"].date().isoformat() == "2026-03-16"
    assert row["start_time"] == "07:00"
    assert row["end_time"] == "21:00"
    assert row["group"] == "1a"
    assert row["subject"] == "Podstawowa opieka zdrowotna"
