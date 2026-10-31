"""PDF Rotate — rotate all or selected pages with visualizer offset support."""
from __future__ import annotations
from typing import Any
import json
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
import fitz  # PyMuPDF

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
    angle: Any = Form(90),     # 90, 180, 270
    pages: str = Form("all"),  # "all", blank, or e.g. "1, 3, 5-7"
    page_rotations: str = Form(""),  # JSON dict or array of per-page offsets
):
    """Rotate pages by global angle plus optional per-page offsets from visualizer."""
    actual_file = file or (files[0] if files else None)
    if not actual_file:
        raise HTTPException(400, "A PDF file is required to rotate.")

    rot_angle = _safe_int(angle, 90) % 360

    tmp = make_temp_dir()
    try:
        data = await validate_upload(actual_file, ACCEPTED_PDF_EXTENSIONS)
        doc = fitz.open(stream=data, filetype="pdf")
        total = len(doc)

        p_str = pages.strip().lower() if pages else "all"
        if not p_str or p_str == "all":
            target_set = set(range(1, total + 1))
        else:
            target_set = set()
            for part in p_str.split(","):
                part = part.strip()
                if not part:
                    continue
                if "-" in part:
                    tokens = [t.strip() for t in part.split("-")]
                    if len(tokens) == 2 and tokens[0].isdigit() and tokens[1].isdigit():
                        start, end = int(tokens[0]), int(tokens[1])
                        if start > end:
                            start, end = end, start
                        for p in range(start, end + 1):
                            if 1 <= p <= total:
                                target_set.add(p)
                elif part.isdigit():
                    p = int(part)
                    if 1 <= p <= total:
                        target_set.add(p)

        per_page_offsets: dict[int, int] = {}
        if page_rotations and page_rotations.strip():
            try:
                parsed = json.loads(page_rotations.strip())
                if isinstance(parsed, dict):
                    for k, v in parsed.items():
                        try:
                            per_page_offsets[int(k)] = int(v) % 360
                        except Exception:
                            pass
                elif isinstance(parsed, list):
                    for item in parsed:
                        if isinstance(item, dict) and "page" in item and "rotation" in item:
                            try:
                                per_page_offsets[int(item["page"])] = int(item["rotation"]) % 360
                            except Exception:
                                pass
            except Exception:
                pass

        for i in range(total):
            p_num = i + 1
            add_rot = 0
            if p_num in target_set:
                add_rot += rot_angle
            if p_num in per_page_offsets:
                add_rot += per_page_offsets[p_num]

            if add_rot % 360 != 0:
                doc[i].set_rotation((doc[i].rotation + add_rot) % 360)

        out_path = safe_output_path(tmp, "rotated.pdf")
        doc.save(str(out_path), garbage=4, deflate=True)
        doc.close()

        background_tasks.add_task(cleanup_temp_dir, tmp)
        return FileResponse(str(out_path), media_type="application/pdf", filename="rotated.pdf")
    except HTTPException:
        cleanup_temp_dir(tmp)
        raise
    except Exception as exc:
        cleanup_temp_dir(tmp)
        raise HTTPException(500, f"Rotate failed: {exc}") from exc
