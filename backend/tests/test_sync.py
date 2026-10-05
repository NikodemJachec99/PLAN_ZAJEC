from __future__ import annotations

from datetime import timedelta
import json

from app.sync import SyncService, extract_excel_links, utcnow

from .conftest import MAIN_II, MAIN_III, PRACTICAL_II, PRACTICAL_III, FakeSite

MAIN_PATH = "/wp-content/uploads/sites/89/PI_s_III_29_09_2026.xlsx"
PRACTICAL_PATH = "/wp-content/uploads/sites/89/PI_s_III_sem.zimowy_05.10.2026.xlsx"


def _publish_current(site: FakeSite) -> None:
    site.file(MAIN_PATH, MAIN_III.read_bytes(), etag='"m1"')
    site.file(PRACTICAL_PATH, PRACTICAL_III.read_bytes(), etag='"p1"')
    site.page(MAIN_PATH, PRACTICAL_PATH)


def _origins(service: SyncService) -> dict[str, str]:
    return {record.kind: record.origin for record in service.active}  # type: ignore[misc]


def test_link_extraction_handles_real_world_markup() -> None:
    html = """
    <div class="wp-block-file"><a href="/wp-content/uploads/sites/89/Plan%20III.xlsx?ver=2">Plan III</a>
    <a href="/wp-content/uploads/sites/89/Plan%20III.xlsx?ver=2" class="wp-block-file__button" download>Pobierz</a></div>
    <a href='https://view.officeapps.live.com/op/view.aspx?src=https%3A%2F%2Fwnoz.uni.opole.pl%2Fwp-content%2Fuploads%2Fpraktyki.xlsx'>podgląd</a>
    <a href="stary.xls">stary format</a>
    <a href="regulamin.pdf">PDF</a>
    <a href="relative/harmonogram.XLSX">bez zamknięcia
    <script>var f = {"url":"https:\\/\\/wnoz.uni.opole.pl\\/wp-content\\/uploads\\/z-skryptu.xlsx"};</script>
    """
    links = extract_excel_links(html, "https://wnoz.uni.opole.pl/plan-iii/")
    urls = [link.url for link in links]
    assert urls == [
        "https://wnoz.uni.opole.pl/wp-content/uploads/sites/89/Plan%20III.xlsx?ver=2",
        "https://wnoz.uni.opole.pl/wp-content/uploads/praktyki.xlsx",
        "https://wnoz.uni.opole.pl/plan-iii/stary.xls",
        "https://wnoz.uni.opole.pl/plan-iii/relative/harmonogram.XLSX",
        "https://wnoz.uni.opole.pl/wp-content/uploads/z-skryptu.xlsx",
    ]
    assert links[0].text == "Plan III"
    assert links[0].filename == "Plan III.xlsx"


def test_seed_is_used_until_first_sync_then_site_files_take_over(site: FakeSite, make_settings) -> None:
    service = SyncService(make_settings(site.base + "/plan/"))
    assert _origins(service) == {"main": "seed", "practical": "seed"}
    seed_version = service.snapshot.version

    _publish_current(site)
    service.check_now()
    assert _origins(service) == {"main": "site", "practical": "site"}
    assert service.status.last_error is None
    assert service.status.links_found == 2
    # Same bytes as the seed -> same plan version, nothing "changes" for users.
    assert service.snapshot.version == seed_version
    assert len(service.snapshot.payload["events"]) == 544
    # ...but the file descriptions served to the browser now point at the faculty site.
    served = service.snapshot.payload["sources"]
    assert {source["origin"] for source in served} == {"site"}
    assert all(source["url"].startswith(site.base) for source in served)


def test_new_file_on_page_updates_plan(site: FakeSite, make_settings) -> None:
    _publish_current(site)
    service = SyncService(make_settings(site.base + "/plan/"))
    service.check_now()
    before = service.snapshot.version

    # Faculty uploads a new practical schedule under a new name and swaps the link.
    site.file("/wp-content/uploads/sites/89/Pi_s_II_letni_19.03.2026.xlsx", PRACTICAL_II.read_bytes())
    site.page(MAIN_PATH, "/wp-content/uploads/sites/89/Pi_s_II_letni_19.03.2026.xlsx")
    assert service.check_now() is True
    assert service.snapshot.version != before
    names = sorted(source["name"] for source in service.snapshot.payload["sources"])
    assert names == ["PI_s_III_29_09_2026.xlsx", "Pi_s_II_letni_19.03.2026.xlsx"]
    assert service.status.last_changed_at is not None


def test_file_replaced_under_same_url_is_detected(site: FakeSite, make_settings) -> None:
    _publish_current(site)
    service = SyncService(make_settings(site.base + "/plan/"))
    service.check_now()
    before = service.snapshot.version

    site.file(MAIN_PATH, MAIN_II.read_bytes(), etag='"m2"')  # e.g. "Enable Media Replace"
    assert service.check_now() is True
    assert service.snapshot.version != before
    assert any(event["date"].startswith("2026-03") for event in service.snapshot.payload["events"])


def test_unchanged_files_use_conditional_requests(site: FakeSite, make_settings) -> None:
    _publish_current(site)
    service = SyncService(make_settings(site.base + "/plan/"))
    service.check_now()
    site.requests.clear()
    assert service.check_now() is False
    file_requests = [headers for path, headers in site.requests if path.endswith(".xlsx")]
    assert len(file_requests) == 2
    assert all(headers.get("if-none-match") for headers in file_requests)
    assert all(record.origin == "site" and not record.stale for record in service.active)


def test_broken_new_version_keeps_previous_good_file(site: FakeSite, make_settings) -> None:
    _publish_current(site)
    service = SyncService(make_settings(site.base + "/plan/"))
    service.check_now()
    before = service.snapshot.version

    site.file(MAIN_PATH, b"<html>Strona w budowie</html>", etag='"broken"')
    assert service.check_now() is False
    assert service.snapshot.version == before
    main = next(record for record in service.active if record.kind == "main")
    assert main.stale and "ostatniej pobranej" in (main.note or "")
    assert service.status.consecutive_failures == 0  # page itself worked

    corrupted_but_zip = b"PK\x03\x04 not really a workbook"
    site.file(MAIN_PATH, corrupted_but_zip, etag='"broken2"')
    service.check_now()
    assert service.snapshot.version == before
    assert "nie" in (service.status.last_error or "").lower()


def test_page_outage_keeps_plan(site: FakeSite, make_settings) -> None:
    _publish_current(site)
    service = SyncService(make_settings(site.base + "/plan/"))
    service.check_now()
    before = service.snapshot.version

    site.routes.pop("/plan/")
    assert service.check_now() is False
    assert service.snapshot.version == before
    assert service.status.consecutive_failures == 1
    assert "404" in (service.status.last_error or "")

    site.page()  # page without any Excel links (e.g. during an edit)
    service.check_now()
    assert service.snapshot.version == before
    assert service.status.consecutive_failures == 2

    _publish_current(site)
    service.check_now()
    assert service.status.consecutive_failures == 0
    assert service.status.last_error is None


def test_missing_kind_is_kept_for_grace_period_then_dropped(site: FakeSite, make_settings) -> None:
    _publish_current(site)
    service = SyncService(make_settings(site.base + "/plan/"))
    service.check_now()

    site.page(MAIN_PATH)  # practical schedule link disappears
    service.check_now()
    kinds = sorted(record.kind for record in service.active)  # type: ignore[type-var]
    assert kinds == ["main", "practical"]
    assert next(record for record in service.active if record.kind == "practical").stale

    service.missing_since["practical"] = (utcnow() - timedelta(hours=13)).isoformat()
    service._save_manifest()  # the state lives on disk (shared between workers)
    service.check_now()
    assert [record.kind for record in service.active] == ["main"]


def test_state_survives_restart(site: FakeSite, make_settings) -> None:
    _publish_current(site)
    settings = make_settings(site.base + "/plan/")
    first = SyncService(settings)
    first.check_now()
    manifest = json.loads((settings.data_dir / "sources" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"]["last_success_at"]

    site.close()  # site down after a restart
    second = SyncService(settings)
    assert second.snapshot.version == first.snapshot.version
    assert _origins(second) == {"main": "site", "practical": "site"}


def test_manual_upload_overrides_until_site_changes(site: FakeSite, make_settings) -> None:
    _publish_current(site)
    service = SyncService(make_settings(site.base + "/plan/"))
    service.check_now()

    service.upload_manual("Pi_s_II_letni_19.03.2026.xlsx", PRACTICAL_II.read_bytes())
    assert _origins(service)["practical"] == "manual"
    service.check_now()  # site unchanged -> manual file stays
    assert _origins(service)["practical"] == "manual"

    site.file("/wp-content/uploads/sites/89/nowy-main.xlsx", MAIN_II.read_bytes())
    site.page("/wp-content/uploads/sites/89/nowy-main.xlsx", PRACTICAL_PATH)
    service.check_now()  # only the other file changed -> manual practical file stays
    assert _origins(service) == {"main": "site", "practical": "manual"}

    site.file("/wp-content/uploads/sites/89/nowe-praktyki.xlsx", PRACTICAL_II.read_bytes())
    site.page("/wp-content/uploads/sites/89/nowy-main.xlsx", "/wp-content/uploads/sites/89/nowe-praktyki.xlsx")
    service.check_now()  # the faculty published a new practical schedule -> site wins
    assert _origins(service) == {"main": "site", "practical": "site"}
    assert service.manual == []


def test_request_check_is_rate_limited(make_settings) -> None:
    service = SyncService(make_settings())
    assert service.request_check() is True
    assert service.request_check() is False


def test_unrelated_spreadsheet_on_page_is_ignored(site: FakeSite, make_settings) -> None:
    from io import BytesIO

    import openpyxl

    workbook = openpyxl.Workbook()
    workbook.active["A1"] = "Lista obecności"
    workbook.active["A2"] = "Jan Kowalski"
    buffer = BytesIO()
    workbook.save(buffer)

    _publish_current(site)
    site.file("/wp-content/uploads/sites/89/lista.xlsx", buffer.getvalue())
    site.page(MAIN_PATH, PRACTICAL_PATH, "/wp-content/uploads/sites/89/lista.xlsx")
    service = SyncService(make_settings(site.base + "/plan/"))
    service.check_now()
    assert service.status.last_error is None
    assert service.status.links_found == 3
    assert sorted(record.kind for record in service.active) == ["main", "practical"]  # type: ignore[type-var]
