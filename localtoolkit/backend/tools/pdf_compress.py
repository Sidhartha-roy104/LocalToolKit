"""PDF Compress — reduce PDF file size with transparent 3-step ladder and report."""
from __future__ import annotations
from typing import Any
import io
import json
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, StreamingResponse
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


def _safe_bool(val: Any) -> bool:
    if isinstance(val, bool):
        return val
    s = str(val).lower().strip()
    return s in ("true", "1", "yes", "on")


def analyze_pdf_breakdown(data: bytes) -> tuple[dict[str, int], int]:
    """Analyze size breakdown: images, fonts, and other objects."""
    total_len = len(data)
    img_bytes = 0
    font_bytes = 0
    seen_xrefs: set[int] = set()

    try:
        doc = fitz.open(stream=data, filetype="pdf")
        for page in doc:
            for im in page.get_images(full=True):
                xref = im[0]
                if xref not in seen_xrefs:
                    seen_xrefs.add(xref)
                    try:
                        s = doc.xref_stream(xref)
                        if s:
                            img_bytes += len(s)
                    except Exception:
                        pass
            for f in page.get_fonts(full=True):
                xref = f[0]
                if xref > 0 and xref not in seen_xrefs:
                    seen_xrefs.add(xref)
                    try:
                        s = doc.xref_stream(xref)
                        if s:
                            font_bytes += len(s)
                    except Exception:
                        pass
        doc.close()
    except Exception:
        pass

    other_bytes = max(0, total_len - img_bytes - font_bytes)
    return {"images": img_bytes, "fonts": font_bytes, "other": other_bytes}, total_len


def compress_pdf_document(doc: fitz.Document, target_dpi: int = 150, jpeg_quality: int = 65) -> None:
    """Compress images in a PyMuPDF Document safely: SMask composite, CMYK->RGB, quality floor 45."""
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


def run_compression_ladder(
    data: bytes,
    quality_preset: str = "medium",
    target_kb: int = 0,
    allow_rasterize: bool = False,
) -> tuple[bytes, dict[str, Any]]:
    """
    Execute 3-step ladder:
      Step a: Lossless cleanup
      Step b: Recompress/downsample images in steps
      Step c: Rasterize pages at decreasing DPI (if enabled as last resort)
    Returns (output_bytes, report_dict).
    """
    breakdown, orig_len = analyze_pdf_breakdown(data)
    target_bytes = target_kb * 1024 if target_kb > 0 else 0

    saved_a = 0
    saved_b = 0
    saved_c = 0

    # ── Step a: Lossless cleanup ──────────────────────────────────────────────
    doc_a = fitz.open(stream=data, filetype="pdf")
    doc_a.set_metadata({})
    bytes_a = doc_a.tobytes(garbage=4, deflate=True, clean=True)
    doc_a.close()

    saved_a = max(0, orig_len - len(bytes_a))
    curr_bytes = bytes_a if len(bytes_a) < orig_len else data

    # If target met at Step a
    if target_bytes > 0 and len(curr_bytes) <= target_bytes:
        report = {
            "original_size": orig_len,
            "final_size": len(curr_bytes),
            "target_size": target_bytes,
            "reached": True,
            "breakdown": breakdown,
            "steps_saved": {"lossless_cleanup": saved_a, "image_compression": 0, "rasterization": 0},
            "rasterize_needed": False,
            "closest_reached": len(curr_bytes),
        }
        return curr_bytes, report

    # ── Step b: Image downsampling & recompression ladder ─────────────────────
    base_step_b = curr_bytes
    if target_bytes > 0:
        ladder = [(200, 75), (150, 65), (120, 55), (100, 48), (72, 45)]
    else:
        dpi, q, _ = _PRESETS.get(quality_preset, (150, 65, True))
        ladder = [(dpi, q)]

    best_b = curr_bytes
    for dpi, q in ladder:
        doc_b = fitz.open(stream=base_step_b, filetype="pdf")
        compress_pdf_document(doc_b, target_dpi=dpi, jpeg_quality=q)
        out_b = doc_b.tobytes(garbage=4, deflate=True, clean=True)
        doc_b.close()
        if len(out_b) < len(best_b):
            best_b = out_b
        if target_bytes > 0 and len(best_b) <= target_bytes:
            break

    saved_b = max(0, len(base_step_b) - len(best_b))
    curr_bytes = best_b

    # If target met at Step b
    if target_bytes > 0 and len(curr_bytes) <= target_bytes:
        report = {
            "original_size": orig_len,
            "final_size": len(curr_bytes),
            "target_size": target_bytes,
            "reached": True,
            "breakdown": breakdown,
            "steps_saved": {"lossless_cleanup": saved_a, "image_compression": saved_b, "rasterization": 0},
            "rasterize_needed": False,
            "closest_reached": len(curr_bytes),
        }
        return curr_bytes, report

    # ── Step c: Optional rasterization (Last Resort) ──────────────────────────
    rasterize_needed = (target_bytes > 0 and len(curr_bytes) > target_bytes)
    if rasterize_needed and allow_rasterize:
        base_step_c = curr_bytes
        best_c = curr_bytes
        for r_dpi, r_q in [(150, 65), (120, 55), (100, 48), (72, 45)]:
            try:
                doc_src = fitz.open(stream=data, filetype="pdf")
                out_c = fitz.open()
                for pg in doc_src:
                    pix = pg.get_pixmap(dpi=r_dpi, alpha=False)
                    buf = io.BytesIO()
                    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                    img.save(buf, format="JPEG", quality=r_q, optimize=True)
                    new_pg = out_c.new_page(width=pg.rect.width, height=pg.rect.height)
                    new_pg.insert_image(pg.rect, stream=buf.getvalue())
                c_bytes = out_c.tobytes(garbage=4, deflate=True)
                out_c.close()
                doc_src.close()
                if len(c_bytes) < len(best_c):
                    best_c = c_bytes
                if len(best_c) <= target_bytes:
                    break
            except Exception:
                break

        saved_c = max(0, len(base_step_c) - len(best_c))
        curr_bytes = best_c

    reached = True if target_bytes == 0 else (len(curr_bytes) <= target_bytes)
    report = {
        "original_size": orig_len,
        "final_size": len(curr_bytes),
        "target_size": target_bytes,
        "reached": reached,
        "breakdown": breakdown,
        "steps_saved": {
            "lossless_cleanup": saved_a,
            "image_compression": saved_b,
            "rasterization": saved_c,
        },
        "rasterize_needed": (target_bytes > 0 and not reached and not allow_rasterize),
        "closest_reached": len(curr_bytes),
    }
    return curr_bytes, report


@router.post("/estimate-size")
async def estimate_pdf_size(
    file: UploadFile | None = File(None),
    files: list[UploadFile] | None = File(None),
    quality: str = Form("medium"),
    target_kb: Any = Form(0),
    allow_rasterize: Any = Form(False),
    rasterize: Any = Form(False),
):
    """Estimate compressed PDF size and report step savings via identical ladder."""
    actual_file = file or (files[0] if files else None)
    if not actual_file:
        raise HTTPException(400, "A PDF file is required.")

    kb_target = max(0, _safe_int(target_kb, 0))
    is_rasterize = _safe_bool(allow_rasterize) or _safe_bool(rasterize)

    try:
        data = await validate_upload(actual_file, ACCEPTED_PDF_EXTENSIONS)
        out_bytes, report = run_compression_ladder(
            data,
            quality_preset=quality,
            target_kb=kb_target,
            allow_rasterize=is_rasterize,
        )
        return {
            "original_bytes": report["original_size"],
            "estimated_bytes": report["final_size"],
            "reachable": report["reached"],
            "target_bytes": report["target_size"],
            "breakdown": report["breakdown"],
            "steps_saved": report["steps_saved"],
            "rasterize_needed": report["rasterize_needed"],
            "closest_reached": report["closest_reached"],
            "report": report,
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
    allow_rasterize: Any = Form(False),
    rasterize: Any = Form(False),
):
    """Compress PDF using ladder: lossless cleanup, image downsampling, optional rasterization."""
    actual_file = file or (files[0] if files else None)
    if not actual_file:
        raise HTTPException(400, "A PDF file is required to compress.")

    kb_target = max(0, _safe_int(target_kb, 0))
    is_rasterize = _safe_bool(allow_rasterize) or _safe_bool(rasterize)

    tmp = make_temp_dir()
    try:
        data = await validate_upload(actual_file, ACCEPTED_PDF_EXTENSIONS)
        out_bytes, report = run_compression_ladder(
            data,
            quality_preset=quality,
            target_kb=kb_target,
            allow_rasterize=is_rasterize,
        )

        out_path = safe_output_path(tmp, "compressed.pdf")
        out_path.write_bytes(out_bytes)
        background_tasks.add_task(cleanup_temp_dir, tmp)

        headers = {
            "Content-Disposition": 'attachment; filename="compressed.pdf"',
            "X-Compression-Report": json.dumps(report),
            "X-Target-Reachable": "true" if report["reached"] else "false",
        }
        if not report["reached"]:
            headers["X-Warning"] = f"Target {kb_target} KB could not be reached cleanly; closest size is {report['final_size']//1024} KB."

        return StreamingResponse(
            io.BytesIO(out_bytes),
            media_type="application/pdf",
            headers=headers,
        )
    except HTTPException:
        cleanup_temp_dir(tmp)
        raise
    except Exception as exc:
        cleanup_temp_dir(tmp)
        raise HTTPException(500, f"Compression failed: {exc}") from exc
