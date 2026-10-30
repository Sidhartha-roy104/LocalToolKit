"""
Temporary file / directory helpers.
Each request gets its own UUID-named temp dir; it is deleted after the response.
No filenames or file contents are ever logged.
"""
from __future__ import annotations
import os, re, shutil, uuid, logging
from pathlib import Path
from backend.config import TEMP_ROOT

log = logging.getLogger(__name__)


def make_temp_dir() -> Path:
    """Create a fresh, isolated temp directory for one request."""
    TEMP_ROOT.mkdir(parents=True, exist_ok=True)
    d = TEMP_ROOT / uuid.uuid4().hex
    d.mkdir()
    return d


def cleanup_temp_dir(path: Path) -> None:
    """Silently remove a temp directory and all its contents."""
    try:
        shutil.rmtree(path, ignore_errors=True)
    except Exception:
        pass  # best-effort; never raise inside a BackgroundTask


def sweep_old_temps() -> None:
    """Remove any leftover temp directories from previous runs (called at startup)."""
    if not TEMP_ROOT.exists():
        return
    for item in TEMP_ROOT.iterdir():
        if item.is_dir():
            shutil.rmtree(item, ignore_errors=True)
    log.info("Swept leftover temp directories.")


_UNSAFE = re.compile(r"[^\w.\-]")

def sanitize_filename(name: str) -> str:
    """
    Return a safe filename: keep only word chars, dots, hyphens.
    The actual storage name is always a UUID; this is only for display / output naming.
    """
    stem = Path(name).stem
    suffix = Path(name).suffix.lower()
    safe_stem = _UNSAFE.sub("_", stem)[:80] or "file"
    return safe_stem + suffix


def safe_output_path(directory: Path, filename: str) -> Path:
    """
    Resolve an output path and assert it stays inside `directory`
    (path-traversal guard).
    """
    resolved = (directory / filename).resolve()
    if not str(resolved).startswith(str(directory.resolve())):
        raise ValueError("Path traversal detected")
    return resolved
