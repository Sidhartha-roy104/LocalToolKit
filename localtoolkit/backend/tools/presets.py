"""Presets API — read and update presets.
Bundled presets are read-only from backend/data/presets.json.
Custom presets and edits save to the user's app data folder (custom_presets.json).
"""
from __future__ import annotations
import json
import logging
from pathlib import Path
from fastapi import APIRouter, HTTPException, Request
from backend.utils.files import resource_path
from backend.config import APP_DATA_DIR

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/presets", tags=["Presets"])

_CUSTOM_PRESETS_FILE = APP_DATA_DIR / "custom_presets.json"


def _get_bundled_presets_path() -> Path:
    p = resource_path("backend/data/presets.json")
    if not p.exists():
        p = Path(__file__).resolve().parent.parent / "data" / "presets.json"
    return p


def _load_bundled_presets() -> list[dict]:
    p = _get_bundled_presets_path()
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception as exc:
        log.warning("Could not read bundled presets: %s", exc)
        return []


def _load_custom_presets() -> list[dict]:
    if not _CUSTOM_PRESETS_FILE.exists():
        return []
    try:
        data = json.loads(_CUSTOM_PRESETS_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception as exc:
        log.warning("Could not read custom presets: %s", exc)
        return []


@router.get("")
@router.get("/")
def list_presets():
    """
    Retrieve all presets: bundled presets merged with custom user presets from app data.
    Custom presets with matching ID override bundled defaults.
    """
    bundled = _load_bundled_presets()
    custom = _load_custom_presets()

    # Map by ID
    merged_map = {p.get("id"): p for p in bundled if isinstance(p, dict) and "id" in p}
    for cp in custom:
        if isinstance(cp, dict) and "id" in cp:
            merged_map[cp["id"]] = cp

    return list(merged_map.values())


@router.post("")
@router.post("/")
async def save_presets(request: Request):
    """
    Save custom presets and user edits to app data folder (custom_presets.json).
    Never modifies the bundled read-only presets file.
    """
    try:
        data = await request.json()
        if not isinstance(data, list):
            raise HTTPException(400, "Presets must be a list of preset objects.")

        APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
        tmp = _CUSTOM_PRESETS_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(_CUSTOM_PRESETS_FILE)
        return {"status": "ok", "count": len(data)}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, f"Failed to save custom presets: {exc}") from exc
