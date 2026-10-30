"""PDF to Images — convert each page to JPG or PNG using PyMuPDF."""
from __future__ import annotations
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
import fitz, io, zipfile
from backend.utils.files import make_temp_dir, cleanup_temp_dir, safe_output_path
from backend.utils.security import validate_upload
from backend.config import ACCEPTED_PDF_EXTENSIONS

router = APIRouter(prefix="/api/pdf", tags=["PDF"])

@router.post("/to-images")
async def pdf_to_images(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    fmt: str = Form("jpg"),   # jpg | png
    dpi: int = Form(150),
):
    """Convert each PDF page to an image and return as a ZIP."""
    if fmt not in ("jpg", "png"):
        raise HTTPException(400, "fmt must be jpg or png.")
    if not (72 <= dpi <= 600):
        raise HTTPException(400, "dpi must be between 72 and 600.")
    tmp = make_temp_dir()
    try:
        data = await validate_upload(file, ACCEPTED_PDF_EXTENSIONS)
        src = tmp / "input.pdf"
        src.write_bytes(data)

        doc = fitz.open(str(src))
        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        pix_fmt = "jpeg" if fmt == "jpg" else "png"
        mime_ext = "jpg" if fmt == "jpg" else "png"
        media_type = "image/jpeg" if fmt == "jpg" else "image/png"

        if len(doc) == 1:
            # Return single image directly
            page = doc[0]
            pix = page.get_pixmap(matrix=mat)
            img_bytes = pix.tobytes(pix_fmt)
            doc.close()
            background_tasks.add_task(cleanup_temp_dir, tmp)
            return StreamingResponse(
                io.BytesIO(img_bytes),
                media_type=media_type,
                headers={"Content-Disposition": f'attachment; filename="page_1.{mime_ext}"'},
            )

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for i, page in enumerate(doc):
                pix = page.get_pixmap(matrix=mat)
                img_bytes = pix.tobytes(pix_fmt)
                zf.writestr(f"page_{i+1:03d}.{mime_ext}", img_bytes)
        doc.close()
        buf.seek(0)
        background_tasks.add_task(cleanup_temp_dir, tmp)
        return StreamingResponse(buf, media_type="application/zip",
                                 headers={"Content-Disposition": 'attachment; filename="pdf_pages.zip"'})
    except HTTPException:
        cleanup_temp_dir(tmp)
        raise
    except Exception as exc:
        cleanup_temp_dir(tmp)
        raise HTTPException(500, f"Conversion failed: {exc}") from exc

