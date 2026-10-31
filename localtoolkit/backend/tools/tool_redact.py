"""Redact / Blur Area — permanently mask sensitive data (Aadhaar, address, numbers) on images & PDFs."""
from __future__ import annotations
from typing import Any
import io
import json
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from PIL import Image, ImageDraw, ImageFilter
import fitz

from backend.utils.files import make_temp_dir, cleanup_temp_dir, safe_output_path, sanitize_filename
from backend.utils.security import validate_upload
from backend.config import ACCEPTED_IMAGE_EXTENSIONS, ACCEPTED_PDF_EXTENSIONS

router = APIRouter(prefix="/api/tools", tags=["Extra Tools"])


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


@router.post("/redact")
async def redact_file(
    background_tasks: BackgroundTasks,
    file: UploadFile | None = File(None),
    files: list[UploadFile] | None = File(None),
    page_number: Any = Form(1),
    page: Any = Form(1),
    x_pct: Any = Form(20.0),        # Left position %
    y_pct: Any = Form(40.0),        # Top position %
    w_pct: Any = Form(60.0),        # Width %
    h_pct: Any = Form(8.0),         # Height %
    style: str = Form("blackout"),    # "blackout", "black", or "blur"
    boxes: str = Form(""),          # Optional JSON string of multiple boxes
):
    """Redact or blur specified bounding box area(s) on PDF or Image."""
    actual_file = file or (files[0] if files else None)
    if not actual_file:
        raise HTTPException(400, "A file is required for redaction.")

    tmp = make_temp_dir()
    try:
        ext = Path(actual_file.filename or "").suffix.lower()
        allowed = ACCEPTED_IMAGE_EXTENSIONS | ACCEPTED_PDF_EXTENSIONS
        data = await validate_upload(actual_file, allowed)
        safe_stem = Path(sanitize_filename(actual_file.filename or "redacted")).stem

        # Parse target page
        p_num = _safe_int(page_number, 1)
        p_alt = _safe_int(page, 1)
        target_page_idx = (p_num if p_num > 1 else p_alt) - 1

        # Parse boxes
        rect_list = []
        if boxes and boxes.strip():
            try:
                parsed = json.loads(boxes.strip())
                if isinstance(parsed, list):
                    for b in parsed:
                        if isinstance(b, dict):
                            rect_list.append((
                                _safe_float(b.get("x") or b.get("x_pct"), 0),
                                _safe_float(b.get("y") or b.get("y_pct"), 0),
                                _safe_float(b.get("w") or b.get("w_pct"), 20),
                                _safe_float(b.get("h") or b.get("h_pct"), 10),
                            ))
            except Exception:
                pass

        if not rect_list:
            rect_list.append((
                _safe_float(x_pct, 20.0),
                _safe_float(y_pct, 40.0),
                _safe_float(w_pct, 60.0),
                _safe_float(h_pct, 8.0),
            ))

        mask_style = style.strip().lower()
        is_blur = "blur" in mask_style

        if ext == ".pdf":
            doc = fitz.open(stream=data, filetype="pdf")
            if target_page_idx < 0 or target_page_idx >= len(doc):
                target_page_idx = 0
            page_obj = doc[target_page_idx]
            rect = page_obj.rect

            for (bx, by, bw, bh) in rect_list:
                rx0 = (bx / 100.0) * rect.width
                ry0 = (by / 100.0) * rect.height
                rx1 = min(rect.width, rx0 + (bw / 100.0) * rect.width)
                ry1 = min(rect.height, ry0 + (bh / 100.0) * rect.height)
                redact_rect = fitz.Rect(rx0, ry0, rx1, ry1)

                fill_color = (0.85, 0.85, 0.85) if is_blur else (0, 0, 0)
                page_obj.add_redact_annot(redact_rect, fill=fill_color)

            page_obj.apply_redactions()

            out_name = f"{safe_stem}_redacted.pdf"
            out_path = safe_output_path(tmp, out_name)
            doc.save(str(out_path), garbage=4, deflate=True, clean=True)
            doc.close()
            media_type = "application/pdf"
        else:
            img = Image.open(io.BytesIO(data)).convert("RGB")
            iw, ih = img.size

            for (bx, by, bw, bh) in rect_list:
                ix0 = int((bx / 100.0) * iw)
                iy0 = int((by / 100.0) * ih)
                ix1 = min(iw, ix0 + int((bw / 100.0) * iw))
                iy1 = min(ih, iy0 + int((bh / 100.0) * ih))

                if ix1 <= ix0 or iy1 <= iy0:
                    continue

                if is_blur:
                    box = (ix0, iy0, ix1, iy1)
                    region = img.crop(box)
                    blurred = region.filter(ImageFilter.GaussianBlur(radius=15))
                    img.paste(blurred, box)
                else:
                    draw = ImageDraw.Draw(img)
                    draw.rectangle([(ix0, iy0), (ix1, iy1)], fill=(0, 0, 0))

            out_name = f"{safe_stem}_redacted.jpg"
            out_path = safe_output_path(tmp, out_name)
            img.save(str(out_path), format="JPEG", quality=90, optimize=True)
            media_type = "image/jpeg"

        background_tasks.add_task(cleanup_temp_dir, tmp)
        return FileResponse(str(out_path), media_type=media_type, filename=out_name)
    except HTTPException:
        cleanup_temp_dir(tmp)
        raise
    except Exception as exc:
        cleanup_temp_dir(tmp)
        raise HTTPException(500, f"Redaction failed: {exc}") from exc
