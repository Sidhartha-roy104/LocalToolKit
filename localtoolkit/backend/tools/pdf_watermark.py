"""PDF Watermark — add a text watermark to every page using PyMuPDF."""
from __future__ import annotations
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
import fitz
from backend.utils.files import make_temp_dir, cleanup_temp_dir, safe_output_path
from backend.utils.security import validate_upload
from backend.config import ACCEPTED_PDF_EXTENSIONS

router = APIRouter(prefix="/api/pdf", tags=["PDF"])

@router.post("/watermark")
async def watermark_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    text: str = Form("CONFIDENTIAL"),
    opacity: float = Form(0.15),   # 0.0 – 1.0
    font_size: int = Form(48),
):
    """Stamp a diagonal text watermark on every page."""
    if not text.strip():
        raise HTTPException(400, "Watermark text cannot be empty.")
    tmp = make_temp_dir()
    try:
        data = await validate_upload(file, ACCEPTED_PDF_EXTENSIONS)
        src = tmp / "input.pdf"
        src.write_bytes(data)
        out_path = safe_output_path(tmp, "watermarked.pdf")

        doc = fitz.open(str(src))
        for page in doc:
            rect = page.rect
            tw = fitz.TextWriter(rect)
            font = fitz.Font("helv")
            # Anchor around lower-left center of page so diagonal rotation covers the middle
            center = fitz.Point(rect.width * 0.2, rect.height * 0.7)
            tw.append(
                center,
                text,
                font=font,
                fontsize=font_size,
            )
            tw.write_text(
                page,
                color=(0.5, 0.5, 0.5),
                opacity=opacity,
                morph=(center, fitz.Matrix(45)),
            )
        doc.save(str(out_path))
        doc.close()
        background_tasks.add_task(cleanup_temp_dir, tmp)
        return FileResponse(str(out_path), media_type="application/pdf",
                            filename="watermarked.pdf")
    except HTTPException:
        cleanup_temp_dir(tmp)
        raise
    except Exception as exc:
        cleanup_temp_dir(tmp)
        raise HTTPException(500, f"Watermark failed: {exc}") from exc
