"""Image Compress — reduce image file size with optional resize and batch support."""
from __future__ import annotations
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from typing import List
from PIL import Image
import pillow_heif, io, zipfile
from backend.utils.files import make_temp_dir, cleanup_temp_dir, sanitize_filename
from backend.utils.security import validate_upload
from backend.config import ACCEPTED_IMAGE_EXTENSIONS

pillow_heif.register_heif_opener()

router = APIRouter(prefix="/api/image", tags=["Images"])

def _compress_one(data: bytes, ext: str, quality: int,
                  max_width: int, max_height: int) -> tuple[bytes, str]:
    """Compress a single image. Returns (output_bytes, output_ext)."""
    img = Image.open(io.BytesIO(data))
    if img.mode not in ("RGB", "RGBA", "L"):
        img = img.convert("RGB")
    # Optional resize
    if max_width > 0 or max_height > 0:
        mw = max_width or img.width
        mh = max_height or img.height
        img.thumbnail((mw, mh), Image.LANCZOS)
    out = io.BytesIO()
    # HEIC/BMP → WEBP; PNG with alpha → PNG; else JPEG
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


@router.post("/compress")
async def compress_image(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    quality: int = Form(75),       # 1-95
    max_width: int = Form(0),      # 0 = no limit
    max_height: int = Form(0),
):
    """Compress one or more images. Returns single file or ZIP for batch."""
    if not (1 <= quality <= 95):
        raise HTTPException(400, "quality must be between 1 and 95.")
    tmp = make_temp_dir()
    try:
        results: list[tuple[str, bytes]] = []
        for f in files:
            ext = f.filename.lower()[f.filename.rfind("."):]
            data = await validate_upload(f, ACCEPTED_IMAGE_EXTENSIONS)
            out_bytes, out_ext = _compress_one(data, ext, quality, max_width, max_height)
            stem = sanitize_filename(f.filename).rsplit(".", 1)[0]
            results.append((f"{stem}_compressed{out_ext}", out_bytes))

        if len(results) == 1:
            name, out_bytes = results[0]
            ext = name.rsplit(".", 1)[-1]
            mt = {"jpg": "image/jpeg", "webp": "image/webp", "png": "image/png"}.get(ext, "application/octet-stream")
            background_tasks.add_task(cleanup_temp_dir, tmp)
            return StreamingResponse(io.BytesIO(out_bytes), media_type=mt,
                                     headers={"Content-Disposition": f'attachment; filename="{name}"'})

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for name, out_bytes in results:
                zf.writestr(name, out_bytes)
        buf.seek(0)
        background_tasks.add_task(cleanup_temp_dir, tmp)
        return StreamingResponse(buf, media_type="application/zip",
                                 headers={"Content-Disposition": 'attachment; filename="compressed_images.zip"'})
    except HTTPException:
        cleanup_temp_dir(tmp)
        raise
    except Exception as exc:
        cleanup_temp_dir(tmp)
        raise HTTPException(500, f"Compression failed: {exc}") from exc

