"""PDF Rotate — rotate all or selected pages."""
from __future__ import annotations
from typing import Any
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from pypdf import PdfWriter, PdfReader
from backend.utils.files import make_temp_dir, cleanup_temp_dir, safe_output_path
from backend.utils.security import validate_upload
from backend.config import ACCEPTED_PDF_EXTENSIONS

router = APIRouter(prefix="/api/pdf", tags=["PDF"])


def _safe_int(val: Any, default: int) -> int:
    try:
        if val is None or str(val).strip() == "":
            return default
        return int(float(val))
    except (ValueError, TypeError):
        return default


@router.post("/rotate")
async def rotate_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile | None = File(None),
    files: list[UploadFile] | None = File(None),
    angle: Any = Form(90),   # 90, 180, 270
    pages: str = Form("all"),  # "all" or "1,3,5-7"
):
    """Rotate all or specific pages by angle degrees (clockwise)."""
    actual_file = file or (files[0] if files else None)
    if not actual_file:
        raise HTTPException(400, "A PDF file is required to rotate.")

    rot_angle = _safe_int(angle, 90)
    if rot_angle not in (90, 180, 270):
        rot_angle = 90

    tmp = make_temp_dir()
    try:
        data = await validate_upload(actual_file, ACCEPTED_PDF_EXTENSIONS)
        src = tmp / "input.pdf"
        src.write_bytes(data)
        reader = PdfReader(str(src))
        total = len(reader.pages)

        # Parse target page set
        p_str = pages.strip().lower() if pages else "all"
        if not p_str or p_str == "all":
            target_set = set(range(total))
        else:
            target_set = set()
            for part in p_str.split(","):
                part = part.strip()
                if "-" in part:
                    a, b = part.split("-", 1)
                    target_set.update(range(int(a) - 1, int(b)))
                elif part:
                    target_set.add(int(part) - 1)

        writer = PdfWriter()
        for i, page in enumerate(reader.pages):
            if i in target_set:
                page.rotate(rot_angle)
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
