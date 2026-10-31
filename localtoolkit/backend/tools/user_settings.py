"""
User Settings, History, Favorites, and App Data Storage.
Saved atomically to %APPDATA%/LocalToolkit/settings_history.json (or macOS/Linux equivalent).
Tolerant of missing or corrupt file. Never logs or transmits private data.
"""
from __future__ import annotations
from typing import Any
import json
import logging
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from fastapi import APIRouter, Form, HTTPException, Request

from backend.config import APP_DATA_DIR
from backend.utils.files import sanitize_filename

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/user", tags=["User Settings"])

_SETTINGS_FILE = APP_DATA_DIR / "settings_history.json"

_CLOUD_KEYWORDS = [
    "onedrive", "google drive", "dropbox", "icloud", "box sync", "box drive", "nextcloud", "owncloud", "cloudstorage"
]


def check_cloud_provider(path_str: str) -> str | None:
    """Return cloud provider name if path is inside a cloud-synced folder."""
    p = path_str.lower()
    for provider in _CLOUD_KEYWORDS:
        if provider in p:
            return provider.title()
    return None


def get_default_my_files_dir() -> Path:
    """Default folder: C:/Users/<name>/LocalToolkit (home dir + LocalToolkit)."""
    return (Path.home() / "LocalToolkit").resolve()


def _get_default_settings() -> dict:
    return {
        "favorites": [],
        "recent_tools": [],
        "history_paused": False,
        "recent_files_enabled": False,
        "recent_files": [],
        "my_files_path": str(get_default_my_files_dir()),
    }


def load_settings() -> dict:
    """Load settings from JSON, returning defaults if file is missing or corrupt."""
    defaults = _get_default_settings()
    if not _SETTINGS_FILE.exists():
        return defaults
    try:
        text = _SETTINGS_FILE.read_text(encoding="utf-8")
        data = json.loads(text)
        if not isinstance(data, dict):
            return defaults
        # Fill in any missing default keys
        for k, v in defaults.items():
            if k not in data:
                data[k] = v
        return data
    except Exception as exc:
        log.warning("Could not read settings (%s); falling back to default.", exc)
        return defaults


def save_settings(data: dict) -> None:
    """Write settings atomically via temporary file replacement."""
    try:
        APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
        tmp_file = _SETTINGS_FILE.with_suffix(".tmp")
        tmp_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp_file.replace(_SETTINGS_FILE)
    except Exception as exc:
        log.error("Failed to write settings atomically: %s", exc)
        raise HTTPException(500, f"Failed to save settings: {exc}") from exc


@router.get("/settings")
def get_user_settings():
    """Retrieve user settings, favorites, recent tools, and storage paths."""
    settings = load_settings()
    my_files_path = settings.get("my_files_path", str(get_default_my_files_dir()))
    cloud_warning = check_cloud_provider(my_files_path)

    return {
        **settings,
        "app_data_path": str(APP_DATA_DIR),
        "cloud_warning": cloud_warning,
    }


@router.post("/settings")
async def update_user_settings(
    request: Request,
    history_paused: Any = Form(None),
    recent_files_enabled: Any = Form(None),
    my_files_path: str | None = Form(None),
):
    """Update general settings."""
    hp = history_paused
    rfe = recent_files_enabled
    mfp = my_files_path

    # Try json body fallback if form fields were not present
    if hp is None and rfe is None and mfp is None:
        try:
            body = await request.json()
            if isinstance(body, dict):
                hp = body.get("history_paused")
                rfe = body.get("recent_files_enabled")
                mfp = body.get("my_files_path")
        except Exception:
            pass

    settings = load_settings()
    if hp is not None:
        settings["history_paused"] = str(hp).lower() in ("true", "1")
    if rfe is not None:
        settings["recent_files_enabled"] = str(rfe).lower() in ("true", "1")
    if mfp is not None and str(mfp).strip():
        clean_path = str(Path(str(mfp).strip()).expanduser().resolve())
        settings["my_files_path"] = clean_path

    save_settings(settings)
    cloud_warning = check_cloud_provider(settings["my_files_path"])
    return {
        "status": "ok",
        "settings": settings,
        "cloud_warning": cloud_warning,
    }


@router.post("/record-tool")
async def record_tool_usage(request: Request, tool_id: str = Form("")):
    """Record recently used tool. Capped at 12 items. Ignored if history is paused."""
    tid = tool_id.strip()
    if not tid:
        try:
            body = await request.json()
            if isinstance(body, dict):
                tid = str(body.get("tool_id", "")).strip()
        except Exception:
            pass

    if not tid:
        raise HTTPException(400, "tool_id is required.")

    settings = load_settings()
    if settings.get("history_paused", False):
        return {"status": "paused"}

    recent = settings.get("recent_tools", [])
    now = datetime.now(timezone.utc).isoformat()
    recent = [item for item in recent if (item.get("id") if isinstance(item, dict) else item) != tid]
    recent.insert(0, {"id": tid, "timestamp": now})
    settings["recent_tools"] = recent[:12]
    save_settings(settings)
    return {"status": "ok", "recent_tools": settings["recent_tools"]}


@router.post("/record-file")
async def record_recent_file(request: Request, name: str = Form(""), size: Any = Form(0)):
    """Record processed file name and size only (never contents). Ignored if disabled."""
    fn = name.strip()
    sz = 0
    try:
        sz = int(float(size or 0))
    except (ValueError, TypeError):
        pass

    if not fn:
        try:
            body = await request.json()
            if isinstance(body, dict):
                fn = str(body.get("name", "")).strip()
                sz = int(float(body.get("size", 0) or 0))
        except Exception:
            pass

    if not fn:
        return {"status": "ignored"}

    settings = load_settings()
    if not settings.get("recent_files_enabled", False):
        return {"status": "disabled"}

    recent = settings.get("recent_files", [])
    clean_name = sanitize_filename(fn)
    now = datetime.now(timezone.utc).isoformat()
    recent = [f for f in recent if f.get("name") != clean_name]
    recent.insert(0, {"name": clean_name, "size": sz, "timestamp": now})
    settings["recent_files"] = recent[:20]
    save_settings(settings)
    return {"status": "ok"}


@router.post("/toggle-favorite")
async def toggle_favorite(request: Request, tool_id: str = Form("")):
    """Star or unstar a tool in favorites."""
    tid = tool_id.strip()
    if not tid:
        try:
            body = await request.json()
            if isinstance(body, dict):
                tid = str(body.get("tool_id", "")).strip()
        except Exception:
            pass

    if not tid:
        raise HTTPException(400, "tool_id is required.")

    settings = load_settings()
    favs = set(settings.get("favorites", []))
    if tid in favs:
        favs.remove(tid)
        is_fav = False
    else:
        favs.add(tid)
        is_fav = True
    settings["favorites"] = sorted(list(favs))
    save_settings(settings)
    return {"status": "ok", "favorites": settings["favorites"], "is_favorite": is_fav}


@router.post("/clear-history")
def clear_history():
    """Clear all recently used tools."""
    settings = load_settings()
    settings["recent_tools"] = []
    save_settings(settings)
    return {"status": "ok"}


@router.post("/clear-recent-files")
def clear_recent_files():
    """Clear all recent files list."""
    settings = load_settings()
    settings["recent_files"] = []
    save_settings(settings)
    return {"status": "ok"}


@router.post("/open-appdata")
def open_appdata_folder():
    """Open app data directory in native OS file manager."""
    try:
        APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(str(APP_DATA_DIR))
        elif sys.platform == "darwin":
            shutil.which("open") and os.system(f'open "{APP_DATA_DIR}"')
        else:
            shutil.which("xdg-open") and os.system(f'xdg-open "{APP_DATA_DIR}"')
        return {"status": "ok", "path": str(APP_DATA_DIR)}
    except Exception as exc:
        raise HTTPException(500, f"Failed to open app data folder: {exc}") from exc

