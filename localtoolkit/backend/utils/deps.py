"""
Dependency detection: LibreOffice, Ghostscript (optional).
Results cached at startup via get_deps().
"""
from __future__ import annotations
import shutil, subprocess, functools, logging, sys
from pathlib import Path

log = logging.getLogger(__name__)

_SOFFICE_CANDIDATES_WIN = [
    r"C:\Program Files\LibreOffice\program\soffice.exe",
    r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
]
_SOFFICE_CANDIDATES_UNIX = ["/usr/bin/soffice", "/usr/local/bin/soffice",
                             "/Applications/LibreOffice.app/Contents/MacOS/soffice"]


def find_soffice() -> str | None:
    """Return the path to soffice/libreoffice if available, else None."""
    # Try PATH first
    found = shutil.which("soffice") or shutil.which("libreoffice")
    if found:
        return found
    candidates = _SOFFICE_CANDIDATES_WIN if sys.platform == "win32" else _SOFFICE_CANDIDATES_UNIX
    for p in candidates:
        if Path(p).exists():
            return p
    return None


def find_ghostscript() -> str | None:
    found = shutil.which("gs") or shutil.which("gswin64c") or shutil.which("gswin32c")
    return found


@functools.lru_cache(maxsize=1)
def get_deps() -> dict[str, bool | str]:
    soffice = find_soffice()
    gs = find_ghostscript()
    result = {
        "libreoffice": bool(soffice),
        "libreoffice_path": soffice or "",
        "ghostscript": bool(gs),
        "ghostscript_path": gs or "",
    }
    log.info("Dependency check: libreoffice=%s gs=%s", bool(soffice), bool(gs))
    return result

