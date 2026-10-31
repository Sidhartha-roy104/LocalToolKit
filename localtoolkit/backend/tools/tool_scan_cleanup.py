"""Scan Clean-up to PDF — enhance mobile phone document photos into clean, high-contrast PDFs."""
from __future__ import annotations
from typing import Any
import io
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from PIL import Image, ImageEnhance, ImageOps
import fitz

from backend.utils.files import make_temp_dir, cleanup_temp_dir, safe_output_path
from backend.utils.security import validate_upload
from backend.config import ACCEPTED_IMAGE_EXTENSIONS, ACCEPTED_PDF_EXTENSIONS

router = APIRouter(prefix="/api/tools", tags=["Extra Tools"])


def _safe_float(val: Any, default: float) -> float:
    try:
        if val is None or str(val).strip() == "":
            return default
        return float(val)
    except (ValueError, TypeError):
        return default


@router.post("/scan-cleanup")
async def scan_cleanup_to_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile | None = File(None),
    files: list[UploadFile] | None = File(None),
    contrast: Any = Form(1.8),       # 1.0 = normal, >1.0 increases contrast
    brightness: Any = Form(1.2),     # 1.0 = normal, >1.0 whitens background
    mode: str = Form("bw"),            # "bw" (black & white), "gray" (greyscale), "color"
    output_type: str = Form("pdf"),    # "pdf" or "image"
    output_format: str = Form(""),
):
    """Enhance phone camera document photos, whitening background and sharpening text into PDF or Image."""
    actual_file = file or (files[0] if files else None)
    if not actual_file:
        raise HTTPException(400, "A file is required for scan clean-up.")

    b_val = max(0.5, min(2.5, _safe_float(brightness, 1.2)))
    c_val = max(0.8, min(3.0, _safe_float(contrast, 1.8)))
    out_target = (output_format.strip() or output_type.strip() or "pdf").lower()

    tmp = make_temp_dir()
    try:
        allowed = ACCEPTED_IMAGE_EXTENSIONS | ACCEPTED_PDF_EXTENSIONS
        data = await validate_upload(actual_file, allowed)
        ext = Path(actual_file.filename or "").suffix.lower()

        images: list[Image.Image] = []
        if ext == ".pdf":
            doc = fitz.open(stream=data, filetype="pdf")
            for page in doc:
                pix = page.get_pixmap(dpi=150)
                images.append(Image.open(io.BytesIO(pix.tobytes("png"))))
            doc.close()
        else:
            images.append(Image.open(io.BytesIO(data)))

        cleaned_images: list[Image.Image] = []
        for img in images:
            enh_b = ImageEnhance.Brightness(img)
            img = enh_b.enhance(b_val)

            enh_c = ImageEnhance.Contrast(img)
            img = enh_c.enhance(c_val)

            if mode == "bw":
                gray = img.convert("L")
                table = [0 if i < 175 else 255 for i in range(256)]
                img = gray.point(table, "1")
            elif mode == "gray":
                img = img.convert("L")

            cleaned_images.append(img.convert("RGB"))

        if "image" in out_target or "jpg" in out_target or "png" in out_target:
            out_name = "cleaned_document.jpg"
            out_path = safe_output_path(tmp, out_name)
            cleaned_images[0].save(str(out_path), format="JPEG", quality=90, optimize=True)
            media_type = "image/jpeg"
        else:
            out_name = "cleaned_document.pdf"
            out_path = safe_output_path(tmp, out_name)
            cleaned_images[0].save(
                str(out_path),
                format="PDF",
                save_all=len(cleaned_images) > 1,
                append_images=cleaned_images[1:] if len(cleaned_images) > 1 else [],
                resolution=150.0,
            )
            media_type = "application/pdf"

        background_tasks.add_task(cleanup_temp_dir, tmp)
        return FileResponse(str(out_path), media_type=media_type, filename=out_name)
    except HTTPException:
        cleanup_temp_dir(tmp)
        raise
    except Exception as exc:
        cleanup_temp_dir(tmp)
        raise HTTPException(500, f"Scan clean-up failed: {exc}") from exc
