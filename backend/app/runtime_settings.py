from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import re
import threading
from typing import Any

DEFAULT_MAIN_CANDIDATES = (
    "PI_s_II_3_03_2026.xlsx",
    "plan_zajec.xlsx",
)
DEFAULT_PRACTICAL_CANDIDATES = (
    "Pi_s_II_letni_27.02.2026.xlsx",
    "praktyki_tidy (1).xlsx",
    "praktyki_tidy.xlsx",
)

DEFAULT_MAGDALENKA_EXACT_GROUPS = (
    "---",
    "rok",
    "cały rok",
    "caly rok",
    "wszyscy",
    "all",
    "year",
    "d",
)
DEFAULT_MAGDALENKA_PREFIXES = (
    "11",
    "wsz",
)


def _normalize_text_list(values: list[str] | tuple[str, ...]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = str(value).strip().lower()
        if not normalized or normalized in seen:
            continue
        cleaned.append(normalized)
        seen.add(normalized)
    return cleaned


def _pick_existing(data_dir: Path, candidates: tuple[str, ...]) -> str:
    for candidate in candidates:
        if (data_dir / candidate).exists():
            return candidate
    return candidates[0]


@dataclass(frozen=True)
class RuntimeSettingsData:
    main_file: str
    practical_file: str
    magdalenka_exact_groups: tuple[str, ...]
    magdalenka_prefixes: tuple[str, ...]

    def to_payload(self) -> dict[str, Any]:
        return {
            "main_file": self.main_file,
            "practical_file": self.practical_file,
            "magdalenka_exact_groups": list(self.magdalenka_exact_groups),
            "magdalenka_prefixes": list(self.magdalenka_prefixes),
        }


def default_runtime_settings(data_dir: Path) -> RuntimeSettingsData:
    return RuntimeSettingsData(
        main_file=_pick_existing(data_dir, DEFAULT_MAIN_CANDIDATES),
        practical_file=_pick_existing(data_dir, DEFAULT_PRACTICAL_CANDIDATES),
        magdalenka_exact_groups=tuple(_normalize_text_list(list(DEFAULT_MAGDALENKA_EXACT_GROUPS))),
        magdalenka_prefixes=tuple(_normalize_text_list(list(DEFAULT_MAGDALENKA_PREFIXES))),
    )


def sanitize_excel_filename(filename: str) -> str:
    base = Path(filename or "").name.strip()
    base = re.sub(r"\s+", " ", base)
    if not base:
        raise ValueError("Nazwa pliku jest pusta.")
    if not base.lower().endswith(".xlsx"):
        raise ValueError("Dozwolone sa tylko pliki .xlsx.")
    return base


class RuntimeSettingsStore:
    def __init__(self, *, data_dir: Path, settings_file: Path) -> None:
        self._data_dir = data_dir
        self._settings_file = settings_file
        self._lock = threading.Lock()

    def _read_file(self) -> dict[str, Any] | None:
        if not self._settings_file.exists():
            return None
        try:
            raw = json.loads(self._settings_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Plik ustawien runtime jest uszkodzony: {exc}") from exc
        if not isinstance(raw, dict):
            raise ValueError("Plik ustawien runtime ma nieprawidlowy format.")
        return raw

    def _merge_with_defaults(self, raw: dict[str, Any] | None) -> RuntimeSettingsData:
        defaults = default_runtime_settings(self._data_dir)
        if raw is None:
            return defaults

        main_file = sanitize_excel_filename(str(raw.get("main_file", defaults.main_file)))
        practical_file = sanitize_excel_filename(str(raw.get("practical_file", defaults.practical_file)))
        exact_groups = _normalize_text_list(list(raw.get("magdalenka_exact_groups", defaults.magdalenka_exact_groups)))
        prefixes = _normalize_text_list(list(raw.get("magdalenka_prefixes", defaults.magdalenka_prefixes)))

        return RuntimeSettingsData(
            main_file=main_file,
            practical_file=practical_file,
            magdalenka_exact_groups=tuple(exact_groups),
            magdalenka_prefixes=tuple(prefixes),
        )

    def load(self) -> RuntimeSettingsData:
        with self._lock:
            return self._merge_with_defaults(self._read_file())

    def save(self, data: RuntimeSettingsData) -> RuntimeSettingsData:
        with self._lock:
            self._settings_file.parent.mkdir(parents=True, exist_ok=True)
            self._settings_file.write_text(
                json.dumps(data.to_payload(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            return data

    def compose(
        self,
        *,
        main_file: str | None = None,
        practical_file: str | None = None,
        magdalenka_exact_groups: list[str] | None = None,
        magdalenka_prefixes: list[str] | None = None,
    ) -> RuntimeSettingsData:
        current = self.load()
        return RuntimeSettingsData(
            main_file=sanitize_excel_filename(main_file) if main_file is not None else current.main_file,
            practical_file=sanitize_excel_filename(practical_file) if practical_file is not None else current.practical_file,
            magdalenka_exact_groups=(
                tuple(_normalize_text_list(magdalenka_exact_groups))
                if magdalenka_exact_groups is not None
                else current.magdalenka_exact_groups
            ),
            magdalenka_prefixes=(
                tuple(_normalize_text_list(magdalenka_prefixes))
                if magdalenka_prefixes is not None
                else current.magdalenka_prefixes
            ),
        )

    def update(
        self,
        *,
        main_file: str | None = None,
        practical_file: str | None = None,
        magdalenka_exact_groups: list[str] | None = None,
        magdalenka_prefixes: list[str] | None = None,
    ) -> RuntimeSettingsData:
        next_data = self.compose(
            main_file=main_file,
            practical_file=practical_file,
            magdalenka_exact_groups=magdalenka_exact_groups,
            magdalenka_prefixes=magdalenka_prefixes,
        )
        return self.save(next_data)
