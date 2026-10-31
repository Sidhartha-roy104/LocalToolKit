"""PDF Remove Pages — delete specified pages with robust validation."""
from __future__ import annotations
import io
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
import fitz  # PyMuPDF

from backend.utils.files import make_temp_dir, cleanup_temp_dir, safe_output_path
from backend.utils.security import validate_upload
from backend.config import ACCEPTED_PDF_EXTENSIONS

router = APIRouter(prefix="/api/pdf", tags=["PDF"])


@router.post("/remove-pages")
@router.post("/remove")
async def remove_pages(
    background_tasks: BackgroundTasks,
    file: UploadFile | None = File(None),
    files: list[UploadFile] | None = File(None),
    pages: str = Form(""),  # e.g. "2, 4, 6-8"
    page_numbers: str = Form(""),
):
    """Remove specific pages from a PDF. Combines ranges and validates bounds."""
    actual_file = file or (files[0] if files else None)
    if not actual_file:
        raise HTTPException(400, "A PDF file is required.")

    spec = pages.strip() or page_numbers.strip()
    if not spec:
        raise HTTPException(400, "Please specify pages to remove.")

    tmp = make_temp_dir()
    try:
        data = await validate_upload(actual_file, ACCEPTED_PDF_EXTENSIONS)
        doc = fitz.open(stream=data, filetype="pdf")
        total = len(doc)

        remove_set: set[int] = set()
        for part in spec.split(","):
            part = part.strip()
            if not part:
                continue
            if "-" in part:
                tokens = [t.strip() for t in part.split("-")]
                if len(tokens) != 2 or not tokens[0].isdigit() or not tokens[1].isdigit():
                    doc.close()
                    raise HTTPException(400, f"Invalid range format: '{part}'. Example: 2-5")
                start, end = int(tokens[0]), int(tokens[1])
                if start > end:
                    start, end = end, start  # Handle reversed range gracefully
                for p in range(start, end + 1):
                    if p < 1 or p > total:
                        doc.close()
                        raise HTTPException(400, f"Page {p} does not exist; this PDF has {total} pages.")
                    remove_set.add(p - 1)
            else:
                if not part.isdigit():
                    doc.close()
                    raise HTTPException(400, f"Invalid page number: '{part}'.")
                p = int(part)
                if p < 1 or p > total:
                    doc.close()
                    raise HTTPException(400, f"Page {p} does not exist; this PDF has {total} pages.")
                remove_set.add(p - 1)

        if not remove_set:
            doc.close()
            raise HTTPException(400, "Please specify pages to remove.")

        if len(remove_set) >= total:
            doc.close()
            raise HTTPException(400, "Cannot remove all pages — at least one must remain.")

        out_path = safe_output_path(tmp, "removed_pages.pdf")
        out_doc = fitz.open()
        out_doc.insert_pdf(doc, from_page=0, to_page=total - 1)
        # Delete pages in reverse index order
        for idx in sorted(remove_set, reverse=True):
            out_doc.delete_page(idx)

        out_doc.save(str(out_path), garbage=4, deflate=True)
        out_doc.close()
        doc.close()

        background_tasks.add_task(cleanup_temp_dir, tmp)
        return FileResponse(str(out_path), media_type="application/pdf", filename="removed_pages.pdf")
    except HTTPException:
        cleanup_temp_dir(tmp)
        raise
    except Exception as exc:
        cleanup_temp_dir(tmp)
        raise HTTPException(500, f"Remove pages failed: {exc}") from exc
