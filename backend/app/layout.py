from __future__ import annotations

from datetime import time as dtime
import heapq
import math
from typing import Any

import pandas as pd

from .utils import to_minutes

BASE_START_MIN = 7 * 60
BASE_END_MIN = 21 * 60
COMPACT_MARGIN_MIN = 15


def assign_columns_and_clusters(events: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[int, int]]:
    """Assign a display column for overlapping events and resolve cluster width."""
    if not events:
        return [], {}

    result: list[dict[str, Any]] = []
    active: list[tuple[int, int, int]] = []
    free_cols: list[int] = []
    next_col = 0
    clusters: list[list[tuple[int, int, int, int]]] = []
    current_cluster: list[tuple[int, int, int, int]] = []

    for idx, event in enumerate(events):
        while active and active[0][0] <= event["start_min"]:
            _, released_col, _ = heapq.heappop(active)
            free_cols.append(released_col)
            free_cols.sort()

        if not active and current_cluster:
            clusters.append(current_cluster)
            current_cluster = []

        col = free_cols.pop(0) if free_cols else next_col
        if col == next_col:
            next_col += 1

        heapq.heappush(active, (event["end_min"], col, idx))
        result.append({**event, "col": col, "cluster_id": -1})
        current_cluster.append((idx, event["start_min"], event["end_min"], col))

    if current_cluster:
        clusters.append(current_cluster)

    cluster_cols: dict[int, int] = {}
    for cluster_id, items in enumerate(clusters):
        points: list[tuple[int, int]] = []
        for _, start_min, end_min, _ in items:
            points.append((start_min, 1))
            points.append((end_min, -1))

        points.sort(key=lambda item: (item[0], -item[1]))
        current = peak = 0
        for _, delta in points:
            current += delta
            peak = max(peak, current)

        cluster_cols[cluster_id] = max(peak, 1)
        for idx, *_ in items:
            result[idx]["cluster_id"] = cluster_id

    return result, cluster_cols


def _valid_minutes(series: pd.Series) -> list[int]:
    values: list[int] = []
    for value in series.dropna():
        if isinstance(value, dtime):
            values.append(to_minutes(value))
    return values


def compute_time_range(day_df: pd.DataFrame, compact: bool = True) -> tuple[int, int]:
    if day_df.empty:
        return BASE_START_MIN, BASE_END_MIN

    start_values = _valid_minutes(day_df["start_time_obj"])
    end_values = _valid_minutes(day_df["end_time_obj"])

    if not start_values or not end_values:
        return BASE_START_MIN, BASE_END_MIN

    if compact:
        min_start = min(start_values)
        max_end = max(end_values)
        range_start = max(BASE_START_MIN, int(math.floor((min_start - COMPACT_MARGIN_MIN) / 60) * 60))
        range_end = min(BASE_END_MIN, int(math.ceil((max_end + COMPACT_MARGIN_MIN) / 60) * 60))
    else:
        range_start = min([BASE_START_MIN, *start_values])
        range_end = max([BASE_END_MIN, *end_values])

    if range_end - range_start < 60:
        range_end = range_start + 60

    return range_start, range_end
