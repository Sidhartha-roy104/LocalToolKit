"""Word to PDF — convert Word/ODT/RTF to PDF using LibreOffice headless."""
from __future__ import annotations
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
import subprocess
from pathlib import Path
from backend.utils.files import make_temp_dir, cleanup_temp_dir, sanitize_filename
from backend.utils.security import validate_upload
from backend.utils.deps import get_deps
from backend.config import ACCEPTED_DOC_EXTENSIONS

router = APIRouter(prefix="/api/doc", tags=["Documents"])


@router.post("/word-to-pdf")
async def word_to_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile | None = File(None),
    files: list[UploadFile] | None = File(None),
):
    """Convert a Word document to PDF using LibreOffice headless."""
    actual_file = file or (files[0] if files else None)
    if not actual_file:
        raise HTTPException(400, "A Word/document file is required.")

    deps = get_deps()
    if not deps["libreoffice"]:
        raise HTTPException(503, (
            "LibreOffice is not installed. "
            "Download it from https://www.libreoffice.org/download/libreoffice-fresh/ "
            "then restart LocalToolkit."
        ))
    tmp = make_temp_dir()
    try:
        data = await validate_upload(actual_file, ACCEPTED_DOC_EXTENSIONS)
        safe_name = sanitize_filename(actual_file.filename or "document.docx")
        src = tmp / safe_name
        src.write_bytes(data)

        result = subprocess.run(
            [deps["libreoffice_path"], "--headless", "--convert-to", "pdf",
             "--outdir", str(tmp), str(src)],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode != 0:
            raise HTTPException(500, "LibreOffice conversion failed. The document may be corrupt.")

        out_stem = src.stem
        out_path = tmp / f"{out_stem}.pdf"
        if not out_path.exists():
            pdfs = list(tmp.glob("*.pdf"))
            if not pdfs:
                raise HTTPException(500, "No PDF was produced. Please check the document.")
            out_path = pdfs[0]

        background_tasks.add_task(cleanup_temp_dir, tmp)
        return FileResponse(str(out_path), media_type="application/pdf",
                            filename=f"{out_stem}.pdf")
    except HTTPException:
        cleanup_temp_dir(tmp)
        raise
    except subprocess.TimeoutExpired:
        cleanup_temp_dir(tmp)
        raise HTTPException(504, "Conversion timed out. The document may be very large.")
    except Exception as exc:
        cleanup_temp_dir(tmp)
        raise HTTPException(500, f"Word to PDF failed: {exc}") from exc
