"""Turn a downloaded workbook into events, recognising its layout by content (not by name)."""

from __future__ import annotations

from datetime import date
from pathlib import Path
import zipfile

from ..model import KIND_MAIN, KIND_PRACTICAL, ParsedFile, PlanParseError, UnknownLayoutError
from ..xlsx import SheetGrid, load_grids
from .main_plan import looks_like_main_plan, parse_main_plan
from .practical import looks_like_practical, parse_practical

# Bump whenever parsing output changes, so cached datasets get rebuilt.
PARSER_VERSION = "2026.10.3"


def detect_kind(grids: list[SheetGrid]) -> str | None:
    visible = [grid for grid in grids if not grid.hidden] or grids
    # The row-based plan has an unmistakable header (data / od / do / przedmiot), so test it first.
    for grid in visible:
        if looks_like_main_plan(grid):
            return KIND_MAIN
    for grid in visible:
        if looks_like_practical(grid):
            return KIND_PRACTICAL
    return None


def guess_kind_from_name(name: str) -> str:
    lowered = name.lower()
    hints = ("prakty", "zimow", "letni", "grafik", "harmonogram", "zp_", "_zp")
    return KIND_PRACTICAL if any(hint in lowered for hint in hints) else KIND_MAIN


def parse_workbook(source: Path | bytes, *, reference: date | None = None) -> ParsedFile:
    if isinstance(source, Path):
        payload = source.read_bytes()
    else:
        payload = bytes(source)
    if not payload.startswith(b"PK"):
        raise PlanParseError("Plik nie jest arkuszem .xlsx (nieprawidłowa zawartość).")
    try:
        grids = load_grids(payload)
    except (zipfile.BadZipFile, KeyError, ValueError, OSError) as exc:
        raise PlanParseError(f"Nie udało się otworzyć arkusza: {exc}") from exc

    kind = detect_kind(grids)
    if kind == KIND_PRACTICAL:
        return parse_practical(grids, reference=reference)
    if kind == KIND_MAIN:
        return parse_main_plan(grids)
    raise UnknownLayoutError("Nie rozpoznano układu arkusza (ani plan zajęć, ani harmonogram praktyk).")


__all__ = ["PARSER_VERSION", "detect_kind", "guess_kind_from_name", "parse_workbook"]
