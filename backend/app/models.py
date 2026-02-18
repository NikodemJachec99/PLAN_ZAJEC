from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class FilterOptions(BaseModel):
    subject: list[str] = Field(default_factory=list)
    instructor: list[str] = Field(default_factory=list)
    room: list[str] = Field(default_factory=list)
    group: list[str] = Field(default_factory=list)
    oddzial: list[str] = Field(default_factory=list)
    type: list[str] = Field(default_factory=list)


class MetaResponse(BaseModel):
    timezone: str
    min_date: date | None = None
    max_date: date | None = None
    filters: FilterOptions


class ScheduleEvent(BaseModel):
    id: str
    date: date
    start_time: str
    end_time: str
    start_min: int
    end_min: int
    subject: str
    instructor: str
    room: str
    group: str
    oddzial: str
    type: str
    source: str
    layout_col: int
    layout_cols_total: int
    color_hsl: str


class DaySchedule(BaseModel):
    date: date
    range_start_min: int
    range_end_min: int
    events: list[ScheduleEvent] = Field(default_factory=list)


class WeekSchedule(BaseModel):
    week_start: date
    week_end: date
    days: list[DaySchedule] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: str
    last_reload_at: datetime | None = None
    cache_ttl_seconds: int
    records: int


class ErrorResponse(BaseModel):
    detail: str
    request_id: str | None = None
