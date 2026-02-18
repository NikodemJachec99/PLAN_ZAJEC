from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd

from .utils import is_magdalenka_group


@dataclass(frozen=True)
class ScheduleFilters:
    subject: tuple[str, ...] = ()
    instructor: tuple[str, ...] = ()
    room: tuple[str, ...] = ()
    group: tuple[str, ...] = ()
    oddzial: tuple[str, ...] = ()
    type: tuple[str, ...] = ()
    only_magdalenka: bool = False


def _normalize_values(values: Iterable[str] | None) -> tuple[str, ...]:
    if not values:
        return ()

    normalized = []
    for value in values:
        stripped = str(value).strip().lower()
        if stripped:
            normalized.append(stripped)

    return tuple(sorted(set(normalized)))


def build_filters(
    *,
    subject: list[str] | None = None,
    instructor: list[str] | None = None,
    room: list[str] | None = None,
    group: list[str] | None = None,
    oddzial: list[str] | None = None,
    type: list[str] | None = None,
    only_magdalenka: bool = False,
) -> ScheduleFilters:
    return ScheduleFilters(
        subject=_normalize_values(subject),
        instructor=_normalize_values(instructor),
        room=_normalize_values(room),
        group=_normalize_values(group),
        oddzial=_normalize_values(oddzial),
        type=_normalize_values(type),
        only_magdalenka=only_magdalenka,
    )


def _apply_category(df: pd.DataFrame, column: str, values: tuple[str, ...]) -> pd.DataFrame:
    if not values or column not in df.columns:
        return df

    allowed = set(values)
    normalized_series = df[column].fillna("").astype(str).str.strip().str.lower()
    return df[normalized_series.isin(allowed)]


def apply_filters(df: pd.DataFrame, filters: ScheduleFilters) -> pd.DataFrame:
    filtered = df

    filtered = _apply_category(filtered, "subject", filters.subject)
    filtered = _apply_category(filtered, "instructor", filters.instructor)
    filtered = _apply_category(filtered, "room", filters.room)
    filtered = _apply_category(filtered, "group", filters.group)
    filtered = _apply_category(filtered, "oddzial", filters.oddzial)
    filtered = _apply_category(filtered, "type", filters.type)

    if filters.only_magdalenka and not filtered.empty:
        main_rows = filtered["source"].fillna("").astype(str).str.lower().eq("main")
        keep_rows = (~main_rows) | filtered["group"].fillna("").astype(str).apply(is_magdalenka_group)
        filtered = filtered[keep_rows]

    return filtered


def extract_filter_values(df: pd.DataFrame) -> dict[str, list[str]]:
    def unique_sorted(column: str) -> list[str]:
        if column not in df.columns:
            return []
        values = (
            df[column]
            .fillna("")
            .astype(str)
            .str.strip()
            .loc[lambda series: series != ""]
            .drop_duplicates()
            .tolist()
        )
        return sorted(values, key=lambda item: item.lower())

    return {
        "subject": unique_sorted("subject"),
        "instructor": unique_sorted("instructor"),
        "room": unique_sorted("room"),
        "group": unique_sorted("group"),
        "oddzial": unique_sorted("oddzial"),
        "type": unique_sorted("type"),
    }
