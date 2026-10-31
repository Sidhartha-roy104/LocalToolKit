"""PDF Merge — combine multiple PDFs into one."""
from __future__ import annotations
from typing import List
import uuid
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from pypdf import PdfWriter, PdfReader
from backend.utils.files import make_temp_dir, cleanup_temp_dir, safe_output_path
from backend.utils.security import validate_upload
from backend.config import ACCEPTED_PDF_EXTENSIONS

router = APIRouter(prefix="/api/pdf", tags=["PDF"])


@router.post("/merge")
async def merge_pdf(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] | None = File(None),
    file: UploadFile | None = File(None),
):
    """Merge multiple PDF files into a single PDF (order preserved)."""
    all_files = []
    if files:
        all_files.extend(files)
    if file:
        all_files.append(file)

    if len(all_files) < 2:
        raise HTTPException(400, "Please upload at least 2 PDF files to merge.")

    tmp = make_temp_dir()
    try:
        writer = PdfWriter()
        for f in all_files:
            data = await validate_upload(f, ACCEPTED_PDF_EXTENSIONS)
            src = tmp / f"{uuid.uuid4().hex}.pdf"
            src.write_bytes(data)
            reader = PdfReader(str(src))
            for page in reader.pages:
                writer.add_page(page)
        out_name = "merged.pdf"
        out_path = safe_output_path(tmp, out_name)
        with open(out_path, "wb") as fh:
            writer.write(fh)
        background_tasks.add_task(cleanup_temp_dir, tmp)
        return FileResponse(str(out_path), media_type="application/pdf",
                            filename=out_name, background=None)
    except HTTPException:
        cleanup_temp_dir(tmp)
        raise
    except Exception as exc:
        cleanup_temp_dir(tmp)
        raise HTTPException(500, f"Merge failed: {exc}") from exc
