import json

from brainshtorm.settings import AppSettings, default_settings_path, load_settings, save_settings


def test_load_missing_settings_returns_defaults(tmp_path):
    settings_path = tmp_path / "missing.json"

    assert load_settings(path=settings_path) == AppSettings()


def test_save_and_load_settings_roundtrip_with_protected_key(tmp_path):
    settings_path = tmp_path / "settings.json"

    def protect(value: str) -> str:
        return f"protected:{value[::-1]}"

    def unprotect(value: str) -> str:
        return value.removeprefix("protected:")[::-1]

    settings = AppSettings(
        provider_name="Demo",
        api_key="secret-token",
        folder_id="folder-1",
        region_label="Москва",
        custom_region_id="213",
        budget_rub=90000,
        max_difficulty=4,
        project_label="SEO-сайт",
        num_phrases=80,
        pasted_directions="ремонт\nкурсы",
    )

    save_settings(settings, path=settings_path, protector=protect)

    raw_text = settings_path.read_text(encoding="utf-8")
    raw_payload = json.loads(raw_text)
    assert "secret-token" not in raw_text
    assert raw_payload["api_key"].startswith("protected:")
    assert load_settings(path=settings_path, unprotector=unprotect) == settings


def test_load_invalid_settings_returns_defaults(tmp_path):
    settings_path = tmp_path / "settings.json"
    settings_path.write_text("{broken json", encoding="utf-8")

    assert load_settings(path=settings_path) == AppSettings()


def test_default_settings_path_is_outside_project():
    path = default_settings_path()

    assert path.name == "settings.json"
    assert path.parent.name == ".brainshtorm"
