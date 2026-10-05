"""Keeps the plan in sync with the faculty web page.

Every few minutes the page is fetched, all Excel links on it are downloaded (conditional
requests + sha256, so unchanged files cost nothing), each workbook is parsed and the set
of files that parsed correctly becomes the active plan. The switch is atomic and the
previous good data is never thrown away because of a failure:

* page unreachable / no Excel links found      -> keep the current plan, report the error
* a file fails to download or parse            -> keep its previous good version
* a kind of file (e.g. practical) disappears   -> keep the last version for a grace period
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from html import unescape
from html.parser import HTMLParser
import hashlib
import json
import logging
import os
from pathlib import Path
import random
import re
import threading
import time as time_module
from typing import Any
from urllib.parse import parse_qs, unquote, urljoin, urlparse, urlencode, urlunparse

import httpx

from .config import Settings
from .model import KIND_MAIN, KIND_PRACTICAL, ParsedFile, PlanParseError, UnknownLayoutError
from .parsers import PARSER_VERSION, guess_kind_from_name, parse_workbook
from .plan import SourceFile, build_plan, plan_version
from .textutil import date_from_filename

try:  # pragma: no cover - not available on Windows
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None  # type: ignore[assignment]

log = logging.getLogger("plan.sync")

EXCEL_EXT_RE = re.compile(r"\.(xlsx|xlsm)$", re.IGNORECASE)
LEGACY_EXCEL_RE = re.compile(r"\.xls$", re.IGNORECASE)
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/128.0 Safari/537.36 PlanZajec/2.0"
)
MANIFEST_SCHEMA = 2


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


# --------------------------------------------------------------------------- page links


@dataclass
class PageLink:
    url: str
    text: str = ""

    @property
    def filename(self) -> str:
        return unquote(Path(urlparse(self.url).path).name) or "plik.xlsx"


class _LinkCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self._open: list[list[Any]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = [value for name, value in attrs if value and name in {"href", "src", "data", "data-href", "data-url", "data-src", "data-file"}]
        if tag == "a":
            href = dict(attrs).get("href")
            self._open.append([href or "", []])
        for value in values:
            self.links.append((value, ""))

    def handle_data(self, data: str) -> None:
        for item in self._open:
            item[1].append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._open:
            href, text = self._open.pop()
            if href:
                self.links.append((href, " ".join("".join(text).split())))


def _unwrap_viewer(url: str) -> str:
    """Office Online / Google viewers wrap the real file URL in a query parameter."""
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    for key in ("src", "url", "file"):
        for candidate in query.get(key, []):
            if candidate.startswith(("http://", "https://")):
                return candidate
    return url


def extract_excel_links(html: str, base_url: str) -> list[PageLink]:
    collector = _LinkCollector()
    try:
        collector.feed(html)
        collector.close()
    except Exception:  # pragma: no cover - HTMLParser is lenient, but never let it kill a sync
        pass
    raw_links = list(collector.links)
    # Belt and braces: URLs that only appear in scripts/JSON blobs.
    for match in re.finditer(r"""https?:\\?/\\?/[^\s"'<>()]+?\.xlsx?m?(?:\?[^\s"'<>()]*)?(?=[\s"'<>()]|$)""", html, re.IGNORECASE):
        raw_links.append((match.group(0).replace("\\/", "/"), ""))

    found: dict[str, PageLink] = {}
    for href, text in raw_links:
        href = unescape(href).strip()
        if not href or href.startswith(("mailto:", "javascript:", "#")):
            continue
        absolute = _unwrap_viewer(urljoin(base_url, href))
        parsed = urlparse(absolute)
        if parsed.scheme not in {"http", "https"}:
            continue
        path = unquote(parsed.path)
        if not (EXCEL_EXT_RE.search(path) or LEGACY_EXCEL_RE.search(path)):
            continue
        key = urlunparse(parsed._replace(fragment=""))
        if key not in found:
            found[key] = PageLink(url=key, text=text)
        elif text and not found[key].text:
            found[key].text = text
    return list(found.values())


def _with_cache_buster(url: str) -> str:
    parsed = urlparse(url)
    query = parse_qs(parsed.query, keep_blank_values=True)
    query["_"] = [str(int(time_module.time() // 60))]
    return urlunparse(parsed._replace(query=urlencode(query, doseq=True)))


def _safe_name(name: str) -> str:
    cleaned = re.sub(r"[^\w.\-]+", "_", name, flags=re.UNICODE).strip("._") or "plik.xlsx"
    return cleaned[-120:]


# --------------------------------------------------------------------------- state


@dataclass
class FileRecord:
    """A concrete downloaded/seeded/uploaded file."""

    sha256: str
    path: str  # relative to the sources dir
    name: str
    origin: str  # site | seed | manual
    url: str = ""
    kind: str | None = None
    fetched_at: str | None = None
    last_modified: str | None = None
    etag: str | None = None
    error: str | None = None
    stale: bool = False
    note: str | None = None
    ignored: bool = False  # unrelated spreadsheet linked on the page

    def to_json(self) -> dict[str, Any]:
        return {key: value for key, value in self.__dict__.items()}

    @classmethod
    def from_json(cls, payload: dict[str, Any]) -> "FileRecord":
        allowed = cls.__dataclass_fields__.keys()  # type: ignore[attr-defined]
        return cls(**{key: value for key, value in payload.items() if key in allowed})


@dataclass
class SyncStatus:
    page_url: str
    interval_seconds: int
    last_checked_at: str | None = None
    last_success_at: str | None = None
    last_changed_at: str | None = None
    last_error: str | None = None
    last_error_at: str | None = None
    consecutive_failures: int = 0
    links_found: int = 0
    running: bool = False

    def to_json(self) -> dict[str, Any]:
        return dict(self.__dict__)


@dataclass
class Snapshot:
    version: str  # identifies the plan data (files + parser); changes => users get notified
    payload: dict[str, Any]
    body: bytes
    etag: str  # identifies the exact response body (also changes when only file metadata does)


class SyncService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.sources_dir = settings.data_dir / "sources"
        self.files_dir = self.sources_dir / "files"
        self.manifest_path = self.sources_dir / "manifest.json"
        self.files_dir.mkdir(parents=True, exist_ok=True)

        self._lock = threading.RLock()  # protects in-memory state
        self._run_lock = threading.Lock()  # one sync at a time in this process
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._thread: threading.Thread | None = None
        self._parse_cache: dict[str, ParsedFile | PlanParseError] = {}
        self._manifest_mtime: float | None = None
        self._last_forced = 0.0

        self.status = SyncStatus(page_url=settings.source_page_url, interval_seconds=settings.sync_interval_seconds)
        self.active: list[FileRecord] = []
        self.site: dict[str, FileRecord] = {}
        self.manual: list[dict[str, Any]] = []
        self.missing_since: dict[str, str] = {}
        self.snapshot: Snapshot | None = None

        self._load_manifest()
        if not self.active:
            self._bootstrap_from_seed()
        try:
            self._rebuild()
        except Exception:  # pragma: no cover - defensive: never fail to start
            log.exception("Could not build plan from saved files - falling back to seed files")
            with self._lock:
                self.active = []
            self._bootstrap_from_seed()
            self._rebuild()

    # ------------------------------------------------------------------ persistence

    def _load_manifest(self) -> None:
        try:
            mtime = self.manifest_path.stat().st_mtime  # taken before reading: a newer write gets re-read later
            payload = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return
        except (OSError, json.JSONDecodeError) as exc:
            log.error("Manifest unreadable (%s) - keeping current state", exc)
            return
        if payload.get("schema") != MANIFEST_SCHEMA:
            return
        with self._lock:
            self.active = [FileRecord.from_json(item) for item in payload.get("active", [])]
            self.active = [record for record in self.active if (self.sources_dir / record.path).exists()]
            self.site = {url: FileRecord.from_json(item) for url, item in payload.get("site", {}).items()}
            self.manual = [item for item in payload.get("manual", []) if (self.sources_dir / item.get("path", "")).exists()]
            self.missing_since = dict(payload.get("missing_since", {}))
            status = payload.get("status", {})
            for key in ("last_checked_at", "last_success_at", "last_changed_at", "last_error", "last_error_at", "consecutive_failures", "links_found"):
                if key in status:
                    setattr(self.status, key, status[key])
            self._manifest_mtime = mtime

    def _save_manifest(self) -> None:
        with self._lock:
            payload = {
                "schema": MANIFEST_SCHEMA,
                "page_url": self.settings.source_page_url,
                "active": [record.to_json() for record in self.active],
                "site": {url: record.to_json() for url, record in self.site.items()},
                "manual": self.manual,
                "missing_since": self.missing_since,
                "status": {key: value for key, value in self.status.to_json().items() if key != "running"},
            }
        tmp = self.manifest_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, self.manifest_path)
        self._manifest_mtime = self.manifest_path.stat().st_mtime
        self._prune_files(payload)

    def _prune_files(self, payload: dict[str, Any], keep_recent: int = 20) -> None:
        referenced = {item.get("path") for item in payload["active"]}
        referenced |= {item.get("path") for item in payload["site"].values()}
        referenced |= {item.get("path") for item in payload["manual"]}
        try:
            files = sorted(self.files_dir.glob("*"), key=lambda path: path.stat().st_mtime, reverse=True)
        except OSError:
            return
        for path in files[keep_recent:]:
            if f"files/{path.name}" not in referenced and not path.name.endswith(".tmp"):
                try:
                    path.unlink()
                except OSError:
                    pass

    def _store_bytes(self, content: bytes, name: str) -> tuple[str, str]:
        sha = hashlib.sha256(content).hexdigest()
        relative = f"files/{sha[:16]}__{_safe_name(name)}"
        target = self.sources_dir / relative
        if not target.exists():
            tmp = target.with_suffix(target.suffix + ".tmp")
            tmp.write_bytes(content)
            os.replace(tmp, target)
        return sha, relative

    def _bootstrap_from_seed(self) -> None:
        seed_dir = self.settings.seed_dir
        if not seed_dir.exists():
            return
        records: list[FileRecord] = []
        for path in sorted(seed_dir.glob("*.xls*")):
            if not EXCEL_EXT_RE.search(path.name):
                continue
            sha, relative = self._store_bytes(path.read_bytes(), path.name)
            record = FileRecord(sha256=sha, path=relative, name=path.name, origin="seed")
            parsed = self._parse(record)
            if isinstance(parsed, ParsedFile):
                record.kind = parsed.kind
                records.append(record)
            else:
                log.warning("Seed file %s skipped: %s", path.name, parsed)
        with self._lock:
            self.active = records
        if records:
            log.info("Loaded %d seed file(s) until the first successful sync", len(records))

    def reload_if_changed(self) -> None:
        """Pick up a manifest written by another worker process (no-op with a single worker)."""
        try:
            mtime = self.manifest_path.stat().st_mtime
        except OSError:
            return
        if self._manifest_mtime is not None and mtime == self._manifest_mtime:
            return
        if not self._run_lock.acquire(blocking=False):
            return  # a sync is running here; it will rebuild the plan itself
        try:
            self._load_manifest()
            self._rebuild()
        finally:
            self._run_lock.release()

    # ------------------------------------------------------------------ parsing / building

    def _parse(self, record: FileRecord) -> ParsedFile | PlanParseError:
        cached = self._parse_cache.get(record.sha256)
        if cached is not None:
            return cached
        reference = date_from_filename(record.name) or (parse_iso(record.fetched_at) or utcnow()).date()
        try:
            result: ParsedFile | PlanParseError = parse_workbook(self.sources_dir / record.path, reference=reference)
        except PlanParseError as exc:
            result = exc
        except Exception as exc:  # pragma: no cover - unexpected parser crash must not stop syncing
            log.exception("Parser crashed on %s", record.name)
            result = PlanParseError(f"Błąd odczytu pliku: {exc.__class__.__name__}: {exc}")
        if len(self._parse_cache) > 32:
            self._parse_cache.clear()
        self._parse_cache[record.sha256] = result
        return result

    def _source_files(self, records: list[FileRecord]) -> list[SourceFile]:
        sources: list[SourceFile] = []
        for record in records:
            parsed = self._parse(record)
            if not isinstance(parsed, ParsedFile):
                continue
            as_of = date_from_filename(record.name) or parsed.as_of
            if as_of is None and record.last_modified:
                try:
                    as_of = datetime.strptime(record.last_modified, "%a, %d %b %Y %H:%M:%S %Z").date()
                except ValueError:
                    as_of = None
            extra = [record.note] if record.note else []
            sources.append(
                SourceFile(
                    id=record.sha256[:12],
                    kind=parsed.kind,
                    name=record.name,
                    sha256=record.sha256,
                    parsed=parsed,
                    url=record.url,
                    origin=record.origin,
                    fetched_at=record.fetched_at,
                    last_modified=record.last_modified,
                    as_of=as_of,
                    stale=record.stale,
                    extra_warnings=extra,
                )
            )
        sources.sort(key=lambda source: (source.kind != KIND_MAIN, source.name))
        return sources

    def _rebuild(self) -> bool:
        """Rebuild the served plan from the active files. Returns True if the plan data changed."""
        with self._lock:
            records = list(self.active)
            previous = self.snapshot
        version = plan_version(PARSER_VERSION, [record.sha256 for record in records])
        sources = self._source_files(records)
        same = previous is not None and previous.version == version
        payload = build_plan(sources, version=version, generated_at=previous.payload["generated_at"] if same and previous else None)
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        etag = hashlib.sha256(body).hexdigest()[:24]
        with self._lock:
            self.snapshot = Snapshot(version=version, payload=payload, body=body, etag=etag)
        return not same

    # ------------------------------------------------------------------ network

    def _client(self) -> httpx.Client:
        return httpx.Client(
            follow_redirects=True,
            timeout=httpx.Timeout(self.settings.http_timeout_seconds, connect=15.0),
            headers={
                "User-Agent": USER_AGENT,
                "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.5",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
            },
        )

    def _get(self, client: httpx.Client, url: str, headers: dict[str, str] | None = None) -> httpx.Response:
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                response = client.get(url, headers=headers or {})
                if response.status_code >= 500 or response.status_code == 429:
                    raise httpx.HTTPStatusError(f"HTTP {response.status_code}", request=response.request, response=response)
                return response
            except (httpx.TransportError, httpx.HTTPStatusError) as exc:
                last_error = exc
                if self._stop.is_set():
                    break
                time_module.sleep(min(2 * (attempt + 1), 6))
        assert last_error is not None
        raise last_error

    def _fetch_page(self, client: httpx.Client) -> str:
        url = self.settings.source_page_url
        if self.settings.cache_bust:
            url = _with_cache_buster(url)
        response = self._get(client, url, headers={"Accept": "text/html,application/xhtml+xml"})
        if response.status_code != 200:
            raise RuntimeError(f"Strona planu odpowiedziała kodem HTTP {response.status_code}.")
        return response.text

    def _download(self, client: httpx.Client, link: PageLink, previous: FileRecord | None) -> FileRecord:
        now = iso(utcnow())
        headers = {"Accept": "*/*"}
        have_previous = previous is not None and not previous.error and (self.sources_dir / previous.path).exists()
        if have_previous and previous is not None:
            if previous.etag:
                headers["If-None-Match"] = previous.etag
            if previous.last_modified:
                headers["If-Modified-Since"] = previous.last_modified
        url = _with_cache_buster(link.url) if self.settings.cache_bust else link.url
        name = link.filename
        if LEGACY_EXCEL_RE.search(name):
            return FileRecord(sha256="", path="", name=name, origin="site", url=link.url, fetched_at=now,
                              error="Format .xls (Excel 97-2003) nie jest obsługiwany – potrzebny .xlsx.")
        try:
            response = self._get(client, url, headers=headers)
        except Exception as exc:
            if have_previous and previous is not None:
                return FileRecord(**{**previous.__dict__, "stale": True, "note": f"Nie udało się pobrać nowej wersji ({exc}) – używamy ostatniej pobranej."})
            return FileRecord(sha256="", path="", name=name, origin="site", url=link.url, fetched_at=now, error=f"Pobieranie nie powiodło się: {exc}")

        if response.status_code == 304 and have_previous and previous is not None:
            return FileRecord(**{**previous.__dict__, "fetched_at": now, "stale": False, "note": None})
        if response.status_code != 200:
            error = f"Plik odpowiedział kodem HTTP {response.status_code}."
            if have_previous and previous is not None:
                return FileRecord(**{**previous.__dict__, "stale": True, "note": error + " Używamy ostatniej pobranej wersji."})
            return FileRecord(sha256="", path="", name=name, origin="site", url=link.url, fetched_at=now, error=error)

        content = response.content
        problem = None
        if len(content) > self.settings.max_file_bytes:
            problem = "Plik jest zbyt duży."
        elif not content.startswith(b"PK"):
            problem = "Serwer zwrócił coś innego niż plik .xlsx (np. stronę błędu)."
        if problem:
            if have_previous and previous is not None:
                return FileRecord(**{**previous.__dict__, "stale": True, "note": problem + " Używamy ostatniej pobranej wersji."})
            return FileRecord(sha256="", path="", name=name, origin="site", url=link.url, fetched_at=now, error=problem)
        disposition = response.headers.get("content-disposition", "")
        match = re.search(r"filename\*?=(?:UTF-8'')?\"?([^\";]+)", disposition)
        if match:
            name = unquote(match.group(1))
        sha, relative = self._store_bytes(content, name)
        return FileRecord(
            sha256=sha,
            path=relative,
            name=name,
            origin="site",
            url=link.url,
            fetched_at=now,
            etag=response.headers.get("etag"),
            last_modified=response.headers.get("last-modified"),
        )

    # ------------------------------------------------------------------ decision logic

    def _decide_active(self, site_records: list[FileRecord], now: datetime) -> tuple[list[FileRecord], list[str]]:
        problems: list[str] = []
        previous_active = list(self.active)
        chosen: list[FileRecord] = []
        failed: list[FileRecord] = []

        for record in site_records:
            if not record.error:
                parsed = self._parse(record)
                if isinstance(parsed, ParsedFile):
                    record.kind = parsed.kind
                    chosen.append(record)
                    continue
                record.error = str(parsed)
                known_url = any(old.url == record.url for old in previous_active)
                if isinstance(parsed, UnknownLayoutError) and not known_url:
                    record.ignored = True  # e.g. an unrelated spreadsheet linked on the same page
                    log.info("Ignoring %s: %s", record.name, parsed)
                    continue
            failed.append(record)

        good_kinds = {record.kind for record in chosen}
        for record in failed:
            problems.append(f"{record.name}: {record.error}")
            fallback = next((old for old in previous_active if old.url and old.url == record.url and old.sha256 != record.sha256), None)
            if fallback is None:
                kind = guess_kind_from_name(record.name)
                candidates = [old for old in previous_active if old.kind == kind]
                if kind not in good_kinds and len(candidates) == 1:
                    fallback = candidates[0]
            if fallback is not None and fallback.sha256 not in {item.sha256 for item in chosen}:
                chosen.append(
                    FileRecord(**{**fallback.__dict__, "stale": True, "note": f"Nowej wersji pliku {record.name} nie udało się odczytać ({record.error}). Pokazujemy poprzednią wersję."})
                )

        # Manual uploads override the site's file of the same kind until the site changes it.
        site_shas_by_kind: dict[str, list[str]] = {}
        for record in site_records:
            if record.kind and not record.error:
                site_shas_by_kind.setdefault(record.kind, []).append(record.sha256)
        kept_manual: list[dict[str, Any]] = []
        for override in self.manual:
            kind = override["kind"]
            if sorted(site_shas_by_kind.get(kind, [])) != sorted(override.get("site_shas", [])):
                continue  # the faculty published something new -> the site wins again
            kept_manual.append(override)
            chosen = [record for record in chosen if record.kind != kind]
            chosen.append(
                FileRecord(sha256=override["sha256"], path=override["path"], name=override["name"], origin="manual",
                           kind=kind, fetched_at=override.get("uploaded_at"),
                           note="Plik wgrany ręcznie – zostanie zastąpiony, gdy uczelnia opublikuje nowy plik.")
            )
        self.manual = kept_manual

        # Deduplicate (the same file linked twice).
        unique: dict[str, FileRecord] = {}
        for record in chosen:
            unique.setdefault(record.sha256, record)
        chosen = list(unique.values())

        present = {record.kind for record in chosen}
        grace = timedelta(hours=self.settings.missing_grace_hours)
        for kind in {record.kind for record in previous_active if record.kind}:
            if kind in present:
                self.missing_since.pop(kind, None)
                continue
            since = parse_iso(self.missing_since.get(kind)) or now
            self.missing_since[kind] = iso(since) or ""
            if now - since < grace:
                for old in previous_active:
                    if old.kind == kind:
                        chosen.append(FileRecord(**{**old.__dict__, "stale": True, "note": "Pliku nie ma obecnie na stronie uczelni – pokazujemy ostatnią wersję."}))
                problems.append(f"Na stronie brak pliku typu „{'zajęcia praktyczne' if kind == KIND_PRACTICAL else 'plan zajęć'}”.")
        for kind in list(self.missing_since):
            if kind in present:
                self.missing_since.pop(kind, None)
        return chosen, problems

    # ------------------------------------------------------------------ public API

    def check_now(self, *, wait: bool = True) -> bool:
        """Run one sync. Returns True if the plan changed."""
        if not self._run_lock.acquire(blocking=wait):
            return False
        lock_file = None
        try:
            if fcntl is not None:
                lock_file = open(self.sources_dir / ".sync.lock", "w")
                try:
                    fcntl.flock(lock_file, fcntl.LOCK_EX | (0 if wait else fcntl.LOCK_NB))
                except BlockingIOError:
                    return False
                self._load_manifest()  # another process may have synced meanwhile
            self.status.running = True
            return self._check()
        finally:
            self.status.running = False
            if lock_file is not None:
                lock_file.close()
            self._run_lock.release()

    def _record_failure(self, message: str, now: datetime) -> None:
        log.warning("Sync problem: %s", message)
        self.status.last_error = message
        self.status.last_error_at = iso(now)
        self.status.consecutive_failures += 1

    def _check(self) -> bool:
        now = utcnow()
        self.status.last_checked_at = iso(now)
        try:
            with self._client() as client:
                html = self._fetch_page(client)
                links = extract_excel_links(html, self.settings.source_page_url)
                self.status.links_found = len(links)
                if not links:
                    raise RuntimeError("Na stronie planu nie znaleziono żadnych plików Excel – pokazujemy ostatnią wersję planu.")
                site_records = [self._download(client, link, self.site.get(link.url)) for link in links]
        except RuntimeError as exc:
            self._record_failure(str(exc), now)
            self._save_manifest()
            return False
        except Exception as exc:
            self._record_failure(f"Nie udało się połączyć ze stroną uczelni ({exc or exc.__class__.__name__}).", now)
            self._save_manifest()
            return False

        with self._lock:
            previous_active = list(self.active)
            chosen, problems = self._decide_active(site_records, now)
            self.site = {record.url: record for record in site_records if record.url}
            if chosen:
                self.active = chosen
        if not chosen:
            self._record_failure("Żaden plik ze strony nie dał się odczytać – pokazujemy ostatnią wersję planu.", now)
            self._save_manifest()
            return False

        try:
            changed = self._rebuild()
        except Exception as exc:  # pragma: no cover - defensive
            log.exception("Building the plan failed")
            with self._lock:
                self.active = previous_active
            self._record_failure(f"Nie udało się zbudować planu z nowych plików ({exc}) – pokazujemy poprzednią wersję.", now)
            self._save_manifest()
            return False
        self.status.last_success_at = iso(now)
        if changed:
            self.status.last_changed_at = iso(now)
            log.info("Plan updated to version %s", self.snapshot.version if self.snapshot else "?")
        if problems:
            self.status.last_error = " ".join(problems)
            self.status.last_error_at = iso(now)
        else:
            self.status.last_error = None
        self.status.consecutive_failures = 0
        self._save_manifest()
        return changed

    def request_check(self) -> bool:
        """Ask the background loop to check right away (rate limited). Returns False if throttled."""
        now = time_module.monotonic()
        if now - self._last_forced < self.settings.min_forced_check_seconds:
            return False
        self._last_forced = now
        self._wake.set()
        return True

    def upload_manual(self, filename: str, content: bytes) -> FileRecord:
        if not content:
            raise ValueError("Plik jest pusty.")
        if len(content) > self.settings.max_file_bytes:
            raise ValueError("Plik jest zbyt duży.")
        if not EXCEL_EXT_RE.search(filename or ""):
            raise ValueError("Dozwolone są tylko pliki .xlsx.")
        sha, relative = self._store_bytes(content, filename)
        record = FileRecord(sha256=sha, path=relative, name=Path(filename).name, origin="manual", fetched_at=iso(utcnow()))
        parsed = self._parse(record)
        if not isinstance(parsed, ParsedFile):
            raise ValueError(str(parsed))
        with self._run_lock, self._lock:
            kind = parsed.kind
            site_shas = sorted(r.sha256 for r in self.site.values() if r.kind == kind and not r.error)
            self.manual = [item for item in self.manual if item["kind"] != kind]
            self.manual.append({"kind": kind, "sha256": sha, "path": relative, "name": record.name, "uploaded_at": record.fetched_at, "site_shas": site_shas})
            record.kind = kind
            record.note = "Plik wgrany ręcznie – zostanie zastąpiony, gdy uczelnia opublikuje nowy plik."
            self.active = [item for item in self.active if item.kind != kind] + [record]
        if self._rebuild():
            self.status.last_changed_at = iso(utcnow())
        self._save_manifest()
        return record

    def clear_manual(self) -> None:
        with self._run_lock, self._lock:
            self.manual = []
            self._reapply_site()
        self._rebuild()
        self._save_manifest()

    def _reapply_site(self) -> None:
        site = [FileRecord(**{**record.__dict__}) for record in self.site.values() if not record.error and not record.ignored]
        if site:
            chosen, _ = self._decide_active(site, utcnow())
            if chosen:
                self.active = chosen
        else:
            self.active = [record for record in self.active if record.origin != "manual"]
            if not self.active:
                self._bootstrap_from_seed()

    def status_payload(self) -> dict[str, Any]:
        with self._lock:
            snapshot = self.snapshot
            stale_after = timedelta(seconds=max(3 * self.settings.sync_interval_seconds, 1800))
            last_success = parse_iso(self.status.last_success_at)
            return {
                "version": snapshot.version if snapshot else None,
                "now": iso(utcnow()),
                "sync": {
                    **self.status.to_json(),
                    "healthy": bool(last_success and utcnow() - last_success < stale_after),
                },
                "sources": snapshot.payload["sources"] if snapshot else [],
            }

    # ------------------------------------------------------------------ background loop

    def start(self) -> None:
        if self._thread is not None or not self.settings.sync_enabled:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="plan-sync", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()
        if self._thread is not None:
            self._thread.join(timeout=10)
            self._thread = None

    def _loop(self) -> None:
        delay = 0.0
        while not self._stop.is_set():
            self._wake.wait(timeout=delay)
            self._wake.clear()
            if self._stop.is_set():
                break
            try:
                self.check_now(wait=False)
            except Exception:  # pragma: no cover - the loop must survive anything
                log.exception("Unexpected error during sync")
            interval = self.settings.sync_interval_seconds
            if self.status.consecutive_failures:
                interval = min(interval, 120)  # retry sooner while the site is failing
            delay = interval * random.uniform(0.9, 1.1)
