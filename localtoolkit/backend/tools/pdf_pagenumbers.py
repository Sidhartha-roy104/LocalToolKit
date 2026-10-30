"""PDF Add Page Numbers — stamp page numbers onto each page using PyMuPDF."""
from __future__ import annotations
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
import fitz
from backend.utils.files import make_temp_dir, cleanup_temp_dir, safe_output_path
from backend.utils.security import validate_upload
from backend.config import ACCEPTED_PDF_EXTENSIONS

router = APIRouter(prefix="/api/pdf", tags=["PDF"])

@router.post("/page-numbers")
async def add_page_numbers(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    position: str = Form("bottom-center"),  # bottom-center | bottom-right | top-center
    start: int = Form(1),
    font_size: int = Form(10),
):
    """Add page numbers to a PDF at the specified position."""
    tmp = make_temp_dir()
    try:
        data = await validate_upload(file, ACCEPTED_PDF_EXTENSIONS)
        src = tmp / "input.pdf"
        src.write_bytes(data)
        out_path = safe_output_path(tmp, "numbered.pdf")

        doc = fitz.open(str(src))
        for i, page in enumerate(doc):
            rect = page.rect
            label = str(start + i)
            if position == "bottom-center":
                pt = fitz.Point(rect.width / 2, rect.height - 20)
            elif position == "bottom-right":
                pt = fitz.Point(rect.width - 40, rect.height - 20)
            else:  # top-center
                pt = fitz.Point(rect.width / 2, 20)
            page.insert_text(pt, label, fontsize=font_size,
                             color=(0.3, 0.3, 0.3), overlay=True)
        doc.save(str(out_path))
        doc.close()
        background_tasks.add_task(cleanup_temp_dir, tmp)
        return FileResponse(str(out_path), media_type="application/pdf",
                            filename="numbered.pdf")
    except HTTPException:
        cleanup_temp_dir(tmp)
        raise
    except Exception as exc:
        cleanup_temp_dir(tmp)
        raise HTTPException(500, f"Page numbering failed: {exc}") from exc

