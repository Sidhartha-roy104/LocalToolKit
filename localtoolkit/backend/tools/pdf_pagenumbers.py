"""PDF Add Page Numbers — stamp page numbers onto each page using PyMuPDF."""
from __future__ import annotations
from typing import Any
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
import fitz
from backend.utils.files import make_temp_dir, cleanup_temp_dir, safe_output_path
from backend.utils.security import validate_upload
from backend.config import ACCEPTED_PDF_EXTENSIONS

router = APIRouter(prefix="/api/pdf", tags=["PDF"])


def _safe_int(val: Any, default: int) -> int:
    try:
        if val is None or str(val).strip() == "":
            return default
        return int(float(val))
    except (ValueError, TypeError):
        return default


@router.post("/page-numbers")
@router.post("/pagenumbers")
async def add_page_numbers(
    background_tasks: BackgroundTasks,
    file: UploadFile | None = File(None),
    files: list[UploadFile] | None = File(None),
    position: str = Form("bottom-center"),  # bottom-center | bottom-right | bottom-left | top-center | top-right
    start: Any = Form(1),
    font_size: Any = Form(10),
    format_style: str = Form("Page {n}"),
    format: str = Form(""),
):
    """Add page numbers to a PDF at the specified position with custom format."""
    actual_file = file or (files[0] if files else None)
    if not actual_file:
        raise HTTPException(400, "A PDF file is required.")

    start_num = _safe_int(start, 1)
    size = _safe_int(font_size, 10)
    fmt_pattern = format.strip() or format_style.strip() or "Page {n}"

    tmp = make_temp_dir()
    try:
        data = await validate_upload(actual_file, ACCEPTED_PDF_EXTENSIONS)
        src = tmp / "input.pdf"
        src.write_bytes(data)
        out_path = safe_output_path(tmp, "numbered.pdf")

        doc = fitz.open(str(src))
        total_pages = len(doc)
        for i, page in enumerate(doc):
            rect = page.rect
            curr_num = start_num + i
            label = fmt_pattern.replace("{n}", str(curr_num)).replace("{total}", str(total_pages))

            tw = len(label) * (size * 0.5)

            if position == "bottom-right":
                pt = fitz.Point(max(20, rect.width - tw - 30), rect.height - 20)
            elif position == "bottom-left":
                pt = fitz.Point(30, rect.height - 20)
            elif position == "top-center":
                pt = fitz.Point(max(20, (rect.width - tw) / 2), 25)
            elif position == "top-right":
                pt = fitz.Point(max(20, rect.width - tw - 30), 25)
            elif position == "top-left":
                pt = fitz.Point(30, 25)
            else:  # bottom-center
                pt = fitz.Point(max(20, (rect.width - tw) / 2), rect.height - 20)

            page.insert_text(pt, label, fontsize=size,
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
