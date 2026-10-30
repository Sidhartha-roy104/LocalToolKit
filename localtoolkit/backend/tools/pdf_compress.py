"""PDF Compress — reduce PDF file size using PyMuPDF."""
from __future__ import annotations
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
import fitz  # PyMuPDF
from backend.utils.files import make_temp_dir, cleanup_temp_dir, safe_output_path
from backend.utils.security import validate_upload
from backend.config import ACCEPTED_PDF_EXTENSIONS

router = APIRouter(prefix="/api/pdf", tags=["PDF"])

# quality → (image_dpi, jpeg_quality, deflate)
_PRESETS = {
    "low":    (72,  40, True),
    "medium": (100, 65, True),
    "high":   (150, 82, True),
}

@router.post("/compress")
async def compress_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    quality: str = Form("medium"),  # low | medium | high
):
    """Compress a PDF by downsampling images and enabling deflate."""
    if quality not in _PRESETS:
        raise HTTPException(400, "quality must be low, medium, or high.")
    dpi, jpeg_q, deflate = _PRESETS[quality]
    tmp = make_temp_dir()
    try:
        data = await validate_upload(file, ACCEPTED_PDF_EXTENSIONS)
        src = tmp / "input.pdf"
        src.write_bytes(data)
        out_path = safe_output_path(tmp, "compressed.pdf")

        doc = fitz.open(str(src))
        # Re-compress images on every page
        for page in doc:
            for img in page.get_images(full=True):
                xref = img[0]
                pix = fitz.Pixmap(doc, xref)
                if pix.colorspace and pix.colorspace.n > 3:
                    pix = fitz.Pixmap(fitz.csRGB, pix)
                # Scale down if larger than target dpi
                w, h = pix.width, pix.height
                scale = min(1.0, dpi / 96.0)  # rough normalisation
                if scale < 1.0:
                    pix = pix.scale(scale, scale)
                img_bytes = pix.tobytes("jpeg", jpg_quality=jpeg_q)
                doc.update_stream(xref, img_bytes)
                pix = None

        doc.save(
            str(out_path),
            garbage=4,
            deflate=deflate,
            clean=True,
        )
        doc.close()
        background_tasks.add_task(cleanup_temp_dir, tmp)
        return FileResponse(str(out_path), media_type="application/pdf",
                            filename="compressed.pdf")
    except HTTPException:
        cleanup_temp_dir(tmp)
        raise
    except Exception as exc:
        cleanup_temp_dir(tmp)
        raise HTTPException(500, f"Compression failed: {exc}") from exc

