"""PDF Extract Pages — extract a subset of pages into a new PDF."""
from __future__ import annotations
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from pypdf import PdfWriter, PdfReader
from backend.utils.files import make_temp_dir, cleanup_temp_dir, safe_output_path
from backend.utils.security import validate_upload
from backend.config import ACCEPTED_PDF_EXTENSIONS

router = APIRouter(prefix="/api/pdf", tags=["PDF"])


@router.post("/extract")
async def extract_pages(
    background_tasks: BackgroundTasks,
    file: UploadFile | None = File(None),
    files: list[UploadFile] | None = File(None),
    pages: str = Form(""),  # e.g. "1-3,5,8-10"
    page_numbers: str = Form(""),
):
    """Extract specific pages from a PDF into a new file."""
    actual_file = file or (files[0] if files else None)
    if not actual_file:
        raise HTTPException(400, "A PDF file is required to extract pages.")

    spec = pages.strip() or page_numbers.strip()
    if not spec:
        raise HTTPException(400, "Please specify page numbers to extract.")

    tmp = make_temp_dir()
    try:
        data = await validate_upload(actual_file, ACCEPTED_PDF_EXTENSIONS)
        src = tmp / "input.pdf"
        src.write_bytes(data)
        reader = PdfReader(str(src))
        total = len(reader.pages)

        indices: list[int] = []
        for part in spec.split(","):
            part = part.strip()
            if "-" in part:
                a, b = part.split("-", 1)
                indices.extend(range(int(a) - 1, int(b)))
            elif part:
                indices.append(int(part) - 1)

        invalid = [i + 1 for i in indices if i < 0 or i >= total]
        if invalid:
            raise HTTPException(400, f"Pages out of range: {invalid}")

        writer = PdfWriter()
        for i in indices:
            writer.add_page(reader.pages[i])

        out_path = safe_output_path(tmp, "extracted.pdf")
        with open(out_path, "wb") as fh:
            writer.write(fh)
        background_tasks.add_task(cleanup_temp_dir, tmp)
        return FileResponse(str(out_path), media_type="application/pdf",
                            filename="extracted.pdf")
    except HTTPException:
        cleanup_temp_dir(tmp)
        raise
    except Exception as exc:
        cleanup_temp_dir(tmp)
        raise HTTPException(500, f"Extract failed: {exc}") from exc
