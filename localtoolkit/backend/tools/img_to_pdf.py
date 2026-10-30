"""Images to PDF — combine multiple images into a single PDF using img2pdf."""
from __future__ import annotations
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from typing import List
from PIL import Image
import pillow_heif, img2pdf, io
from backend.utils.files import make_temp_dir, cleanup_temp_dir, safe_output_path
from backend.utils.security import validate_upload
from backend.config import ACCEPTED_IMAGE_EXTENSIONS

pillow_heif.register_heif_opener()

router = APIRouter(prefix="/api/image", tags=["Images"])

@router.post("/to-pdf")
async def images_to_pdf(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
):
    """Combine one or more images into a single PDF (order preserved)."""
    if not files:
        raise HTTPException(400, "Please upload at least one image.")
    tmp = make_temp_dir()
    try:
        jpeg_paths: list[str] = []
        for i, f in enumerate(files):
            data = await validate_upload(f, ACCEPTED_IMAGE_EXTENSIONS)
            img = Image.open(io.BytesIO(data))
            if img.mode != "RGB":
                img = img.convert("RGB")
            jpeg_path = tmp / f"{i:04d}.jpg"
            img.save(str(jpeg_path), format="JPEG", quality=95)
            jpeg_paths.append(str(jpeg_path))

        out_path = safe_output_path(tmp, "images.pdf")
        with open(out_path, "wb") as fh:
            fh.write(img2pdf.convert(jpeg_paths))

        background_tasks.add_task(cleanup_temp_dir, tmp)
        return FileResponse(str(out_path), media_type="application/pdf",
                            filename="images.pdf")
    except HTTPException:
        cleanup_temp_dir(tmp)
        raise
    except Exception as exc:
        cleanup_temp_dir(tmp)
        raise HTTPException(500, f"Conversion failed: {exc}") from exc

