"""Preview API — generate low-res thumbnails and live stamp previews using PyMuPDF."""
from __future__ import annotations
from typing import Any
import base64
import io
import subprocess
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
import fitz  # PyMuPDF

from backend.utils.files import make_temp_dir, cleanup_temp_dir, sanitize_filename
from backend.utils.security import validate_upload
from backend.utils.deps import get_deps
from backend.config import ACCEPTED_PDF_EXTENSIONS, ACCEPTED_DOC_EXTENSIONS, ACCEPTED_IMAGE_EXTENSIONS

router = APIRouter(prefix="/api/preview", tags=["Preview"])


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


@router.post("/pdf-thumbnails")
async def preview_pdf_thumbnails(
    file: UploadFile | None = File(None),
    files: list[UploadFile] | None = File(None),
    max_pages: Any = Form(50),
    dpi: Any = Form(54),
):
    """Render fast low-res JPEG thumbnails for PDF pages (default 54 DPI for quick transfer)."""
    actual_file = file or (files[0] if files else None)
    if not actual_file:
        raise HTTPException(400, "A PDF file is required.")

    lim = max(1, _safe_int(max_pages, 50))
    res_dpi = max(36, min(150, _safe_int(dpi, 54)))

    try:
        data = await validate_upload(actual_file, ACCEPTED_PDF_EXTENSIONS)
        doc = fitz.open(stream=data, filetype="pdf")
        total_pages = len(doc)
        limit = min(total_pages, lim)

        thumbnails: list[dict] = []
        for idx in range(limit):
            page = doc[idx]
            pix = page.get_pixmap(dpi=res_dpi)
            b64_data = base64.b64encode(pix.tobytes("jpeg", jpg_quality=65)).decode("ascii")
            thumbnails.append({
                "page": idx + 1,
                "width": pix.width,
                "height": pix.height,
                "rotation": page.rotation,
                "data": f"data:image/jpeg;base64,{b64_data}",
            })
        doc.close()

        return {
            "total_pages": total_pages,
            "rendered_count": len(thumbnails),
            "thumbnails": thumbnails,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(400, f"Failed to generate thumbnails: {exc}") from exc


@router.post("/watermark")
async def preview_watermark(
    file: UploadFile | None = File(None),
    files: list[UploadFile] | None = File(None),
    text: str = Form("CONFIDENTIAL"),
    opacity: Any = Form(0.20),
    font_size: Any = Form(36),
    angle: Any = Form(45),
    color: str = Form("gray"),
):
    """Render a live preview of Page 1 with the watermark stamped."""
    actual_file = file or (files[0] if files else None)
    if not actual_file:
        raise HTTPException(400, "A PDF file is required.")

    op_val = max(0.05, min(1.0, _safe_float(opacity, 0.20)))
    fs_val = max(8, min(120, _safe_int(font_size, 36)))
    ang_val = _safe_float(angle, 45)

    try:
        data = await validate_upload(actual_file, ACCEPTED_PDF_EXTENSIONS)
        doc = fitz.open(stream=data, filetype="pdf")
        if len(doc) == 0:
            raise HTTPException(400, "PDF has no pages.")

        page = doc[0]
        rect = page.rect
        center = fitz.Point(rect.width / 2, rect.height / 2)

        # Parse color
        col = (0.5, 0.5, 0.5)
        c_low = color.strip().lower()
        if c_low == "red":
            col = (0.85, 0.15, 0.15)
        elif c_low == "blue":
            col = (0.15, 0.35, 0.85)
        elif c_low == "black":
            col = (0.1, 0.1, 0.1)

        tw = fitz.TextWriter(rect)
        font = fitz.Font("helv")

        tw.append(center, text or "CONFIDENTIAL", fontsize=fs_val, font=font)
        mat = fitz.Matrix(ang_val)
        tw.write_text(page, opacity=op_val, color=col, morph=(center, mat))

        pix = page.get_pixmap(dpi=72)
        b64_data = base64.b64encode(pix.tobytes("jpeg", jpg_quality=75)).decode("ascii")
        doc.close()

        return {
            "page": 1,
            "width": pix.width,
            "height": pix.height,
            "data": f"data:image/jpeg;base64,{b64_data}",
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(400, f"Watermark preview failed: {exc}") from exc


@router.post("/page-numbers")
async def preview_page_numbers(
    file: UploadFile | None = File(None),
    files: list[UploadFile] | None = File(None),
    position: str = Form("bottom-center"),
    start: Any = Form(1),
    font_size: Any = Form(10),
    format_style: str = Form("Page {n}"),
    format: str = Form(""),
):
    """Render a live preview of Page 1 with page number stamped."""
    actual_file = file or (files[0] if files else None)
    if not actual_file:
        raise HTTPException(400, "A PDF file is required.")

    st_val = _safe_int(start, 1)
    fs_val = max(8, min(48, _safe_int(font_size, 10)))
    fmt_pat = format.strip() or format_style.strip() or "Page {n}"

    try:
        data = await validate_upload(actual_file, ACCEPTED_PDF_EXTENSIONS)
        doc = fitz.open(stream=data, filetype="pdf")
        if len(doc) == 0:
            raise HTTPException(400, "PDF has no pages.")

        page = doc[0]
        rect = page.rect
        margin = 36
        label = fmt_pat.replace("{n}", str(st_val)).replace("{total}", str(len(doc)))

        if position == "bottom-left":
            pt = fitz.Point(margin, rect.height - margin)
        elif position == "bottom-right":
            pt = fitz.Point(rect.width - margin - (len(label) * fs_val * 0.55), rect.height - margin)
        elif position == "top-center":
            pt = fitz.Point((rect.width - (len(label) * fs_val * 0.55)) / 2, margin + fs_val)
        elif position == "top-right":
            pt = fitz.Point(rect.width - margin - (len(label) * fs_val * 0.55), margin + fs_val)
        elif position == "top-left":
            pt = fitz.Point(margin, margin + fs_val)
        else:  # bottom-center default
            pt = fitz.Point((rect.width - (len(label) * fs_val * 0.55)) / 2, rect.height - margin)

        page.insert_text(pt, label, fontsize=fs_val, color=(0.2, 0.2, 0.2))

        pix = page.get_pixmap(dpi=72)
        b64_data = base64.b64encode(pix.tobytes("jpeg", jpg_quality=75)).decode("ascii")
        doc.close()

        return {
            "page": 1,
            "width": pix.width,
            "height": pix.height,
            "data": f"data:image/jpeg;base64,{b64_data}",
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(400, f"Page number preview failed: {exc}") from exc


@router.post("/doc-page")
async def preview_doc_page(
    file: UploadFile | None = File(None),
    files: list[UploadFile] | None = File(None),
):
    """Render a first-page preview of a Word document if LibreOffice is available."""
    actual_file = file or (files[0] if files else None)
    if not actual_file:
        return {"available": False, "reason": "No document file provided"}

    deps = get_deps()
    if not deps["libreoffice"]:
        return {"available": False, "reason": "LibreOffice not installed"}

    tmp = make_temp_dir()
    try:
        data = await validate_upload(actual_file, ACCEPTED_DOC_EXTENSIONS)
        safe_name = sanitize_filename(actual_file.filename or "doc.docx")
        src = tmp / safe_name
        src.write_bytes(data)

        subprocess.run(
            [deps["libreoffice_path"], "--headless", "--convert-to", "pdf", "--outdir", str(tmp), str(src)],
            capture_output=True, text=True, timeout=60,
        )
        pdfs = list(tmp.glob("*.pdf"))
        if not pdfs:
            return {"available": False, "reason": "Conversion produced no PDF"}

        doc = fitz.open(str(pdfs[0]))
        page = doc[0]
        pix = page.get_pixmap(dpi=72)
        b64_data = base64.b64encode(pix.tobytes("jpeg", jpg_quality=75)).decode("ascii")
        doc.close()

        return {
            "available": True,
            "page": 1,
            "width": pix.width,
            "height": pix.height,
            "data": f"data:image/jpeg;base64,{b64_data}",
        }
    except Exception as exc:
        return {"available": False, "reason": str(exc)}
    finally:
        cleanup_temp_dir(tmp)
