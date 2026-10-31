"""Photo + Signature Combiner — stitch photo, signature, candidate name, and date into one image."""
from __future__ import annotations
from typing import Any
import io
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from PIL import Image, ImageDraw, ImageFont

from backend.utils.files import make_temp_dir, cleanup_temp_dir, safe_output_path
from backend.utils.security import validate_upload
from backend.config import ACCEPTED_IMAGE_EXTENSIONS

router = APIRouter(prefix="/api/tools", tags=["Extra Tools"])


def _safe_int(val: Any, default: int) -> int:
    try:
        if val is None or str(val).strip() == "":
            return default
        return int(float(val))
    except Exception:
        return default


@router.post("/combine-photo-signature")
async def combine_photo_signature(
    background_tasks: BackgroundTasks,
    photo: UploadFile | None = File(None),
    signature: UploadFile | None = File(None),
    file: UploadFile | None = File(None),
    files: list[UploadFile] | None = File(None),
    name_text: str = Form(""),
    date_text: str = Form(""),
    target_width: Any = Form(350),
    target_height: Any = Form(500),
    layout: str = Form("vertical"),
    spacing: Any = Form(10),
    format: str = Form("jpg"),
    quality: Any = Form(85),
):
    """Combine photo and signature vertically with optional name/date strip."""
    tmp = make_temp_dir()
    try:
        # Resolve photo and signature from input combinations
        actual_photo = photo
        actual_sig = signature

        all_files = []
        if files:
            all_files.extend(files)
        if file:
            all_files.append(file)

        if not actual_photo and len(all_files) >= 1:
            actual_photo = all_files[0]
        if not actual_sig and len(all_files) >= 2:
            actual_sig = all_files[1]

        if not actual_photo:
            raise HTTPException(400, "Please provide at least a photograph.")

        photo_bytes = await validate_upload(actual_photo, ACCEPTED_IMAGE_EXTENSIONS)
        photo_img = Image.open(io.BytesIO(photo_bytes)).convert("RGB")

        if actual_sig:
            sig_bytes = await validate_upload(actual_sig, ACCEPTED_IMAGE_EXTENSIONS)
            sig_img = Image.open(io.BytesIO(sig_bytes)).convert("RGB")
        else:
            # If no second file was provided, create a placeholder clean signature area
            sig_img = Image.new("RGB", (300, 100), (255, 255, 255))

        tw = _safe_int(target_width, 350)
        th = _safe_int(target_height, 500)
        q = _safe_int(quality, 85)

        w = max(200, tw)
        h = max(250, th)

        # Height partitioning: photo ~65%, signature ~25%, text strip ~10%
        has_text = bool(name_text.strip() or date_text.strip())
        text_h = 45 if has_text else 0
        sig_h = int((h - text_h) * 0.30)
        photo_h = h - text_h - sig_h

        fitted_photo = photo_img.resize((w, photo_h), Image.Resampling.LANCZOS)
        fitted_sig = sig_img.resize((w, sig_h), Image.Resampling.LANCZOS)

        canvas = Image.new("RGB", (w, h), (255, 255, 255))
        canvas.paste(fitted_photo, (0, 0))

        # Divider line
        draw = ImageDraw.Draw(canvas)
        draw.line([(0, photo_h), (w, photo_h)], fill=(220, 220, 220), width=1)

        y_cursor = photo_h
        if has_text:
            text_lines = []
            if name_text.strip():
                text_lines.append(f"NAME: {name_text.strip().upper()}")
            if date_text.strip():
                text_lines.append(f"DOB/DOP: {date_text.strip()}")

            # Render text box on white background
            draw.rectangle([(0, y_cursor), (w, y_cursor + text_h)], fill=(255, 255, 255))
            txt_y = y_cursor + 4
            for line in text_lines:
                draw.text((w // 2, txt_y), line, fill=(20, 20, 20), anchor="mt")
                txt_y += 18

            y_cursor += text_h
            draw.line([(0, y_cursor), (w, y_cursor)], fill=(220, 220, 220), width=1)

        canvas.paste(fitted_sig, (0, y_cursor))

        out_name = "combined_photo_sig.jpg"
        out_path = safe_output_path(tmp, out_name)
        canvas.save(str(out_path), "JPEG", quality=max(20, min(95, q)), optimize=True)

        background_tasks.add_task(cleanup_temp_dir, tmp)
        return FileResponse(str(out_path), media_type="image/jpeg", filename=out_name)
    except HTTPException:
        cleanup_temp_dir(tmp)
        raise
    except Exception as exc:
        cleanup_temp_dir(tmp)
        raise HTTPException(500, f"Failed to combine photo and signature: {exc}") from exc
