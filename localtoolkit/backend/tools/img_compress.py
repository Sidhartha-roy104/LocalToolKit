"""Image Compress — reduce image file size with quality slider, target KB binary search, and live estimation."""
from __future__ import annotations
from typing import Any, List
import io
import zipfile
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from PIL import Image
import pillow_heif

pillow_heif.register_heif_opener()

from backend.utils.files import make_temp_dir, cleanup_temp_dir, sanitize_filename
from backend.utils.security import validate_upload
from backend.config import ACCEPTED_IMAGE_EXTENSIONS

router = APIRouter(prefix="/api/image", tags=["Images"])


def _safe_int(val: Any, default: int) -> int:
    try:
        if val is None or str(val).strip() == "":
            return default
        return int(float(val))
    except (ValueError, TypeError):
        return default


def _compress_one(
    data: bytes, ext: str, quality: int, max_width: int = 0, max_height: int = 0
) -> tuple[bytes, str]:
    """Compress a single image. Returns (output_bytes, output_ext)."""
    img = Image.open(io.BytesIO(data))
    if img.mode not in ("RGB", "RGBA", "L"):
        img = img.convert("RGB")
    if max_width > 0 or max_height > 0:
        mw = max_width or img.width
        mh = max_height or img.height
        img.thumbnail((mw, mh), Image.Resampling.LANCZOS)
    out = io.BytesIO()
    if ext in (".heic", ".heif", ".bmp"):
        img.convert("RGB").save(out, format="WEBP", quality=quality, method=6)
        out_ext = ".webp"
    elif ext == ".png" and img.mode == "RGBA":
        img.save(out, format="PNG", optimize=True)
        out_ext = ".png"
    elif ext == ".png":
        img.convert("RGB").save(out, format="JPEG", quality=quality, optimize=True)
        out_ext = ".jpg"
    elif ext == ".webp":
        img.save(out, format="WEBP", quality=quality, method=6)
        out_ext = ".webp"
    else:
        img.convert("RGB").save(out, format="JPEG", quality=quality, optimize=True)
        out_ext = ".jpg"
    return out.getvalue(), out_ext


def compress_to_target(
    data: bytes, ext: str, target_bytes: int, allow_downscale: bool = True
) -> tuple[bytes, str, bool]:
    """
    Binary search quality (and scale if needed) to meet target_bytes.
    Returns (out_bytes, out_ext, reachable).
    """
    low_q, high_q = 20, 92
    best_bytes = None
    best_ext = ".jpg"

    # 1. Binary search on quality
    for _ in range(7):
        mid_q = (low_q + high_q) // 2
        b, e = _compress_one(data, ext, mid_q)
        best_ext = e
        if len(b) <= target_bytes:
            best_bytes = b
            low_q = mid_q + 1  # Try higher quality
        else:
            high_q = mid_q - 1

    if best_bytes and len(best_bytes) <= target_bytes:
        return best_bytes, best_ext, True

    # 2. If lowest quality is still too large, downscale progressively
    if allow_downscale:
        img = Image.open(io.BytesIO(data))
        orig_w, orig_h = img.size
        scale = 0.90
        while scale >= 0.20:
            nw = max(10, int(orig_w * scale))
            nh = max(10, int(orig_h * scale))
            b, e = _compress_one(data, ext, 35, max_width=nw, max_height=nh)
            if len(b) <= target_bytes:
                return b, e, True
            scale -= 0.10

    # Fallback to smallest achievable
    fallback_b, fallback_e = _compress_one(data, ext, 20)
    return fallback_b, fallback_e, False


@router.post("/estimate-size")
async def estimate_image_size(
    file: UploadFile | None = File(None),
    files: list[UploadFile] | None = File(None),
    quality: Any = Form(75),
    target_kb: Any = Form(0),
):
    """Fast estimation of compressed image size for UI feedback."""
    actual_file = file or (files[0] if files else None)
    if not actual_file:
        raise HTTPException(400, "An image file is required.")

    try:
        raw_q = int(float(quality))
        if raw_q < 1 or raw_q > 100:
            raise HTTPException(400, "Quality must be between 1 and 100.")
        q_val = min(95, raw_q)
    except HTTPException:
        raise
    except Exception:
        q_val = 75
    kb_val = max(0, _safe_int(target_kb, 0))

    try:
        data = await validate_upload(actual_file, ACCEPTED_IMAGE_EXTENSIONS)
        ext = Path(actual_file.filename or "img.jpg").suffix.lower()
        orig_bytes = len(data)

        if kb_val > 0:
            target_bytes = kb_val * 1024
            b, _, reachable = compress_to_target(data, ext, target_bytes)
            return {
                "original_bytes": orig_bytes,
                "estimated_bytes": len(b),
                "reachable": reachable,
                "target_bytes": target_bytes,
            }
        else:
            b, _ = _compress_one(data, ext, q_val)
            return {
                "original_bytes": orig_bytes,
                "estimated_bytes": len(b),
                "reachable": True,
            }
    except Exception as exc:
        raise HTTPException(400, f"Estimation failed: {exc}") from exc


@router.post("/compress")
async def compress_image(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] | None = File(None),
    file: UploadFile | None = File(None),
    quality: Any = Form(75),       # 1-95
    target_kb: Any = Form(0),      # If > 0, hits target size via binary search
    max_width: Any = Form(0),      # 0 = no limit
    max_height: Any = Form(0),
):
    """Compress one or more images with quality or target size."""
    all_files = []
    if files:
        all_files.extend(files)
    if file:
        all_files.append(file)

    if not all_files:
        raise HTTPException(400, "At least one image file is required.")

    try:
        raw_q = int(float(quality))
        if raw_q < 1 or raw_q > 100:
            raise HTTPException(400, "Quality must be between 1 and 100.")
        q_val = min(95, raw_q)
    except HTTPException:
        raise
    except Exception:
        q_val = 75
    kb_val = max(0, _safe_int(target_kb, 0))
    mw_val = max(0, _safe_int(max_width, 0))
    mh_val = max(0, _safe_int(max_height, 0))

    tmp = make_temp_dir()
    try:
        results: list[tuple[str, bytes]] = []
        for f in all_files:
            ext = Path(f.filename or "img.jpg").suffix.lower()
            data = await validate_upload(f, ACCEPTED_IMAGE_EXTENSIONS)

            is_reachable = True
            if kb_val > 0:
                out_bytes, out_ext, is_reachable = compress_to_target(data, ext, kb_val * 1024)
            else:
                out_bytes, out_ext = _compress_one(data, ext, q_val, mw_val, mh_val)

            stem = sanitize_filename(f.filename or "image").rsplit(".", 1)[0]
            results.append((f"{stem}_compressed{out_ext}", out_bytes, is_reachable))

        if len(results) == 1:
            name, out_bytes, reached = results[0]
            ext = name.rsplit(".", 1)[-1].lower()
            mt = {"jpg": "image/jpeg", "webp": "image/webp", "png": "image/png"}.get(ext, "application/octet-stream")
            headers = {"Content-Disposition": f'attachment; filename="{name}"'}
            if kb_val > 0:
                headers["X-Target-Reachable"] = "true" if reached else "false"
                if not reached:
                    headers["X-Warning"] = f"Target size {kb_val} KB could not be reached cleanly; smallest possible image is returned ({len(out_bytes)//1024} KB)."
            background_tasks.add_task(cleanup_temp_dir, tmp)
            return StreamingResponse(
                io.BytesIO(out_bytes),
                media_type=mt,
                headers=headers,
            )

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for name, out_bytes, _ in results:
                zf.writestr(name, out_bytes)
        buf.seek(0)
        background_tasks.add_task(cleanup_temp_dir, tmp)
        return StreamingResponse(
            buf,
            media_type="application/zip",
            headers={"Content-Disposition": 'attachment; filename="compressed_images.zip"'},
        )
    except HTTPException:
        cleanup_temp_dir(tmp)
        raise
    except Exception as exc:
        cleanup_temp_dir(tmp)
        raise HTTPException(500, f"Compression failed: {exc}") from exc
