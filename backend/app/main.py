from __future__ import annotations

from datetime import date
from functools import lru_cache
import uuid

from fastapi import Depends, FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import Settings, get_settings
from .errors import DataSourceUnavailable
from .filters import ScheduleFilters, build_filters
from .models import DaySchedule, ErrorResponse, HealthResponse, MetaResponse, WeekSchedule
from .service import ScheduleService


@lru_cache
def get_service() -> ScheduleService:
    settings = get_settings()
    return ScheduleService(settings=settings)


def get_filters(
    subject: list[str] | None = Query(default=None),
    instructor: list[str] | None = Query(default=None),
    room: list[str] | None = Query(default=None),
    group: list[str] | None = Query(default=None),
    oddzial: list[str] | None = Query(default=None),
    type: list[str] | None = Query(default=None),
    only_magdalenka: bool = Query(default=False),
) -> ScheduleFilters:
    return build_filters(
        subject=subject,
        instructor=instructor,
        room=room,
        group=group,
        oddzial=oddzial,
        type=type,
        only_magdalenka=only_magdalenka,
    )


def create_app() -> FastAPI:
    settings: Settings = get_settings()
    app = FastAPI(
        title="Plan Zajec API",
        version="1.0.0",
        description="REST API for schedule data sourced from Excel files.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "OPTIONS"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):  # type: ignore[override]
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["x-request-id"] = request_id
        return response

    @app.exception_handler(DataSourceUnavailable)
    async def data_source_exception_handler(request: Request, exc: DataSourceUnavailable):
        payload = ErrorResponse(detail=str(exc), request_id=getattr(request.state, "request_id", None))
        return JSONResponse(status_code=503, content=payload.model_dump())

    @app.exception_handler(Exception)
    async def unexpected_exception_handler(request: Request, _exc: Exception):
        payload = ErrorResponse(
            detail="Wewnetrzny blad serwera.",
            request_id=getattr(request.state, "request_id", None),
        )
        return JSONResponse(status_code=500, content=payload.model_dump())

    @app.get("/")
    def root() -> dict[str, str]:
        return {"message": "Plan Zajec API", "docs": "/docs"}

    @app.get("/api/v1/health", response_model=HealthResponse)
    def health(service: ScheduleService = Depends(get_service)) -> HealthResponse:
        return service.health()

    @app.get("/api/v1/meta", response_model=MetaResponse)
    def meta(service: ScheduleService = Depends(get_service)) -> MetaResponse:
        return service.meta()

    @app.get("/api/v1/schedule/day", response_model=DaySchedule)
    def schedule_day(
        date_value: date = Query(alias="date"),
        filters: ScheduleFilters = Depends(get_filters),
        service: ScheduleService = Depends(get_service),
    ) -> DaySchedule:
        return service.get_day_schedule(day_date=date_value, filters=filters)

    @app.get("/api/v1/schedule/week", response_model=WeekSchedule)
    def schedule_week(
        anchor_date: date = Query(),
        filters: ScheduleFilters = Depends(get_filters),
        service: ScheduleService = Depends(get_service),
    ) -> WeekSchedule:
        return service.get_week_schedule(anchor_date=anchor_date, filters=filters)

    return app


app = create_app()
