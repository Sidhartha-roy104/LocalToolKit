"""
Temporary file / directory helpers and resource resolution.
Each request gets its own UUID-named temp dir; it is deleted after the response.
No filenames or file contents are ever logged.
"""
from __future__ import annotations
import os, sys, re, shutil, uuid, logging
from pathlib import Path

log = logging.getLogger(__name__)


def resource_path(relative: str | Path = "") -> Path:
    """
    Get absolute path to resource, works for development and PyInstaller frozen app.
    When frozen with PyInstaller, sys._MEIPASS points to the bundled files folder.
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base = Path(sys._MEIPASS)
    elif getattr(sys, "frozen", False):
        base = Path(sys.executable).resolve().parent
    else:
        # Development root (project directory)
        base = Path(__file__).resolve().parent.parent.parent
    
    if relative:
        return (base / relative).resolve()
    return base.resolve()


def get_temp_root() -> Path:
    import tempfile
    return Path(tempfile.gettempdir()) / "localtoolkit"


def get_app_data_dir() -> Path:
    """
    Return user application data directory for settings, history, and custom presets.
    Windows: %APPDATA%/LocalToolkit
    macOS: ~/Library/Application Support/LocalToolkit
    Linux: ~/.config/LocalToolkit (or $XDG_CONFIG_HOME/LocalToolkit)
    """
    if sys.platform == "win32":
        app_data = os.environ.get("APPDATA")
        base = Path(app_data) if app_data else (Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        xdg = os.environ.get("XDG_CONFIG_HOME")
        base = Path(xdg) if xdg else (Path.home() / ".config")
    d = (base / "LocalToolkit").resolve()
    d.mkdir(parents=True, exist_ok=True)
    return d


def make_temp_dir() -> Path:
    """Create a fresh, isolated temp directory in the system temp directory."""
    temp_root = get_temp_root()
    temp_root.mkdir(parents=True, exist_ok=True)
    d = temp_root / uuid.uuid4().hex
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
    temp_root = get_temp_root()
    if not temp_root.exists():
        return
    for item in temp_root.iterdir():
        if item.is_dir():
            shutil.rmtree(item, ignore_errors=True)
    log.info("Swept leftover temp directories from %s.", temp_root)


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
