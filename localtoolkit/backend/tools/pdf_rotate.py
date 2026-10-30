"""PDF Rotate — rotate all or selected pages."""
from __future__ import annotations
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from pypdf import PdfWriter, PdfReader
from backend.utils.files import make_temp_dir, cleanup_temp_dir, safe_output_path
from backend.utils.security import validate_upload
from backend.config import ACCEPTED_PDF_EXTENSIONS

router = APIRouter(prefix="/api/pdf", tags=["PDF"])

@router.post("/rotate")
async def rotate_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    angle: int = Form(90),   # 90, 180, 270
    pages: str = Form("all"),  # "all" or "1,3,5-7"
):
    """Rotate all or specific pages by angle degrees (clockwise)."""
    if angle not in (90, 180, 270):
        raise HTTPException(400, "angle must be 90, 180, or 270.")
    tmp = make_temp_dir()
    try:
        data = await validate_upload(file, ACCEPTED_PDF_EXTENSIONS)
        src = tmp / "input.pdf"
        src.write_bytes(data)
        reader = PdfReader(str(src))
        total = len(reader.pages)

        # Parse target page set
        if pages.strip().lower() == "all":
            target_set = set(range(total))
        else:
            target_set = set()
            for part in pages.split(","):
                part = part.strip()
                if "-" in part:
                    a, b = part.split("-", 1)
                    target_set.update(range(int(a) - 1, int(b)))
                elif part:
                    target_set.add(int(part) - 1)

        writer = PdfWriter()
        for i, page in enumerate(reader.pages):
            if i in target_set:
                page.rotate(angle)
            writer.add_page(page)

        out_path = safe_output_path(tmp, "rotated.pdf")
        with open(out_path, "wb") as fh:
            writer.write(fh)
        background_tasks.add_task(cleanup_temp_dir, tmp)
        return FileResponse(str(out_path), media_type="application/pdf",
                            filename="rotated.pdf")
    except HTTPException:
        cleanup_temp_dir(tmp)
        raise
    except Exception as exc:
        cleanup_temp_dir(tmp)
        raise HTTPException(500, f"Rotate failed: {exc}") from exc

