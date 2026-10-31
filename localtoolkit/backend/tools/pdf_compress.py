"""PDF Compress — reduce PDF file size with presets or target KB estimation."""
from __future__ import annotations
from typing import Any
import io
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
import fitz  # PyMuPDF
from PIL import Image

from backend.utils.files import make_temp_dir, cleanup_temp_dir, safe_output_path
from backend.utils.security import validate_upload
from backend.config import ACCEPTED_PDF_EXTENSIONS

router = APIRouter(prefix="/api/pdf", tags=["PDF"])

_PRESETS = {
    "low":    (100, 45, True),   # quality floor of 45
    "medium": (150, 65, True),
    "high":   (200, 80, True),
}


def _safe_int(val: Any, default: int) -> int:
    try:
        if val is None or str(val).strip() == "":
            return default
        return int(float(val))
    except (ValueError, TypeError):
        return default


def compress_pdf_document(doc: fitz.Document, target_dpi: int = 150, jpeg_quality: int = 65) -> None:
    """Compress images in a PyMuPDF Document safely."""
    jpeg_quality = max(45, min(95, jpeg_quality))
    processed_xrefs: set[int] = set()

    for page in doc:
        image_list = page.get_images(full=True)
        for img_info in image_list:
            xref = img_info[0]
            smask = img_info[1]

            if xref in processed_xrefs:
                continue
            processed_xrefs.add(xref)

            try:
                orig_stream = doc.xref_stream(xref)
                orig_size = len(orig_stream) if orig_stream else 0

                pix = fitz.Pixmap(doc, xref)
                if smask > 0:
                    try:
                        mask = fitz.Pixmap(doc, smask)
                        pix = fitz.Pixmap(pix, mask)
                        mask = None
                    except Exception:
                        pass

                if pix.colorspace and pix.colorspace.n > 3:
                    try:
                        pix = fitz.Pixmap(fitz.csRGB, pix)
                    except Exception:
                        pass

                mode = "RGBA" if pix.alpha else ("RGB" if pix.n == 3 else ("L" if pix.n == 1 else "RGBA"))
                pil_img = Image.frombytes(mode, (pix.width, pix.height), pix.samples)
                pix = None

                if pil_img.mode in ("RGBA", "LA") or (pil_img.mode == "P" and "transparency" in pil_img.info):
                    bg = Image.new("RGB", pil_img.size, (255, 255, 255))
                    alpha_mask = pil_img.split()[-1] if pil_img.mode in ("RGBA", "LA") else None
                    bg.paste(pil_img, mask=alpha_mask)
                    pil_img = bg
                elif pil_img.mode == "CMYK":
                    pil_img = pil_img.convert("RGB")
                elif pil_img.mode != "RGB":
                    pil_img = pil_img.convert("RGB")

                if target_dpi > 0:
                    rects = page.get_image_rects(img_info)
                    if rects:
                        bbox = rects[0]
                        w_in = max(0.01, bbox.width / 72.0)
                        h_in = max(0.01, bbox.height / 72.0)
                        effective_dpi = max(pil_img.width / w_in, pil_img.height / h_in)
                    else:
                        effective_dpi = 150.0

                    if effective_dpi > (target_dpi * 1.05):
                        scale = target_dpi / effective_dpi
                        new_w = max(1, int(pil_img.width * scale))
                        new_h = max(1, int(pil_img.height * scale))
                        pil_img = pil_img.resize((new_w, new_h), Image.Resampling.LANCZOS)

                buf = io.BytesIO()
                pil_img.save(buf, format="JPEG", quality=jpeg_quality, optimize=True)
                compressed_bytes = buf.getvalue()

                if orig_size > 0 and len(compressed_bytes) >= orig_size:
                    continue

                page.replace_image(xref, stream=compressed_bytes)
            except Exception:
                continue


@router.post("/estimate-size")
async def estimate_pdf_size(
    file: UploadFile | None = File(None),
    files: list[UploadFile] | None = File(None),
    quality: str = Form("medium"),
    target_kb: Any = Form(0),
):
    """Estimate compressed PDF size."""
    actual_file = file or (files[0] if files else None)
    if not actual_file:
        raise HTTPException(400, "A PDF file is required.")

    kb_target = max(0, _safe_int(target_kb, 0))
    try:
        data = await validate_upload(actual_file, ACCEPTED_PDF_EXTENSIONS)
        orig_bytes = len(data)
        dpi, jpeg_q, _ = _PRESETS.get(quality, (150, 65, True))

        if kb_target > 0:
            dpi = 100 if kb_target < 300 else 150
            jpeg_q = 45 if kb_target < 300 else 60

        doc = fitz.open(stream=data, filetype="pdf")
        compress_pdf_document(doc, target_dpi=dpi, jpeg_quality=jpeg_q)
        out_bytes = doc.tobytes(garbage=4, deflate=True, clean=True)
        doc.close()

        est_len = len(out_bytes)
        reachable = True if kb_target == 0 else (est_len <= kb_target * 1024)

        return {
            "original_bytes": orig_bytes,
            "estimated_bytes": est_len,
            "reachable": reachable,
            "target_bytes": kb_target * 1024 if kb_target > 0 else 0,
        }
    except Exception as exc:
        raise HTTPException(400, f"Estimation failed: {exc}") from exc


@router.post("/compress")
async def compress_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile | None = File(None),
    files: list[UploadFile] | None = File(None),
    quality: str = Form("medium"),
    target_kb: Any = Form(0),
):
    """Compress a PDF safely by downsampling images and enabling stream deflate."""
    actual_file = file or (files[0] if files else None)
    if not actual_file:
        raise HTTPException(400, "A PDF file is required to compress.")

    kb_target = max(0, _safe_int(target_kb, 0))

    tmp = make_temp_dir()
    try:
        data = await validate_upload(actual_file, ACCEPTED_PDF_EXTENSIONS)
        src = tmp / "input.pdf"
        src.write_bytes(data)
        out_path = safe_output_path(tmp, "compressed.pdf")

        if kb_target > 0:
            target_bytes = kb_target * 1024
            steps = [(200, 80), (150, 65), (120, 55), (100, 48), (72, 45)]
            best_doc_bytes = None

            for dpi, q in steps:
                doc = fitz.open(str(src))
                compress_pdf_document(doc, target_dpi=dpi, jpeg_quality=q)
                b = doc.tobytes(garbage=4, deflate=True, clean=True)
                doc.close()
                best_doc_bytes = b
                if len(b) <= target_bytes:
                    break
            out_path.write_bytes(best_doc_bytes or data)
        else:
            q_key = quality if quality in _PRESETS else "medium"
            dpi, jpeg_q, deflate = _PRESETS[q_key]
            doc = fitz.open(str(src))
            compress_pdf_document(doc, target_dpi=dpi, jpeg_quality=jpeg_q)
            doc.save(str(out_path), garbage=4, deflate=deflate, clean=True)
            doc.close()

        background_tasks.add_task(cleanup_temp_dir, tmp)
        return FileResponse(str(out_path), media_type="application/pdf", filename="compressed.pdf")
    except HTTPException:
        cleanup_temp_dir(tmp)
        raise
    except Exception as exc:
        cleanup_temp_dir(tmp)
        raise HTTPException(500, f"Compression failed: {exc}") from exc
