"""Image Resize & Crop Tool — resize with crop and physical unit conversion (px, cm, mm, in at DPI)."""
from __future__ import annotations
from typing import Any
import io
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from PIL import Image
import pillow_heif

pillow_heif.register_heif_opener()

from backend.utils.files import make_temp_dir, cleanup_temp_dir, safe_output_path, sanitize_filename
from backend.utils.security import validate_upload
from backend.config import ACCEPTED_IMAGE_EXTENSIONS

router = APIRouter(prefix="/api/image", tags=["Image"])


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


def _to_pixels(val: float, unit: str, dpi: int) -> int:
    """Convert a value in unit (px, cm, mm, in) to pixels at given DPI."""
    unit = unit.lower().strip()
    if unit == "cm":
        return max(1, round(val * dpi / 2.54))
    elif unit == "mm":
        return max(1, round(val * dpi / 25.4))
    elif unit == "in":
        return max(1, round(val * dpi))
    return max(1, round(val))  # px default


@router.post("/resize-crop")
async def resize_crop_image(
    background_tasks: BackgroundTasks,
    file: UploadFile | None = File(None),
    files: list[UploadFile] | None = File(None),
    crop_x: Any = Form(0),
    crop_y: Any = Form(0),
    crop_w: Any = Form(0),
    crop_h: Any = Form(0),
    width: Any = Form(0),
    height: Any = Form(0),
    target_w: Any = Form(0),
    target_h: Any = Form(0),
    unit: str = Form("px"),
    dpi: Any = Form(150),
    fmt: str = Form("jpg"),
    output_format: str = Form(""),
    quality: Any = Form(85),
):
    """Crop and resize image with unit conversion and DPI preservation."""
    actual_file = file or (files[0] if files else None)
    if not actual_file:
        raise HTTPException(400, "An image file is required.")

    cx = _safe_int(crop_x, 0)
    cy = _safe_int(crop_y, 0)
    cw = _safe_int(crop_w, 0)
    ch = _safe_int(crop_h, 0)

    w_val = _safe_float(width, 0)
    h_val = _safe_float(height, 0)
    tw_val = _safe_float(target_w, 0)
    th_val = _safe_float(target_h, 0)
    dpi_val = max(72, min(600, _safe_int(dpi, 150)))
    q_val = max(10, min(100, _safe_int(quality, 85)))

    tmp = make_temp_dir()
    try:
        data = await validate_upload(actual_file, ACCEPTED_IMAGE_EXTENSIONS)
        img = Image.open(io.BytesIO(data))

        # Handle crop if specified
        orig_w, orig_h = img.size
        if cw > 0 and ch > 0:
            cx1 = max(0, min(orig_w - 1, cx))
            cy1 = max(0, min(orig_h - 1, cy))
            cx2 = max(cx1 + 1, min(orig_w, cx + cw))
            cy2 = max(cy1 + 1, min(orig_h, cy + ch))
            img = img.crop((cx1, cy1, cx2, cy2))

        # Resolve width and height
        effective_w = w_val if w_val > 0 else tw_val
        effective_h = h_val if h_val > 0 else th_val

        # Target dimensions in pixels
        out_w = _to_pixels(effective_w, unit, dpi_val) if effective_w > 0 else img.width
        out_h = _to_pixels(effective_h, unit, dpi_val) if effective_h > 0 else img.height

        # Resize if dimensions differ
        if (out_w, out_h) != img.size:
            img = img.resize((out_w, out_h), Image.Resampling.LANCZOS)

        # Output format & color mode
        chosen_fmt = (output_format.strip() or fmt.strip() or "jpg").lower()
        out_ext = ".jpg" if chosen_fmt in ("jpg", "jpeg") else ".png"

        if out_ext == ".jpg":
            if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
                bg = Image.new("RGB", img.size, (255, 255, 255))
                if img.mode != "RGBA":
                    img = img.convert("RGBA")
                bg.paste(img, mask=img.split()[3])
                img = bg
            elif img.mode != "RGB":
                img = img.convert("RGB")

        stem = sanitize_filename(Path(actual_file.filename or "image").stem)
        out_name = f"{stem}_resized{out_ext}"
        out_path = safe_output_path(tmp, out_name)

        save_kwargs = {"dpi": (dpi_val, dpi_val)}
        if out_ext == ".jpg":
            save_kwargs["quality"] = q_val
            save_kwargs["optimize"] = True
            img.save(str(out_path), "JPEG", **save_kwargs)
            media_type = "image/jpeg"
        else:
            save_kwargs["optimize"] = True
            img.save(str(out_path), "PNG", **save_kwargs)
            media_type = "image/png"

        background_tasks.add_task(cleanup_temp_dir, tmp)
        return FileResponse(str(out_path), media_type=media_type, filename=out_name)
    except HTTPException:
        cleanup_temp_dir(tmp)
        raise
    except Exception as exc:
        cleanup_temp_dir(tmp)
        raise HTTPException(500, f"Resize/crop failed: {exc}") from exc
