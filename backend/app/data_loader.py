from __future__ import annotations

from pathlib import Path

import pandas as pd

from .errors import DataSourceUnavailable
from .utils import normalize_text, normalize_time_series

MAIN_FILE_NAME = "plan_zajec.xlsx"
PRAKTYKI_CANDIDATES = ("praktyki_tidy (1).xlsx", "praktyki_tidy.xlsx")

OUTPUT_COLUMNS = [
    "date",
    "start_time",
    "end_time",
    "start_time_obj",
    "end_time_obj",
    "subject",
    "instructor",
    "room",
    "group",
    "oddzial",
    "type",
    "source",
]


def concat_nonempty(frames: list[pd.DataFrame]) -> pd.DataFrame:
    valid_frames = [frame.dropna(axis=1, how="all") for frame in frames if frame is not None and not frame.empty]
    if not valid_frames:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)
    return pd.concat(valid_frames, ignore_index=True, sort=False)


def _empty_output() -> pd.DataFrame:
    return pd.DataFrame(columns=OUTPUT_COLUMNS)


def load_main_data(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise DataSourceUnavailable(f"Nie znaleziono pliku danych: {path.name}")

    try:
        raw_df = pd.read_excel(path, header=3)
    except Exception as exc:
        raise DataSourceUnavailable(f"Nie udalo sie odczytac pliku {path.name}: {exc}") from exc

    if raw_df.empty:
        raise DataSourceUnavailable(f"Plik {path.name} nie zawiera danych.")

    base_columns = [
        "date",
        "day_of_week",
        "start_time",
        "end_time",
        "subject",
        "type",
        "degree",
        "first_name",
        "last_name",
        "room",
        "field_year",
        "group",
        "info_combined",
        "additional_info",
    ]

    if len(raw_df.columns) < len(base_columns):
        raise DataSourceUnavailable(
            f"Struktura pliku {path.name} jest niezgodna z oczekiwanym formatem planu."
        )

    extra_columns = [f"unnamed_{index}" for index in range(len(raw_df.columns) - len(base_columns))]
    raw_df.columns = base_columns + extra_columns

    df = raw_df[
        [
            "date",
            "start_time",
            "end_time",
            "subject",
            "type",
            "degree",
            "first_name",
            "last_name",
            "room",
            "group",
        ]
    ].copy()

    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.normalize()
    df = df.dropna(subset=["date"])

    df["instructor"] = (
        df["degree"].fillna("").astype(str).str.strip()
        + " "
        + df["first_name"].fillna("").astype(str).str.strip()
        + " "
        + df["last_name"].fillna("").astype(str).str.strip()
    ).str.replace(r"\s+", " ", regex=True).str.strip()

    df["group"] = df["group"].fillna("---").astype(str).str.strip()
    df["oddzial"] = ""
    df["source"] = "main"

    df["start_time_obj"] = normalize_time_series(df["start_time"])
    df["end_time_obj"] = normalize_time_series(df["end_time"])
    df["start_time"] = df["start_time_obj"].apply(lambda item: item.strftime("%H:%M") if item else "")
    df["end_time"] = df["end_time_obj"].apply(lambda item: item.strftime("%H:%M") if item else "")

    for column in ("subject", "room", "type"):
        df[column] = df[column].apply(normalize_text)

    return df[OUTPUT_COLUMNS].sort_values(by=["date", "start_time_obj"], na_position="last")


def _resolve_praktyki_path(data_dir: Path) -> Path | None:
    for filename in PRAKTYKI_CANDIDATES:
        candidate = data_dir / filename
        if candidate.exists():
            return candidate
    return None


def load_praktyki_data(data_dir: Path) -> pd.DataFrame:
    path = _resolve_praktyki_path(data_dir)
    if path is None:
        return _empty_output()

    try:
        df = pd.read_excel(path)
    except Exception as exc:
        raise DataSourceUnavailable(f"Nie udalo sie odczytac pliku {path.name}: {exc}") from exc

    if df.empty:
        return _empty_output()

    renamed_columns = {
        "przedmiot": "subject",
        "prowadzacy": "instructor",
        "miejsce": "room",
        "typ": "type",
        "rodzaj": "type",
    }
    for source_col, target_col in renamed_columns.items():
        if source_col in df.columns and target_col not in df.columns:
            df[target_col] = df[source_col]

    if "date" not in df.columns:
        raise DataSourceUnavailable(f"Brak kolumny 'date' w pliku {path.name}.")

    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.normalize()
    df = df.dropna(subset=["date"])
    if df.empty:
        return _empty_output()

    if "start_time_obj" in df.columns and df["start_time_obj"].notna().any():
        df["start_time_obj"] = normalize_time_series(df["start_time_obj"])
    else:
        fallback_start = df["start_time"] if "start_time" in df.columns else pd.Series([None] * len(df), index=df.index)
        df["start_time_obj"] = normalize_time_series(fallback_start)

    if "end_time_obj" in df.columns and df["end_time_obj"].notna().any():
        df["end_time_obj"] = normalize_time_series(df["end_time_obj"])
    else:
        fallback_end = df["end_time"] if "end_time" in df.columns else pd.Series([None] * len(df), index=df.index)
        df["end_time_obj"] = normalize_time_series(fallback_end)

    for column in ("subject", "instructor", "room", "group", "oddzial", "type"):
        if column not in df.columns:
            df[column] = ""
        df[column] = df[column].apply(normalize_text)

    df["source"] = "praktyki"

    df["start_time"] = df["start_time_obj"].apply(lambda item: item.strftime("%H:%M") if item else "")
    df["end_time"] = df["end_time_obj"].apply(lambda item: item.strftime("%H:%M") if item else "")

    return df[OUTPUT_COLUMNS].sort_values(by=["date", "start_time_obj"], na_position="last")


def load_combined_data(data_dir: Path) -> pd.DataFrame:
    main_df = load_main_data(data_dir / MAIN_FILE_NAME)
    praktyki_df = load_praktyki_data(data_dir)
    combined = concat_nonempty([main_df, praktyki_df])

    if combined.empty:
        return _empty_output()

    combined["date"] = pd.to_datetime(combined["date"], errors="coerce").dt.normalize()
    combined = combined.dropna(subset=["date"])

    return combined[OUTPUT_COLUMNS].sort_values(by=["date", "start_time_obj"], na_position="last")
