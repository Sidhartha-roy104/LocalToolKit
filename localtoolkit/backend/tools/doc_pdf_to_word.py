"""PDF to Word — convert a PDF to DOCX using pdf2docx."""
from __future__ import annotations
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from pdf2docx import Converter
from backend.utils.files import make_temp_dir, cleanup_temp_dir, safe_output_path
from backend.utils.security import validate_upload
from backend.config import ACCEPTED_PDF_EXTENSIONS

router = APIRouter(prefix="/api/doc", tags=["Documents"])


@router.post("/pdf-to-word")
async def pdf_to_word(
    background_tasks: BackgroundTasks,
    file: UploadFile | None = File(None),
    files: list[UploadFile] | None = File(None),
):
    """
    Convert a PDF to DOCX using pdf2docx.
    Note: Complex layouts (tables, columns, special fonts) may need manual cleanup.
    """
    actual_file = file or (files[0] if files else None)
    if not actual_file:
        raise HTTPException(400, "A PDF file is required.")

    tmp = make_temp_dir()
    try:
        data = await validate_upload(actual_file, ACCEPTED_PDF_EXTENSIONS)
        src = tmp / "input.pdf"
        src.write_bytes(data)
        out_path = safe_output_path(tmp, "converted.docx")

        cv = Converter(str(src))
        cv.convert(str(out_path), start=0, end=None)
        cv.close()

        background_tasks.add_task(cleanup_temp_dir, tmp)
        return FileResponse(
            str(out_path),
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            filename="converted.docx",
        )
    except HTTPException:
        cleanup_temp_dir(tmp)
        raise
    except Exception as exc:
        cleanup_temp_dir(tmp)
        raise HTTPException(500, f"PDF to Word conversion failed: {exc}") from exc
