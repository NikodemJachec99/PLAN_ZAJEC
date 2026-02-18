from datetime import time as dtime

import pandas as pd

from app.layout import assign_columns_and_clusters, compute_time_range


def test_assign_columns_and_clusters_for_overlap() -> None:
    events = [
        {"start_min": 8 * 60, "end_min": 10 * 60, "subject": "A"},
        {"start_min": 9 * 60, "end_min": 11 * 60, "subject": "B"},
        {"start_min": 11 * 60, "end_min": 12 * 60, "subject": "C"},
    ]

    positioned, cluster_cols = assign_columns_and_clusters(events)

    assert positioned[0]["col"] == 0
    assert positioned[1]["col"] == 1
    assert positioned[2]["col"] == 0
    assert cluster_cols[positioned[0]["cluster_id"]] == 2


def test_compute_time_range_compact() -> None:
    frame = pd.DataFrame(
        {
            "start_time_obj": [dtime(9, 10)],
            "end_time_obj": [dtime(12, 40)],
        }
    )

    start_min, end_min = compute_time_range(frame, compact=True)

    assert start_min == 8 * 60
    assert end_min == 13 * 60


def test_compute_time_range_empty() -> None:
    frame = pd.DataFrame({"start_time_obj": [], "end_time_obj": []})
    start_min, end_min = compute_time_range(frame, compact=True)
    assert start_min == 7 * 60
    assert end_min == 21 * 60
