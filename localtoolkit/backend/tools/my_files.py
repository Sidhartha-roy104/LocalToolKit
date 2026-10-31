"""My Files — Local organized storage on disk under Documents/LocalToolkit/."""
from __future__ import annotations
import os
import shutil
import sys
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Query, Request
from fastapi.responses import FileResponse
from backend.utils.files import sanitize_filename
from backend.tools.user_settings import load_settings, check_cloud_provider, get_default_my_files_dir

router = APIRouter(prefix="/api/files", tags=["My Files"])

_STANDARD_FOLDERS = [
    "Under 100 KB",
    "Under 200 KB",
    "Under 500 KB",
    "Under 1 MB",
    "Under 2 MB",
    "Over 2 MB",
    "Photos",
    "Signatures",
    "Certificates",
]


def get_my_files_root() -> Path:
    """Return user-configured My Files root directory (default: C:/Users/<name>/LocalToolkit)."""
    custom_env = os.getenv("LTK_MY_FILES_DIR")
    if custom_env:
        root = Path(custom_env).expanduser().resolve()
    else:
        try:
            settings = load_settings()
            custom_path = settings.get("my_files_path")
            if custom_path:
                root = Path(custom_path).expanduser().resolve()
            else:
                root = get_default_my_files_dir()
        except Exception:
            root = get_default_my_files_dir()

    root.mkdir(parents=True, exist_ok=True)
    # Ensure default folders exist
    for folder_name in _STANDARD_FOLDERS:
        (root / folder_name).mkdir(exist_ok=True)
    return root


def _auto_size_folder(size_bytes: int) -> str:
    """Determine size-matched folder name."""
    if size_bytes < 100 * 1024:
        return "Under 100 KB"
    elif size_bytes < 200 * 1024:
        return "Under 200 KB"
    elif size_bytes < 500 * 1024:
        return "Under 500 KB"
    elif size_bytes < 1024 * 1024:
        return "Under 1 MB"
    elif size_bytes < 2048 * 1024:
        return "Under 2 MB"
    return "Over 2 MB"


def _safe_resolve(subpath: str | Path, must_exist: bool = True) -> Path:
    """Assert resolved path strictly stays inside My Files root directory."""
    root = get_my_files_root()
    resolved = (root / subpath).resolve()
    if not str(resolved).startswith(str(root)):
        raise HTTPException(403, "Access denied: Path traversal detected.")
    if must_exist and not resolved.exists():
        raise HTTPException(404, "File or folder not found.")
    return resolved


@router.get("/info")
def get_info():
    """Get My Files root path and global summary statistics."""
    root = get_my_files_root()
    total_files = 0
    total_bytes = 0
    for p in root.rglob("*"):
        if p.is_file():
            total_files += 1
            total_bytes += p.stat().st_size
    return {
        "root_path": str(root),
        "total_files": total_files,
        "total_bytes": total_bytes,
        "folders": _STANDARD_FOLDERS,
        "cloud_warning": check_cloud_provider(str(root)),
    }


@router.get("/folders")
def list_folders():
    """List all folders with their item counts."""
    root = get_my_files_root()
    folders = []
    # Collect all top-level subdirectories
    for d in sorted(root.iterdir()):
        if d.is_dir():
            count = sum(1 for f in d.iterdir() if f.is_file())
            folders.append({
                "name": d.name,
                "count": count,
                "is_standard": d.name in _STANDARD_FOLDERS,
            })
    return folders


@router.get("/list")
def list_files(
    folder: str = Query("", description="Folder name or empty for all"),
    query: str = Query("", description="Search substring in filename"),
    file_type: str = Query("", description="Filter by ext: pdf, image, all"),
):
    """List files with metadata, searching, and filtering."""
    root = get_my_files_root()
    target_dirs = [_safe_resolve(folder)] if folder else [d for d in root.iterdir() if d.is_dir()]

    files = []
    q = query.lower().strip()

    for d in target_dirs:
        for f in sorted(d.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
            if not f.is_file():
                continue
            name = f.name
            if q and q not in name.lower():
                continue

            ext = f.suffix.lower()
            if file_type == "pdf" and ext != ".pdf":
                continue
            elif file_type == "image" and ext not in (".jpg", ".jpeg", ".png", ".webp", ".bmp"):
                continue

            stat = f.stat()
            files.append({
                "name": name,
                "folder": d.name,
                "size": stat.st_size,
                "modified": stat.st_mtime,
                "ext": ext,
            })
    return files


@router.post("/save")
async def save_file(
    file: UploadFile = File(...),
    folder: str = Form(""),
    filename: str = Form(""),
):
    """Save an output file directly into My Files."""
    root = get_my_files_root()
    data = await file.read()
    size_bytes = len(data)

    target_folder_name = folder.strip() or _auto_size_folder(size_bytes)
    folder_dir = _safe_resolve(target_folder_name, must_exist=False)
    folder_dir.mkdir(parents=True, exist_ok=True)

    clean_name = sanitize_filename(filename.strip() or file.filename or "file")
    dest_path = folder_dir / clean_name

    # Handle collision by appending numeric counter
    counter = 1
    stem = dest_path.stem
    suffix = dest_path.suffix
    while dest_path.exists():
        dest_path = folder_dir / f"{stem}_{counter}{suffix}"
        counter += 1

    dest_path.write_bytes(data)

    return {
        "status": "ok",
        "saved_path": str(dest_path),
        "folder": target_folder_name,
        "filename": dest_path.name,
        "size": size_bytes,
    }


@router.api_route("/open-folder", methods=["GET", "POST"])
async def open_folder_in_os(request: Request, folder: str = Form(""), f_query: str = Query("", alias="folder")):
    """Open folder in Windows File Explorer, macOS Finder, or Linux file manager."""
    folder_val = folder.strip() or f_query.strip()
    if not folder_val and request.method == "POST":
        try:
            body = await request.json()
            if isinstance(body, dict):
                folder_val = str(body.get("folder", "")).strip()
        except Exception:
            pass

    root = get_my_files_root()
    target = _safe_resolve(folder_val) if folder_val else root

    try:
        if sys.platform == "win32":
            os.startfile(str(target))
        elif sys.platform == "darwin":
            shutil.which("open") and os.system(f'open "{target}"')
        else:
            shutil.which("xdg-open") and os.system(f'xdg-open "{target}"')
        return {"status": "ok", "path": str(target)}
    except Exception as exc:
        raise HTTPException(500, f"Failed to open folder: {exc}") from exc


@router.api_route("/rename", methods=["POST", "PUT"])
async def rename_file(
    request: Request,
    folder: str = Form(""),
    old_name: str = Form(""),
    new_name: str = Form(""),
):
    """Rename a file in My Files (supports Form, Query, and JSON)."""
    f = folder.strip()
    o = old_name.strip()
    n = new_name.strip()
    if not (f and o and n):
        try:
            body = await request.json()
            if isinstance(body, dict):
                f = f or str(body.get("folder", "")).strip()
                o = o or str(body.get("old_name", "")).strip()
                n = n or str(body.get("new_name", "")).strip()
        except Exception:
            pass

    if not (f and o and n):
        raise HTTPException(400, "Missing required parameters: folder, old_name, new_name.")

    folder_dir = _safe_resolve(f)
    src = _safe_resolve(folder_dir / o)
    clean_new = sanitize_filename(n)
    dst = folder_dir / clean_new
    if dst.exists() and dst != src:
        raise HTTPException(400, "A file with that name already exists.")
    src.rename(dst)
    return {"status": "ok", "name": clean_new}


@router.api_route("/move", methods=["POST", "PUT"])
async def move_file(
    request: Request,
    from_folder: str = Form(""),
    to_folder: str = Form(""),
    filename: str = Form(""),
):
    """Move a file to another folder in My Files."""
    ff = from_folder.strip()
    tf = to_folder.strip()
    fn = filename.strip()
    if not (ff and tf and fn):
        try:
            body = await request.json()
            if isinstance(body, dict):
                ff = ff or str(body.get("from_folder", "")).strip()
                tf = tf or str(body.get("to_folder", "")).strip()
                fn = fn or str(body.get("filename", "")).strip()
        except Exception:
            pass

    if not (ff and tf and fn):
        raise HTTPException(400, "Missing required parameters: from_folder, to_folder, filename.")

    src_dir = _safe_resolve(ff)
    dst_dir = _safe_resolve(tf, must_exist=False)
    dst_dir.mkdir(parents=True, exist_ok=True)
    src = _safe_resolve(src_dir / fn)
    dst = dst_dir / fn
    if dst.exists():
        raise HTTPException(400, "A file with that name already exists in target folder.")
    shutil.move(str(src), str(dst))
    return {"status": "ok", "folder": tf}


@router.api_route("/delete", methods=["DELETE", "POST", "GET"])
async def delete_file(
    request: Request,
    folder: str = Query(""),
    filename: str = Query(""),
    name: str = Query(""),
):
    """Delete a specific file from My Files (supports Query, Form, or JSON)."""
    f = folder.strip()
    fn = (filename or name).strip()
    if not fn and request.method in ("POST", "DELETE"):
        try:
            form = await request.form()
            f = f or str(form.get("folder", "")).strip()
            fn = fn or str(form.get("filename", "") or form.get("name", "")).strip()
        except Exception:
            pass
        if not fn:
            try:
                body = await request.json()
                if isinstance(body, dict):
                    f = f or str(body.get("folder", "")).strip()
                    fn = fn or str(body.get("filename", "") or body.get("name", "")).strip()
            except Exception:
                pass

    if not fn:
        raise HTTPException(400, "Filename is required.")
    file_path = _safe_resolve(Path(f) / fn)
    if file_path.exists():
        file_path.unlink()
    return {"status": "ok", "deleted": fn}


@router.delete("/delete-all")
def delete_all_files():
    """Delete all user files inside My Files root."""
    root = get_my_files_root()
    count = 0
    for p in root.rglob("*"):
        if p.is_file():
            p.unlink()
            count += 1
    return {"status": "ok", "deleted_count": count}


@router.get("/download/{folder}/{filename}")
def download_my_file(folder: str, filename: str, token: str = Query(None)):
    """Download a file from My Files."""
    file_path = _safe_resolve(Path(folder) / filename)
    ext = file_path.suffix.lower()
    media_type = "application/pdf" if ext == ".pdf" else ("image/jpeg" if ext in (".jpg", ".jpeg") else "application/octet-stream")
    return FileResponse(str(file_path), media_type=media_type, filename=file_path.name)
