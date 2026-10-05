from __future__ import annotations

from contextlib import asynccontextmanager
from functools import lru_cache
import hmac
import logging
from typing import Any
from urllib.parse import unquote
import uuid

from fastapi import Depends, FastAPI, File, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, Response
from starlette.concurrency import run_in_threadpool

from .calendar import build_ics, resolve_selection
from .config import get_settings
from .sync import SyncService

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("plan.api")


@lru_cache
def get_service() -> SyncService:
    return SyncService(get_settings())


def require_password(x_settings_password: str | None = Header(default=None)) -> None:
    expected = get_settings().settings_password
    if not expected:
        raise HTTPException(status_code=403, detail="Ręczne zmiany są wyłączone (brak SETTINGS_PASSWORD na serwerze).")
    provided = unquote(x_settings_password or "")
    if not hmac.compare_digest(provided.encode("utf-8"), expected.encode("utf-8")):
        raise HTTPException(status_code=401, detail="Nieprawidłowe hasło.")


@asynccontextmanager
async def lifespan(_: FastAPI):
    service = get_service()
    service.start()
    try:
        yield
    finally:
        service.stop()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Plan Zajęć API",
        version="2.0.0",
        description="Plan zajęć budowany automatycznie z plików publikowanych na stronie WNoZ UO.",
        lifespan=lifespan,
    )
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["ETag"],
    )

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["x-request-id"] = request_id
        return response

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):  # type: ignore[no-untyped-def]
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": str(exc.detail), "request_id": getattr(request.state, "request_id", None)},
        )

    @app.exception_handler(Exception)
    async def unexpected_exception_handler(request: Request, exc: Exception):  # type: ignore[no-untyped-def]
        log.exception("Unhandled error", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content={"detail": "Wewnętrzny błąd serwera.", "request_id": getattr(request.state, "request_id", None)},
        )

    @app.get("/")
    def root() -> dict[str, str]:
        return {"message": "Plan Zajęć API", "docs": "/docs"}

    @app.get("/api/v1/health")
    def health(service: SyncService = Depends(get_service)) -> dict[str, Any]:
        snapshot = service.snapshot
        return {
            "status": "ok",
            "version": snapshot.version if snapshot else None,
            "events": len(snapshot.payload["events"]) if snapshot else 0,
            "last_success_at": service.status.last_success_at,
        }

    @app.get("/api/v1/plan")
    def plan(request: Request, service: SyncService = Depends(get_service)) -> Response:
        service.reload_if_changed()
        snapshot = service.snapshot
        if snapshot is None:
            raise HTTPException(status_code=503, detail="Plan nie jest jeszcze dostępny.")
        etag = f'"{snapshot.etag}"'
        headers = {"ETag": etag, "Cache-Control": "no-cache"}
        if etag in [tag.strip().removeprefix("W/") for tag in request.headers.get("if-none-match", "").split(",")]:
            return Response(status_code=304, headers=headers)
        return Response(content=snapshot.body, media_type="application/json", headers=headers)

    @app.get("/api/v1/status")
    def status(service: SyncService = Depends(get_service)) -> JSONResponse:
        service.reload_if_changed()
        return JSONResponse(service.status_payload(), headers={"Cache-Control": "no-store"})

    @app.post("/api/v1/sync", status_code=202)
    def sync_now(service: SyncService = Depends(get_service)) -> JSONResponse:
        accepted = service.request_check()
        return JSONResponse({"accepted": accepted, **service.status_payload()}, status_code=202)

    @app.get("/api/v1/calendar.ics")
    def calendar(request: Request, download: bool = False, service: SyncService = Depends(get_service)) -> Response:
        service.reload_if_changed()
        snapshot = service.snapshot
        if snapshot is None:
            raise HTTPException(status_code=503, detail="Plan nie jest jeszcze dostępny.")
        selection = resolve_selection(snapshot.payload, dict(request.query_params))
        body = build_ics(snapshot.payload, selection)
        filename = "plan-zajec-" + "-".join(selection.values()).replace(" ", "_") + ".ics"
        headers = {"Cache-Control": "no-cache"}
        if download:
            headers["Content-Disposition"] = f'attachment; filename="{filename}"'
        return Response(content=body, media_type="text/calendar; charset=utf-8", headers=headers)

    @app.post("/api/v1/admin/upload", dependencies=[Depends(require_password)])
    async def admin_upload(file: UploadFile = File(...), service: SyncService = Depends(get_service)) -> dict[str, Any]:
        content = await file.read()
        try:
            record = await run_in_threadpool(service.upload_manual, file.filename or "", content)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {"uploaded": record.name, "kind": record.kind, **service.status_payload()}

    @app.delete("/api/v1/admin/manual", dependencies=[Depends(require_password)])
    def admin_clear_manual(service: SyncService = Depends(get_service)) -> dict[str, Any]:
        service.clear_manual()
        return service.status_payload()

    return app


app = create_app()
