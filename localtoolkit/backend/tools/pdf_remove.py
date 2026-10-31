"""PDF Remove Pages — delete specific pages from a PDF."""
from __future__ import annotations
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from pypdf import PdfWriter, PdfReader
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
    pages: str = Form(""),  # e.g. "2,4,6-8"
    page_numbers: str = Form(""),
):
    """Remove specific pages from a PDF."""
    actual_file = file or (files[0] if files else None)
    if not actual_file:
        raise HTTPException(400, "A PDF file is required.")

    spec = pages.strip() or page_numbers.strip()
    if not spec:
        raise HTTPException(400, "Please specify pages to remove.")

    tmp = make_temp_dir()
    try:
        data = await validate_upload(actual_file, ACCEPTED_PDF_EXTENSIONS)
        src = tmp / "input.pdf"
        src.write_bytes(data)
        reader = PdfReader(str(src))
        total = len(reader.pages)

        remove_set: set[int] = set()
        for part in spec.split(","):
            part = part.strip()
            if "-" in part:
                a, b = part.split("-", 1)
                remove_set.update(range(int(a) - 1, int(b)))
            elif part:
                remove_set.add(int(part) - 1)

        keep = [i for i in range(total) if i not in remove_set]
        if not keep:
            raise HTTPException(400, "Cannot remove all pages — at least one must remain.")

        writer = PdfWriter()
        for i in keep:
            writer.add_page(reader.pages[i])

        out_path = safe_output_path(tmp, "removed_pages.pdf")
        with open(out_path, "wb") as fh:
            writer.write(fh)
        background_tasks.add_task(cleanup_temp_dir, tmp)
        return FileResponse(str(out_path), media_type="application/pdf",
                            filename="removed_pages.pdf")
    except HTTPException:
        cleanup_temp_dir(tmp)
        raise
    except Exception as exc:
        cleanup_temp_dir(tmp)
        raise HTTPException(500, f"Remove pages failed: {exc}") from exc
