"""PDF Watermark — add a text watermark to every page using PyMuPDF."""
from __future__ import annotations
from typing import Any
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
import fitz
from backend.utils.files import make_temp_dir, cleanup_temp_dir, safe_output_path
from backend.utils.security import validate_upload
from backend.config import ACCEPTED_PDF_EXTENSIONS

router = APIRouter(prefix="/api/pdf", tags=["PDF"])

_COLOR_MAP = {
    "gray": (0.5, 0.5, 0.5),
    "grey": (0.5, 0.5, 0.5),
    "red": (0.8, 0.1, 0.1),
    "blue": (0.1, 0.3, 0.8),
    "black": (0.0, 0.0, 0.0),
}


def _parse_color(c: str) -> tuple[float, float, float]:
    c_lower = c.strip().lower()
    if c_lower in _COLOR_MAP:
        return _COLOR_MAP[c_lower]
    if c_lower.startswith("#") and len(c_lower) == 7:
        try:
            r = int(c_lower[1:3], 16) / 255.0
            g = int(c_lower[3:5], 16) / 255.0
            b = int(c_lower[5:7], 16) / 255.0
            return (r, g, b)
        except Exception:
            pass
    return (0.5, 0.5, 0.5)


def _safe_float(val: Any, default: float) -> float:
    try:
        if val is None or str(val).strip() == "":
            return default
        return float(val)
    except (ValueError, TypeError):
        return default


def _safe_int(val: Any, default: int) -> int:
    try:
        if val is None or str(val).strip() == "":
            return default
        return int(float(val))
    except (ValueError, TypeError):
        return default


@router.post("/watermark")
async def watermark_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile | None = File(None),
    files: list[UploadFile] | None = File(None),
    text: str = Form("CONFIDENTIAL"),
    opacity: Any = Form(0.20),   # 0.0 – 1.0
    font_size: Any = Form(36),
    angle: Any = Form(45),
    color: str = Form("gray"),
):
    """Stamp a diagonal text watermark on every page."""
    actual_file = file or (files[0] if files else None)
    if not actual_file:
        raise HTTPException(400, "A PDF file is required.")

    watermark_text = text.strip() if text else "CONFIDENTIAL"
    if not watermark_text:
        raise HTTPException(400, "Watermark text cannot be empty.")

    op = max(0.01, min(1.0, _safe_float(opacity, 0.20)))
    f_size = max(8, min(120, _safe_int(font_size, 36)))
    rot_angle = _safe_float(angle, 45.0)
    rgb_color = _parse_color(color or "gray")

    tmp = make_temp_dir()
    try:
        data = await validate_upload(actual_file, ACCEPTED_PDF_EXTENSIONS)
        src = tmp / "input.pdf"
        src.write_bytes(data)
        out_path = safe_output_path(tmp, "watermarked.pdf")

        doc = fitz.open(str(src))
        for page in doc:
            rect = page.rect
            tw = fitz.TextWriter(rect)
            font = fitz.Font("helv")
            center = fitz.Point(rect.width * 0.2, rect.height * 0.7)
            tw.append(
                center,
                watermark_text,
                font=font,
                fontsize=f_size,
            )
            tw.write_text(
                page,
                color=rgb_color,
                opacity=op,
                morph=(center, fitz.Matrix(rot_angle)),
            )
        doc.save(str(out_path))
        doc.close()
        background_tasks.add_task(cleanup_temp_dir, tmp)
        return FileResponse(str(out_path), media_type="application/pdf",
                            filename="watermarked.pdf")
    except HTTPException:
        cleanup_temp_dir(tmp)
        raise
    except Exception as exc:
        cleanup_temp_dir(tmp)
        raise HTTPException(500, f"Watermark failed: {exc}") from exc
