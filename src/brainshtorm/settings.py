from __future__ import annotations

import base64
import ctypes
import ctypes.wintypes
import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Any


Protector = Callable[[str], str]


@dataclass(frozen=True)
class AppSettings:
    provider_name: str = "Yandex Wordstat API"
    api_key: str = ""
    folder_id: str = ""
    region_label: str = "Россия"
    custom_region_id: str = ""
    budget_rub: int = 150000
    max_difficulty: int = 6
    project_label: str = "Лидогенерация"
    num_phrases: int = 50
    enable_serp: bool = False
    serp_finalists: int = 10
    serp_results: int = 10
    enable_ai: bool = False
    ai_model: str = "qwen3:8b"
    ai_finalists: int = 5
    ollama_base_url: str = "http://127.0.0.1:11434"
    pasted_directions: str = ""


def default_settings_path() -> Path:
    home_dir = Path(os.environ.get("BRAINSTHORM_HOME", Path.home() / ".brainshtorm"))
    return home_dir / "settings.json"


def load_settings(
    *,
    path: Path | None = None,
    unprotector: Protector | None = None,
) -> AppSettings:
    settings_path = path or default_settings_path()
    if not settings_path.exists():
        return AppSettings()

    try:
        payload = json.loads(settings_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return AppSettings()

    if not isinstance(payload, dict):
        return AppSettings()

    unprotect = unprotector or unprotect_secret
    defaults = AppSettings()
    return AppSettings(
        provider_name=_as_str(payload.get("provider_name"), defaults.provider_name),
        api_key=unprotect(_as_str(payload.get("api_key"), "")),
        folder_id=unprotect(_as_str(payload.get("folder_id"), "")),
        region_label=_as_str(payload.get("region_label"), defaults.region_label),
        custom_region_id=_as_str(payload.get("custom_region_id"), defaults.custom_region_id),
        budget_rub=_as_int(payload.get("budget_rub"), defaults.budget_rub),
        max_difficulty=_as_int(payload.get("max_difficulty"), defaults.max_difficulty),
        project_label=_as_str(payload.get("project_label"), defaults.project_label),
        num_phrases=_as_int(payload.get("num_phrases"), defaults.num_phrases),
        enable_serp=_as_bool(payload.get("enable_serp"), defaults.enable_serp),
        serp_finalists=_as_int(payload.get("serp_finalists"), defaults.serp_finalists),
        serp_results=_as_int(payload.get("serp_results"), defaults.serp_results),
        enable_ai=_as_bool(payload.get("enable_ai"), defaults.enable_ai),
        ai_model=_as_str(payload.get("ai_model"), defaults.ai_model),
        ai_finalists=_as_int(payload.get("ai_finalists"), defaults.ai_finalists),
        ollama_base_url=_as_str(payload.get("ollama_base_url"), defaults.ollama_base_url),
        pasted_directions=_as_str(payload.get("pasted_directions"), defaults.pasted_directions),
    )


def save_settings(
    settings: AppSettings,
    *,
    path: Path | None = None,
    protector: Protector | None = None,
) -> Path:
    settings_path = path or default_settings_path()
    protect = protector or protect_secret
    payload = asdict(settings)
    payload["api_key"] = protect(settings.api_key)
    payload["folder_id"] = protect(settings.folder_id)

    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return settings_path


def protect_secret(value: str) -> str:
    if not value:
        return ""
    if sys.platform == "win32":
        try:
            return "dpapi:" + _b64(_dpapi_protect(value.encode("utf-8")))
        except OSError:
            pass
    return "base64:" + _b64(value.encode("utf-8"))


def unprotect_secret(value: str) -> str:
    if not value:
        return ""
    if value.startswith("dpapi:"):
        try:
            return _dpapi_unprotect(_unb64(value.removeprefix("dpapi:"))).decode("utf-8")
        except (OSError, ValueError, UnicodeDecodeError):
            return ""
    if value.startswith("base64:"):
        try:
            return _unb64(value.removeprefix("base64:")).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            return ""
    return value


def _b64(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


def _unb64(value: str) -> bytes:
    return base64.b64decode(value.encode("ascii"), validate=True)


def _as_str(value: Any, default: str) -> str:
    return value if isinstance(value, str) else default


def _as_int(value: Any, default: int) -> int:
    if isinstance(value, bool):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_bool(value: Any, default: bool) -> bool:
    return value if isinstance(value, bool) else default


class _DataBlob(ctypes.Structure):
    _fields_ = [
        ("cbData", ctypes.wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_char)),
    ]


def _blob_from_bytes(value: bytes) -> tuple[_DataBlob, ctypes.Array[ctypes.c_char]]:
    buffer = ctypes.create_string_buffer(value)
    blob = _DataBlob(
        len(value),
        ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char)),
    )
    return blob, buffer


def _dpapi_protect(value: bytes) -> bytes:
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    input_blob, _input_buffer = _blob_from_bytes(value)
    output_blob = _DataBlob()

    ok = crypt32.CryptProtectData(
        ctypes.byref(input_blob),
        None,
        None,
        None,
        None,
        0,
        ctypes.byref(output_blob),
    )
    if not ok:
        raise ctypes.WinError()
    return _read_and_free_blob(output_blob, kernel32)


def _dpapi_unprotect(value: bytes) -> bytes:
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    input_blob, _input_buffer = _blob_from_bytes(value)
    output_blob = _DataBlob()

    ok = crypt32.CryptUnprotectData(
        ctypes.byref(input_blob),
        None,
        None,
        None,
        None,
        0,
        ctypes.byref(output_blob),
    )
    if not ok:
        raise ctypes.WinError()
    return _read_and_free_blob(output_blob, kernel32)


def _read_and_free_blob(output_blob: _DataBlob, kernel32: Any) -> bytes:
    try:
        return ctypes.string_at(output_blob.pbData, output_blob.cbData)
    finally:
        kernel32.LocalFree(ctypes.cast(output_blob.pbData, ctypes.c_void_p))
