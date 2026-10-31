"""Image Convert — convert between JPG, PNG, WEBP, HEIC, BMP formats."""
from __future__ import annotations
from typing import List
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from PIL import Image
import pillow_heif, io, zipfile
from backend.utils.files import make_temp_dir, cleanup_temp_dir, sanitize_filename
from backend.utils.security import validate_upload
from backend.config import ACCEPTED_IMAGE_EXTENSIONS

pillow_heif.register_heif_opener()

router = APIRouter(prefix="/api/image", tags=["Images"])

_FMT_MAP = {
    "jpg":  ("JPEG",  "image/jpeg",   ".jpg"),
    "jpeg": ("JPEG",  "image/jpeg",   ".jpg"),
    "png":  ("PNG",   "image/png",    ".png"),
    "webp": ("WEBP",  "image/webp",   ".webp"),
    "bmp":  ("BMP",   "image/bmp",    ".bmp"),
}


@router.post("/convert")
async def convert_image(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] | None = File(None),
    file: UploadFile | None = File(None),
    to_format: str = Form("jpg"),
):
    """Convert images to a target format."""
    all_files = []
    if files:
        all_files.extend(files)
    if file:
        all_files.append(file)

    if not all_files:
        raise HTTPException(400, "At least one image is required to convert.")

    target_fmt = to_format.lower().strip(".")
    if target_fmt not in _FMT_MAP:
        target_fmt = "jpg"
    pil_fmt, mime, out_ext = _FMT_MAP[target_fmt]

    tmp = make_temp_dir()
    try:
        results: list[tuple[str, bytes]] = []
        for f in all_files:
            data = await validate_upload(f, ACCEPTED_IMAGE_EXTENSIONS)
            img = Image.open(io.BytesIO(data))
            if pil_fmt == "JPEG" and img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            elif img.mode == "P":
                img = img.convert("RGBA")
            out = io.BytesIO()
            save_kwargs = {}
            if pil_fmt in ("JPEG", "WEBP"):
                save_kwargs["quality"] = 90
            img.save(out, format=pil_fmt, **save_kwargs)
            stem = sanitize_filename(f.filename or "image").rsplit(".", 1)[0]
            results.append((f"{stem}{out_ext}", out.getvalue()))

        if len(results) == 1:
            name, out_bytes = results[0]
            background_tasks.add_task(cleanup_temp_dir, tmp)
            return StreamingResponse(io.BytesIO(out_bytes), media_type=mime,
                                     headers={"Content-Disposition": f'attachment; filename="{name}"'})
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for name, out_bytes in results:
                zf.writestr(name, out_bytes)
        buf.seek(0)
        background_tasks.add_task(cleanup_temp_dir, tmp)
        return StreamingResponse(buf, media_type="application/zip",
                                 headers={"Content-Disposition": 'attachment; filename="converted_images.zip"'})
    except HTTPException:
        cleanup_temp_dir(tmp)
        raise
    except Exception as exc:
        cleanup_temp_dir(tmp)
        raise HTTPException(500, f"Conversion failed: {exc}") from exc
