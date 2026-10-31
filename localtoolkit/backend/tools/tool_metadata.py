"""Metadata Remover — wipe EXIF/GPS tags from images and document info from PDFs."""
from __future__ import annotations
import io
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from PIL import Image
import fitz

from backend.utils.files import make_temp_dir, cleanup_temp_dir, safe_output_path, sanitize_filename
from backend.utils.security import validate_upload
from backend.config import ACCEPTED_IMAGE_EXTENSIONS, ACCEPTED_PDF_EXTENSIONS

router = APIRouter(prefix="/api/tools", tags=["Extra Tools"])


@router.post("/remove-metadata")
async def remove_metadata(
    background_tasks: BackgroundTasks,
    file: UploadFile | None = File(None),
    files: list[UploadFile] | None = File(None),
):
    """Strip all metadata, GPS tags, camera details, and PDF author information."""
    actual_file = file or (files[0] if files else None)
    if not actual_file:
        raise HTTPException(400, "A file is required to remove metadata.")

    tmp = make_temp_dir()
    try:
        ext = Path(actual_file.filename or "").suffix.lower()
        allowed = ACCEPTED_IMAGE_EXTENSIONS | ACCEPTED_PDF_EXTENSIONS
        data = await validate_upload(actual_file, allowed)
        safe_stem = Path(sanitize_filename(actual_file.filename or "cleaned")).stem

        if ext == ".pdf":
            doc = fitz.open(stream=data, filetype="pdf")
            doc.set_metadata({})  # Wipes author, creator, producer, title, keywords
            out_name = f"{safe_stem}_clean.pdf"
            out_path = safe_output_path(tmp, out_name)
            doc.save(str(out_path), garbage=4, deflate=True, clean=True)
            doc.close()
            media_type = "application/pdf"
        else:
            # Strip image EXIF by copying raw pixel buffer without metadata
            img = Image.open(io.BytesIO(data))
            mode = "RGBA" if img.mode in ("RGBA", "LA") else "RGB"
            clean_img = Image.new(mode, img.size)
            clean_img.putdata(list(img.getdata()))

            out_ext = ".png" if mode == "RGBA" else ".jpg"
            out_name = f"{safe_stem}_clean{out_ext}"
            out_path = safe_output_path(tmp, out_name)

            if out_ext == ".jpg":
                clean_img.convert("RGB").save(str(out_path), format="JPEG", quality=90, optimize=True)
                media_type = "image/jpeg"
            else:
                clean_img.save(str(out_path), format="PNG", optimize=True)
                media_type = "image/png"

        background_tasks.add_task(cleanup_temp_dir, tmp)
        return FileResponse(str(out_path), media_type=media_type, filename=out_name)
    except HTTPException:
        cleanup_temp_dir(tmp)
        raise
    except Exception as exc:
        cleanup_temp_dir(tmp)
        raise HTTPException(500, f"Metadata removal failed: {exc}") from exc
