"""PDF Unlock — remove password protection from a PDF."""
from __future__ import annotations
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
import fitz
from backend.utils.files import make_temp_dir, cleanup_temp_dir, safe_output_path
from backend.utils.security import validate_upload
from backend.config import ACCEPTED_PDF_EXTENSIONS

router = APIRouter(prefix="/api/pdf", tags=["PDF"])


@router.post("/unlock")
async def unlock_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile | None = File(None),
    files: list[UploadFile] | None = File(None),
    password: str = Form(""),
):
    """Remove password from an encrypted PDF. Provide the current password."""
    actual_file = file or (files[0] if files else None)
    if not actual_file:
        raise HTTPException(400, "A PDF file is required.")

    tmp = make_temp_dir()
    try:
        data = await validate_upload(actual_file, ACCEPTED_PDF_EXTENSIONS)
        doc = fitz.open(stream=data, filetype="pdf")
        if doc.is_encrypted:
            auth = doc.authenticate(password)
            if not auth:
                doc.close()
                raise HTTPException(403, "Incorrect password — could not unlock PDF.")
        out_path = safe_output_path(tmp, "unlocked.pdf")
        doc.save(str(out_path), encryption=fitz.PDF_ENCRYPT_NONE)
        doc.close()
        background_tasks.add_task(cleanup_temp_dir, tmp)
        return FileResponse(str(out_path), media_type="application/pdf", filename="unlocked.pdf")
    except HTTPException:
        cleanup_temp_dir(tmp)
        raise
    except Exception as exc:
        cleanup_temp_dir(tmp)
        raise HTTPException(500, f"Unlock failed: {exc}") from exc
