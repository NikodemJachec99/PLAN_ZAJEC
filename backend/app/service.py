from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import hashlib
from pathlib import Path
import threading
from typing import Any, Literal

import pandas as pd

from .config import Settings
from .data_loader import load_combined_data
from .errors import DataSourceUnavailable
from .filters import ScheduleFilters, apply_filters_with_magdalenka, extract_filter_values
from .layout import assign_columns_and_clusters, compute_time_range
from .models import (
    DaySchedule,
    FilterOptions,
    HealthResponse,
    MetaResponse,
    RuntimeSettingsResponse,
    ScheduleEvent,
    WeekSchedule,
)
from .runtime_settings import RuntimeSettingsData, RuntimeSettingsStore, sanitize_excel_filename
from .utils import normalize_text, subject_color_hsl, to_minutes


class ScheduleService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._lock = threading.Lock()

        self._frame: pd.DataFrame | None = None
        self._last_reload_at: datetime | None = None
        self._fingerprint: str | None = None

        self._settings.data_dir.mkdir(parents=True, exist_ok=True)
        self._runtime_store = RuntimeSettingsStore(
            data_dir=self._settings.data_dir,
            settings_file=self._settings.runtime_settings_file,
        )
        self._runtime_data = self._runtime_store.load()

    @property
    def settings(self) -> Settings:
        return self._settings

    def _tracked_files(self) -> list[Path]:
        files = [
            self._settings.runtime_settings_file,
            self._settings.data_dir / self._runtime_data.main_file,
            self._settings.data_dir / self._runtime_data.practical_file,
        ]
        return files

    def _build_fingerprint(self) -> str:
        chunks: list[str] = []
        for path in self._tracked_files():
            if path.exists():
                stat = path.stat()
                chunks.append(f"{path.name}:{stat.st_size}:{stat.st_mtime_ns}")
            else:
                chunks.append(f"{path.name}:missing")
        return "|".join(chunks)

    def _cache_expired(self, now: datetime) -> bool:
        if self._last_reload_at is None:
            return True
        return (now - self._last_reload_at).total_seconds() >= self._settings.cache_ttl_seconds

    def _needs_reload(self, now: datetime) -> bool:
        if self._frame is None:
            return True
        if self._cache_expired(now):
            return True
        return self._build_fingerprint() != self._fingerprint

    def _assert_runtime_files(self, runtime_data: RuntimeSettingsData) -> None:
        main_path = self._settings.data_dir / runtime_data.main_file
        practical_path = self._settings.data_dir / runtime_data.practical_file
        if not main_path.exists():
            raise DataSourceUnavailable(f"Plik glownego planu nie istnieje: {runtime_data.main_file}")
        if not practical_path.exists():
            raise DataSourceUnavailable(f"Plik praktyk nie istnieje: {runtime_data.practical_file}")

    def _invalidate_cache_locked(self) -> None:
        self._frame = None
        self._last_reload_at = None
        self._fingerprint = None

    def _reload_locked(self) -> None:
        runtime_data = self._runtime_store.load()
        self._assert_runtime_files(runtime_data)

        frame = load_combined_data(
            self._settings.data_dir,
            main_file_name=runtime_data.main_file,
            practical_file_name=runtime_data.practical_file,
        )
        self._runtime_data = runtime_data
        self._frame = frame
        self._last_reload_at = datetime.now(timezone.utc)
        self._fingerprint = self._build_fingerprint()

    def _ensure_loaded(self) -> pd.DataFrame:
        now = datetime.now(timezone.utc)
        if not self._needs_reload(now):
            return self._frame if self._frame is not None else pd.DataFrame()

        with self._lock:
            if self._needs_reload(now):
                self._reload_locked()

        return self._frame if self._frame is not None else pd.DataFrame()

    def _runtime_response(self) -> RuntimeSettingsResponse:
        runtime_data = self._runtime_store.load()
        self._runtime_data = runtime_data
        return RuntimeSettingsResponse(
            main_file=runtime_data.main_file,
            practical_file=runtime_data.practical_file,
            magdalenka_exact_groups=list(runtime_data.magdalenka_exact_groups),
            magdalenka_prefixes=list(runtime_data.magdalenka_prefixes),
        )

    def get_runtime_settings(self) -> RuntimeSettingsResponse:
        return self._runtime_response()

    def update_runtime_settings(
        self,
        *,
        main_file: str | None = None,
        practical_file: str | None = None,
        magdalenka_exact_groups: list[str] | None = None,
        magdalenka_prefixes: list[str] | None = None,
    ) -> RuntimeSettingsResponse:
        next_data = self._runtime_store.compose(
            main_file=main_file,
            practical_file=practical_file,
            magdalenka_exact_groups=magdalenka_exact_groups,
            magdalenka_prefixes=magdalenka_prefixes,
        )
        try:
            self._assert_runtime_files(next_data)
        except DataSourceUnavailable as exc:
            raise ValueError(str(exc)) from exc
        self._runtime_store.save(next_data)

        with self._lock:
            self._runtime_data = next_data
            self._invalidate_cache_locked()
            self._reload_locked()
        return self._runtime_response()

    def upload_runtime_file(
        self,
        *,
        kind: Literal["main", "practical"],
        filename: str,
        content: bytes,
    ) -> RuntimeSettingsResponse:
        safe_name = sanitize_excel_filename(filename)
        if not content:
            raise ValueError("Plik jest pusty.")

        target = self._settings.data_dir / safe_name
        target.write_bytes(content)

        if kind == "main":
            updated = self._runtime_store.update(main_file=safe_name)
        else:
            updated = self._runtime_store.update(practical_file=safe_name)

        with self._lock:
            self._runtime_data = updated
            self._invalidate_cache_locked()
            self._reload_locked()
        return self._runtime_response()

    def health(self) -> HealthResponse:
        frame = self._ensure_loaded()
        return HealthResponse(
            status="ok",
            last_reload_at=self._last_reload_at,
            cache_ttl_seconds=self._settings.cache_ttl_seconds,
            records=len(frame),
        )

    def meta(self) -> MetaResponse:
        frame = self._ensure_loaded()
        filters = extract_filter_values(frame)

        min_date = None
        max_date = None
        if not frame.empty and "date" in frame.columns:
            min_dt = frame["date"].min()
            max_dt = frame["date"].max()
            if pd.notna(min_dt):
                min_date = min_dt.date()
            if pd.notna(max_dt):
                max_date = max_dt.date()

        return MetaResponse(
            timezone=self._settings.timezone,
            min_date=min_date,
            max_date=max_date,
            filters=FilterOptions(**filters),
        )

    def _filtered_frame(self, filters: ScheduleFilters) -> pd.DataFrame:
        frame = self._ensure_loaded()
        if frame.empty:
            return frame
        return apply_filters_with_magdalenka(
            frame,
            filters,
            magdalenka_exact_groups=self._runtime_data.magdalenka_exact_groups,
            magdalenka_prefixes=self._runtime_data.magdalenka_prefixes,
        )

    @staticmethod
    def _event_id(payload: str) -> str:
        return hashlib.md5(payload.encode("utf-8")).hexdigest()[:16]

    def _serialize_day(self, day_date: date, filtered_df: pd.DataFrame) -> DaySchedule:
        if filtered_df.empty:
            return DaySchedule(date=day_date, range_start_min=7 * 60, range_end_min=21 * 60, events=[])

        day_df = filtered_df[filtered_df["date"].dt.date == day_date]
        range_start_min, range_end_min = compute_time_range(day_df, compact=True)
        if day_df.empty:
            return DaySchedule(
                date=day_date,
                range_start_min=range_start_min,
                range_end_min=range_end_min,
                events=[],
            )

        raw_events: list[dict[str, Any]] = []
        for row in day_df.to_dict("records"):
            start_obj = row.get("start_time_obj")
            end_obj = row.get("end_time_obj")
            if pd.isna(start_obj) or pd.isna(end_obj):
                continue

            start_min = to_minutes(start_obj)
            end_min = to_minutes(end_obj)
            if end_min <= start_min:
                continue

            raw_events.append(
                {
                    "start_min": start_min,
                    "end_min": end_min,
                    "subject": normalize_text(row.get("subject")),
                    "instructor": normalize_text(row.get("instructor")),
                    "room": normalize_text(row.get("room")),
                    "group": normalize_text(row.get("group")),
                    "oddzial": normalize_text(row.get("oddzial")),
                    "type": normalize_text(row.get("type")),
                    "source": normalize_text(row.get("source")),
                    "start_time": normalize_text(row.get("start_time")),
                    "end_time": normalize_text(row.get("end_time")),
                }
            )

        raw_events.sort(key=lambda item: (item["start_min"], item["end_min"]))
        positioned_events, cluster_cols = assign_columns_and_clusters(raw_events)

        serialized_events: list[ScheduleEvent] = []
        for event in positioned_events:
            start_time = event["start_time"] or f"{event['start_min'] // 60:02d}:{event['start_min'] % 60:02d}"
            end_time = event["end_time"] or f"{event['end_min'] // 60:02d}:{event['end_min'] % 60:02d}"
            event_identity = "|".join(
                [
                    day_date.isoformat(),
                    start_time,
                    end_time,
                    event["subject"],
                    event["room"],
                    event["group"],
                    event["source"],
                    event["instructor"],
                ]
            )

            serialized_events.append(
                ScheduleEvent(
                    id=self._event_id(event_identity),
                    date=day_date,
                    start_time=start_time,
                    end_time=end_time,
                    start_min=event["start_min"],
                    end_min=event["end_min"],
                    subject=event["subject"],
                    instructor=event["instructor"],
                    room=event["room"],
                    group=event["group"],
                    oddzial=event["oddzial"],
                    type=event["type"],
                    source=event["source"],
                    layout_col=event["col"],
                    layout_cols_total=max(1, cluster_cols.get(event["cluster_id"], 1)),
                    color_hsl=subject_color_hsl(event["subject"]),
                )
            )

        return DaySchedule(
            date=day_date,
            range_start_min=range_start_min,
            range_end_min=range_end_min,
            events=serialized_events,
        )

    def get_day_schedule(self, day_date: date, filters: ScheduleFilters) -> DaySchedule:
        filtered_df = self._filtered_frame(filters)
        return self._serialize_day(day_date=day_date, filtered_df=filtered_df)

    def get_week_schedule(self, anchor_date: date, filters: ScheduleFilters) -> WeekSchedule:
        filtered_df = self._filtered_frame(filters)
        week_start = anchor_date - timedelta(days=anchor_date.weekday())
        week_end = week_start + timedelta(days=6)

        days: list[DaySchedule] = []
        for offset in range(7):
            day_date = week_start + timedelta(days=offset)
            days.append(self._serialize_day(day_date=day_date, filtered_df=filtered_df))

        return WeekSchedule(week_start=week_start, week_end=week_end, days=days)
