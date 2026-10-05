from __future__ import annotations

from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import shutil
import threading
from typing import Iterator

import pytest

from app.config import Settings

FIXTURES = Path(__file__).parent / "fixtures"
MAIN_III = FIXTURES / "PI_s_III_29_09_2026.xlsx"
PRACTICAL_III = FIXTURES / "PI_s_III_sem.zimowy_05.10.2026.xlsx"
MAIN_II = FIXTURES / "PI_s_II_23_03_2026.xlsx"
PRACTICAL_II = FIXTURES / "Pi_s_II_letni_19.03.2026.xlsx"


class FakeSite:
    """Tiny in-process web server standing in for wnoz.uni.opole.pl."""

    def __init__(self) -> None:
        self.routes: dict[str, tuple[int, bytes, dict[str, str]]] = {}
        self.requests: list[tuple[str, dict[str, str]]] = []
        site = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802 - http.server API
                path = self.path.split("?")[0]
                site.requests.append((path, {key.lower(): value for key, value in self.headers.items()}))
                status, body, headers = site.routes.get(path, (404, b"not found", {}))
                etag = headers.get("ETag")
                if etag and self.headers.get("If-None-Match") == etag:
                    self.send_response(304)
                    self.send_header("ETag", etag)
                    self.end_headers()
                    return
                self.send_response(status)
                for key, value in headers.items():
                    self.send_header(key, value)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args: object) -> None:
                return

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    @property
    def base(self) -> str:
        return f"http://127.0.0.1:{self.server.server_address[1]}"

    def page(self, *links: str, path: str = "/plan/") -> None:
        anchors = "".join(f'<p><a href="{link}">Plik {index}</a></p>' for index, link in enumerate(links))
        html = f"<html><body><h1>Plan</h1>{anchors}</body></html>".encode()
        self.routes[path] = (200, html, {"Content-Type": "text/html; charset=utf-8"})

    def file(self, path: str, content: bytes, etag: str | None = None) -> None:
        headers = {"Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}
        if etag:
            headers["ETag"] = etag
        self.routes[path] = (200, content, headers)

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture()
def site() -> Iterator[FakeSite]:
    fake = FakeSite()
    try:
        yield fake
    finally:
        fake.close()


@pytest.fixture()
def seed_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "seed"
    directory.mkdir()
    shutil.copy(MAIN_III, directory / MAIN_III.name)
    shutil.copy(PRACTICAL_III, directory / PRACTICAL_III.name)
    return directory


@pytest.fixture()
def make_settings(tmp_path: Path, seed_dir: Path):
    def factory(page_url: str = "http://127.0.0.1:9/plan/", **overrides: object) -> Settings:
        base = Settings(
            data_dir=tmp_path / "data",
            seed_dir=seed_dir,
            timezone="Europe/Warsaw",
            allowed_origins=["http://localhost:5173"],
            settings_password="tajne hasło",
            source_page_url=page_url,
            sync_enabled=False,
            sync_interval_seconds=300,
            min_forced_check_seconds=5,
            missing_grace_hours=12.0,
            http_timeout_seconds=5.0,
            max_file_bytes=5 * 1024 * 1024,
            cache_bust=True,
        )
        return replace(base, **overrides)  # type: ignore[arg-type]

    return factory
