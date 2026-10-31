"""PDF Protect — add a user password to a PDF."""
from __future__ import annotations
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
import fitz
from backend.utils.files import make_temp_dir, cleanup_temp_dir, safe_output_path
from backend.utils.security import validate_upload
from backend.config import ACCEPTED_PDF_EXTENSIONS

router = APIRouter(prefix="/api/pdf", tags=["PDF"])


@router.post("/protect")
async def protect_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile | None = File(None),
    files: list[UploadFile] | None = File(None),
    password: str = Form(""),
    user_password: str = Form(""),
):
    """Encrypt a PDF with a user password (AES-128 via PyMuPDF)."""
    actual_file = file or (files[0] if files else None)
    if not actual_file:
        raise HTTPException(400, "A PDF file is required.")

    pw = password.strip() or user_password.strip()
    if not pw:
        raise HTTPException(400, "Password cannot be empty.")

    tmp = make_temp_dir()
    try:
        data = await validate_upload(actual_file, ACCEPTED_PDF_EXTENSIONS)
        doc = fitz.open(stream=data, filetype="pdf")
        out_path = safe_output_path(tmp, "protected.pdf")
        perm = int(
            fitz.PDF_PERM_ACCESSIBILITY
            | fitz.PDF_PERM_PRINT
            | fitz.PDF_PERM_COPY
            | fitz.PDF_PERM_ANNOTATE
        )
        doc.save(
            str(out_path),
            encryption=fitz.PDF_ENCRYPT_AES_128,
            user_pw=pw,
            owner_pw=pw,
            permissions=perm,
        )
        doc.close()
        background_tasks.add_task(cleanup_temp_dir, tmp)
        return FileResponse(str(out_path), media_type="application/pdf", filename="protected.pdf")
    except HTTPException:
        cleanup_temp_dir(tmp)
        raise
    except Exception as exc:
        cleanup_temp_dir(tmp)
        raise HTTPException(500, f"Protect failed: {exc}") from exc
