"""Add Signature to PDF — stamp a signature image onto any PDF page."""
from __future__ import annotations
from typing import Any
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from PIL import Image, ImageDraw, ImageFont
import fitz
import io

from backend.utils.files import make_temp_dir, cleanup_temp_dir, safe_output_path
from backend.utils.security import validate_upload
from backend.config import ACCEPTED_PDF_EXTENSIONS, ACCEPTED_IMAGE_EXTENSIONS

router = APIRouter(prefix="/api/tools", tags=["Extra Tools"])


def _safe_float(val: Any, default: float) -> float:
    try:
        if val is None or str(val).strip() == "":
            return default
        return float(val)
    except (ValueError, TypeError):
        return default


def _safe_int(val: Any, default: int) -> int:
    try:
        if val is None or str(val).strip() == "":
            return default
        return int(float(val))
    except (ValueError, TypeError):
        return default


@router.post("/pdf-sign")
async def add_signature_to_pdf(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] | None = File(None),
    file: UploadFile | None = File(None),
    pdf_file: UploadFile | None = File(None),
    sig_file: UploadFile | None = File(None),
    pdf: UploadFile | None = File(None),
    signature: UploadFile | None = File(None),
    page_number: Any = Form(1),
    page: Any = Form(1),
    pos_x_pct: Any = Form(65),
    x: Any = Form(0),
    pos_y_pct: Any = Form(80),
    y: Any = Form(0),
    sig_width_pt: Any = Form(130),
    width: Any = Form(0),
    sig_height_pt: Any = Form(50),
    height: Any = Form(0),
):
    """Stamp a signature onto a specific PDF page at coordinate percentages or points."""
    tmp = make_temp_dir()
    try:
        # Resolve PDF and signature files from all possible upload combinations
        actual_pdf = pdf_file or pdf
        actual_sig = sig_file or signature

        all_uploads = []
        if files:
            all_uploads.extend(files)
        if file:
            all_uploads.append(file)

        for up in all_uploads:
            ext = Path(up.filename or "").suffix.lower()
            if ext == ".pdf":
                if not actual_pdf:
                    actual_pdf = up
            elif ext in ACCEPTED_IMAGE_EXTENSIONS:
                if not actual_sig:
                    actual_sig = up

        if not actual_pdf:
            raise HTTPException(400, "A PDF file is required to sign.")

        pdf_bytes = await validate_upload(actual_pdf, ACCEPTED_PDF_EXTENSIONS)

        # If no signature image provided, create a clean digital signature box image
        if actual_sig:
            sig_bytes = await validate_upload(actual_sig, ACCEPTED_IMAGE_EXTENSIONS)
        else:
            stamp_img = Image.new("RGBA", (300, 100), (255, 255, 255, 0))
            draw = ImageDraw.Draw(stamp_img)
            draw.rectangle([(2, 2), (297, 97)], outline=(79, 70, 229, 230), width=2)
            draw.text((15, 20), "Digitally Signed", fill=(79, 70, 229, 255))
            draw.text((15, 55), "Verified Offline - LocalToolkit", fill=(100, 100, 100, 220))
            sig_buf = io.BytesIO()
            stamp_img.save(sig_buf, format="PNG")
            sig_bytes = sig_buf.getvalue()

        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        pg_arg = _safe_int(page_number, 1)
        pg_alt = _safe_int(page, 1)
        target_page = pg_arg if pg_arg > 1 else pg_alt
        if target_page < 1 or target_page > len(doc):
            raise HTTPException(400, f"Page number {target_page} is out of range (1-{len(doc)}).")

        p = doc[target_page - 1]
        rect = p.rect

        px_val = _safe_float(pos_x_pct, 65.0)
        py_val = _safe_float(pos_y_pct, 80.0)
        x_val = _safe_float(x, 0)
        y_val = _safe_float(y, 0)

        sw_val = _safe_float(sig_width_pt, 130.0)
        w_val = _safe_float(width, 0)
        sh_val = _safe_float(sig_height_pt, 50.0)
        h_val = _safe_float(height, 0)

        sw = sw_val if sw_val > 0 else (w_val if w_val > 0 else 130.0)
        sh = sh_val if sh_val > 0 else (h_val if h_val > 0 else 50.0)

        if px_val > 0 or py_val > 0:
            x0 = (px_val / 100.0) * rect.width
            y0 = (py_val / 100.0) * rect.height
        else:
            x0 = x_val
            y0 = y_val

        x1 = min(rect.width, x0 + sw)
        y1 = min(rect.height, y0 + sh)
        sig_rect = fitz.Rect(x0, y0, x1, y1)

        p.insert_image(sig_rect, stream=sig_bytes, keep_proportion=True)

        out_name = "signed_document.pdf"
        out_path = safe_output_path(tmp, out_name)
        doc.save(str(out_path), garbage=4, deflate=True, clean=True)
        doc.close()

        background_tasks.add_task(cleanup_temp_dir, tmp)
        return FileResponse(str(out_path), media_type="application/pdf", filename=out_name)
    except HTTPException:
        cleanup_temp_dir(tmp)
        raise
    except Exception as exc:
        cleanup_temp_dir(tmp)
        raise HTTPException(500, f"Failed to sign PDF: {exc}") from exc
