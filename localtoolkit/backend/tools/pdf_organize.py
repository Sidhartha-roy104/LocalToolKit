"""PDF Organize/Reorder Pages — reorder pages by providing a new order."""
from __future__ import annotations
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from pypdf import PdfWriter, PdfReader
from backend.utils.files import make_temp_dir, cleanup_temp_dir, safe_output_path
from backend.utils.security import validate_upload
from backend.config import ACCEPTED_PDF_EXTENSIONS

router = APIRouter(prefix="/api/pdf", tags=["PDF"])


@router.post("/organize")
async def organize_pages(
    background_tasks: BackgroundTasks,
    file: UploadFile | None = File(None),
    files: list[UploadFile] | None = File(None),
    order: str = Form(""),  # e.g. "3,1,2,4" — 1-based new order
):
    """Reorder PDF pages. Provide a comma-separated list of page numbers in the desired order."""
    actual_file = file or (files[0] if files else None)
    if not actual_file:
        raise HTTPException(400, "A PDF file is required.")

    if not order or not order.strip():
        raise HTTPException(400, "Please specify the new page order (e.g. 3, 1, 2, 4).")

    tmp = make_temp_dir()
    try:
        data = await validate_upload(actual_file, ACCEPTED_PDF_EXTENSIONS)
        src = tmp / "input.pdf"
        src.write_bytes(data)
        reader = PdfReader(str(src))
        total = len(reader.pages)

        indices = [int(x.strip()) - 1 for x in order.split(",") if x.strip()]
        if not indices:
            raise HTTPException(400, "No valid page numbers found in order.")

        invalid = [i + 1 for i in indices if i < 0 or i >= total]
        if invalid:
            raise HTTPException(400, f"Pages out of range: {invalid}")

        writer = PdfWriter()
        for i in indices:
            writer.add_page(reader.pages[i])

        out_path = safe_output_path(tmp, "organized.pdf")
        with open(out_path, "wb") as fh:
            writer.write(fh)
        background_tasks.add_task(cleanup_temp_dir, tmp)
        return FileResponse(str(out_path), media_type="application/pdf",
                            filename="organized.pdf")
    except HTTPException:
        cleanup_temp_dir(tmp)
        raise
    except Exception as exc:
        cleanup_temp_dir(tmp)
        raise HTTPException(500, f"Organize failed: {exc}") from exc
