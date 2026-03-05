from __future__ import annotations

from datetime import date as dt_date, datetime, time as dtime
from pathlib import Path
import re
import unicodedata

import pandas as pd

from .errors import DataSourceUnavailable
from .utils import normalize_text, normalize_time_series, parse_time_value

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


def _ascii_lower(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    stripped = "".join(char for char in normalized if not unicodedata.combining(char))
    return stripped.strip().lower()


def _month_to_number(value: str) -> int | None:
    normalized = _ascii_lower(value)
    if not normalized:
        return None

    mapping = {
        "styczen": 1,
        "luty": 2,
        "marzec": 3,
        "kwiecien": 4,
        "maj": 5,
        "czerwiec": 6,
        "lipiec": 7,
        "sierpien": 8,
        "wrzesien": 9,
        "pazdziernik": 10,
        "listopad": 11,
        "grudzien": 12,
    }

    for label, month in mapping.items():
        if normalized.startswith(label):
            return month
    return None


def _extract_reference_year(matrix: pd.DataFrame) -> int:
    sample = matrix.head(6).fillna("").astype(str).to_numpy().flatten().tolist()
    years: list[int] = []
    for cell in sample:
        for value in re.findall(r"\b20\d{2}\b", cell):
            years.append(int(value))
    if years:
        return max(years)
    return datetime.now().year


def _extract_matrix_date_columns(matrix: pd.DataFrame) -> list[tuple[int, pd.Timestamp]]:
    if matrix.shape[0] < 5 or matrix.shape[1] < 3:
        return []

    year = _extract_reference_year(matrix)
    month_row = 2
    day_row = 4
    current_month: int | None = None
    previous_month: int | None = None

    result: list[tuple[int, pd.Timestamp]] = []
    for col in range(2, matrix.shape[1]):
        month_cell = normalize_text(matrix.iat[month_row, col])
        parsed_month = _month_to_number(month_cell)
        if parsed_month is not None:
            if previous_month is not None and parsed_month < previous_month and previous_month - parsed_month >= 6:
                year += 1
            current_month = parsed_month
            previous_month = parsed_month

        if current_month is None:
            continue

        day_value = matrix.iat[day_row, col]
        if pd.isna(day_value):
            continue

        try:
            day_int = int(float(day_value))
        except (TypeError, ValueError):
            continue

        if day_int < 1 or day_int > 31:
            continue

        try:
            event_date = pd.Timestamp(dt_date(year, current_month, day_int))
        except ValueError:
            continue

        result.append((col, event_date))

    return result


def _extract_praktyki_legend(matrix: pd.DataFrame) -> dict[str, dict[str, str]]:
    subject_header_row: int | None = None
    max_cols = matrix.shape[1]

    for row in range(matrix.shape[0]):
        for col in range(min(max_cols, 12)):
            if _ascii_lower(normalize_text(matrix.iat[row, col])) == "przedmiot":
                subject_header_row = row
                break
        if subject_header_row is not None:
            break

    if subject_header_row is None:
        return {}

    legend: dict[str, dict[str, str]] = {}
    for row in range(subject_header_row + 1, matrix.shape[0]):
        type_value = normalize_text(matrix.iat[row, 0])
        code_value = normalize_text(matrix.iat[row, 1])
        subject_value = normalize_text(matrix.iat[row, 3])
        oddzial_value = normalize_text(matrix.iat[row, 16]) if max_cols > 16 else ""
        room_value = normalize_text(matrix.iat[row, 22]) if max_cols > 22 else ""
        instructor_value = normalize_text(matrix.iat[row, 31]) if max_cols > 31 else ""

        if not type_value and not code_value and not subject_value:
            continue

        payload = {
            "subject": subject_value,
            "oddzial": oddzial_value,
            "room": room_value,
            "instructor": instructor_value,
            "type": type_value or "ZP",
        }

        keys: list[str] = []
        if code_value:
            keys.append(_ascii_lower(code_value))
        if type_value and "csm" in _ascii_lower(type_value):
            keys.append("csm")
        if type_value and not code_value:
            keys.append(_ascii_lower(type_value))

        for key in keys:
            if key:
                legend[key] = payload

    return legend


def _parse_cell_content(raw_value: str) -> tuple[str, str, str]:
    text = re.sub(r"\s+", " ", normalize_text(raw_value))
    if not text:
        return "", "", ""

    time_match = re.search(r"(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})", text)
    start_raw = ""
    end_raw = ""
    if time_match:
        start_raw, end_raw = time_match.group(1), time_match.group(2)
        text = re.sub(r"(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})", "", text).strip()

    return text, start_raw, end_raw


def _derive_lookup_key(token_text: str, legend: dict[str, dict[str, str]]) -> tuple[str, str]:
    if not token_text:
        return "", ""

    parts = token_text.split()
    first = _ascii_lower(parts[0]) if parts else _ascii_lower(token_text)
    second = _ascii_lower(parts[1]) if len(parts) > 1 else ""
    room_override = parts[0].upper() if parts and first.startswith("csm") else ""

    if first.startswith("csm"):
        return "csm", room_override
    if first in legend:
        return first, room_override
    if second and second in legend:
        return second, room_override
    return first, room_override


def _build_praktyki_from_matrix(matrix: pd.DataFrame) -> pd.DataFrame:
    date_columns = _extract_matrix_date_columns(matrix)
    if not date_columns:
        raise DataSourceUnavailable("Nie rozpoznano kolumn dat w pliku praktyk.")

    legend = _extract_praktyki_legend(matrix)

    rows: list[dict[str, object]] = []
    current_major_group = ""
    for row_idx in range(5, matrix.shape[0]):
        type_marker = _ascii_lower(normalize_text(matrix.iat[row_idx, 0]))
        maybe_subject_header = _ascii_lower(normalize_text(matrix.iat[row_idx, 5])) if matrix.shape[1] > 5 else ""
        if type_marker.startswith("zp") or maybe_subject_header == "przedmiot":
            break

        major_raw = matrix.iat[row_idx, 0]
        subgroup_raw = normalize_text(matrix.iat[row_idx, 1]) if matrix.shape[1] > 1 else ""

        if pd.notna(major_raw):
            try:
                current_major_group = str(int(float(major_raw)))
            except (TypeError, ValueError):
                major_text = normalize_text(major_raw)
                if major_text and not major_text.lower().startswith("nan"):
                    current_major_group = major_text

        group_value = f"{current_major_group}{subgroup_raw}" if current_major_group and subgroup_raw else subgroup_raw or current_major_group
        if not group_value:
            continue

        for col_index, event_date in date_columns:
            if col_index >= matrix.shape[1]:
                continue

            cell_value = matrix.iat[row_idx, col_index]
            if pd.isna(cell_value):
                continue

            raw_text = normalize_text(cell_value)
            if not raw_text:
                continue

            token_text, start_raw, end_raw = _parse_cell_content(raw_text)
            lookup_key, room_override = _derive_lookup_key(token_text, legend)
            lookup = legend.get(lookup_key, {})

            start_obj = parse_time_value(start_raw) if start_raw else dtime(7, 0)
            end_obj = parse_time_value(end_raw) if end_raw else dtime(21, 0)
            if start_obj is None or end_obj is None:
                continue

            rows.append(
                {
                    "date": event_date,
                    "start_time_obj": start_obj,
                    "end_time_obj": end_obj,
                    "start_time": start_obj.strftime("%H:%M"),
                    "end_time": end_obj.strftime("%H:%M"),
                    "subject": normalize_text(lookup.get("subject")) or "Zajecia praktyczne",
                    "instructor": normalize_text(lookup.get("instructor")),
                    "room": room_override or normalize_text(lookup.get("room")),
                    "group": group_value,
                    "oddzial": normalize_text(lookup.get("oddzial")),
                    "type": normalize_text(lookup.get("type")) or "ZP",
                    "source": "praktyki",
                }
            )

    if not rows:
        return _empty_output()

    result = pd.DataFrame(rows)
    return result[OUTPUT_COLUMNS].sort_values(by=["date", "start_time_obj"], na_position="last")


def _load_praktyki_tidy(path: Path) -> pd.DataFrame:
    try:
        df = pd.read_excel(path)
    except Exception as exc:
        raise DataSourceUnavailable(f"Nie udalo sie odczytac pliku {path.name}: {exc}") from exc

    if df.empty:
        return _empty_output()

    try:
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

        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.normalize()
            df = df.dropna(subset=["date"])
            if df.empty:
                return _empty_output()

            if "start_time_obj" in df.columns and df["start_time_obj"].notna().any():
                df["start_time_obj"] = normalize_time_series(df["start_time_obj"])
            else:
                fallback_start = (
                    df["start_time"] if "start_time" in df.columns else pd.Series([None] * len(df), index=df.index)
                )
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

        matrix = pd.read_excel(path, header=None)
        return _build_praktyki_from_matrix(matrix)
    except Exception as exc:
        raise DataSourceUnavailable(f"Nie udalo sie odczytac pliku {path.name}: {exc}") from exc

def load_praktyki_data(path: Path | None) -> pd.DataFrame:
    if path is None:
        return _empty_output()
    if not path.exists():
        raise DataSourceUnavailable(f"Nie znaleziono pliku danych: {path.name}")
    return _load_praktyki_tidy(path)

def load_combined_data(data_dir: Path, *, main_file_name: str = MAIN_FILE_NAME, practical_file_name: str | None = None) -> pd.DataFrame:
    main_df = load_main_data(data_dir / main_file_name)
    practical_path = data_dir / practical_file_name if practical_file_name else _resolve_praktyki_path(data_dir)
    praktyki_df = load_praktyki_data(practical_path)
    combined = concat_nonempty([main_df, praktyki_df])

    if combined.empty:
        return _empty_output()

    combined["date"] = pd.to_datetime(combined["date"], errors="coerce").dt.normalize()
    combined = combined.dropna(subset=["date"])

    return combined[OUTPUT_COLUMNS].sort_values(by=["date", "start_time_obj"], na_position="last")
