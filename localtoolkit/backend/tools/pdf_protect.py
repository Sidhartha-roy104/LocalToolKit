"""PDF Protect — add a user password to a PDF."""
from __future__ import annotations
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from pypdf import PdfWriter, PdfReader
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
):
    """Encrypt a PDF with a user password (AES-128)."""
    actual_file = file or (files[0] if files else None)
    if not actual_file:
        raise HTTPException(400, "A PDF file is required.")

    if not password or not password.strip():
        raise HTTPException(400, "Password cannot be empty.")

    tmp = make_temp_dir()
    try:
        data = await validate_upload(actual_file, ACCEPTED_PDF_EXTENSIONS)
        src = tmp / "input.pdf"
        src.write_bytes(data)
        reader = PdfReader(str(src))
        writer = PdfWriter()
        writer.append_pages_from_reader(reader)
        writer.encrypt(password, algorithm="AES-128")
        out_path = safe_output_path(tmp, "protected.pdf")
        with open(out_path, "wb") as fh:
            writer.write(fh)
        background_tasks.add_task(cleanup_temp_dir, tmp)
        return FileResponse(str(out_path), media_type="application/pdf",
                            filename="protected.pdf")
    except HTTPException:
        cleanup_temp_dir(tmp)
        raise
    except Exception as exc:
        cleanup_temp_dir(tmp)
        raise HTTPException(500, f"Protect failed: {exc}") from exc
