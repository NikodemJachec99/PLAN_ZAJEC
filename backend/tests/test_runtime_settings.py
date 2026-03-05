from pathlib import Path

from app.runtime_settings import RuntimeSettingsStore


def test_runtime_settings_store_persists_values(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "plan_zajec.xlsx").write_bytes(b"x")
    (data_dir / "praktyki_tidy (1).xlsx").write_bytes(b"x")

    store = RuntimeSettingsStore(
        data_dir=data_dir,
        settings_file=data_dir / "runtime_settings.json",
    )

    updated = store.update(
        main_file="plan_zajec.xlsx",
        practical_file="praktyki_tidy (1).xlsx",
        magdalenka_exact_groups=["11", "d"],
        magdalenka_prefixes=["11"],
    )

    loaded = store.load()
    assert loaded.main_file == "plan_zajec.xlsx"
    assert loaded.practical_file == "praktyki_tidy (1).xlsx"
    assert tuple(updated.magdalenka_exact_groups) == tuple(loaded.magdalenka_exact_groups)
