"""PDF Split — split a PDF by page ranges or into individual pages."""
from __future__ import annotations
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, StreamingResponse
from pypdf import PdfWriter, PdfReader
from pathlib import Path
import io
import zipfile
from backend.utils.files import make_temp_dir, cleanup_temp_dir, safe_output_path
from backend.utils.security import validate_upload
from backend.config import ACCEPTED_PDF_EXTENSIONS

router = APIRouter(prefix="/api/pdf", tags=["PDF"])


def _parse_ranges(spec: str, total: int) -> list[list[int]]:
    """
    Parse a range spec like "1-3,5,7-9" into lists of 0-based page indices.
    Returns a list of groups, each group is one output file.
    """
    groups: list[list[int]] = []
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-", 1)
            start, end = int(a) - 1, int(b) - 1
            if start < 0 or end >= total or start > end:
                raise ValueError(f"Invalid range: {part}")
            groups.append(list(range(start, end + 1)))
        elif part:
            idx = int(part) - 1
            if idx < 0 or idx >= total:
                raise ValueError(f"Invalid page: {part}")
            groups.append([idx])
    return groups


@router.post("/split")
async def split_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile | None = File(None),
    files: list[UploadFile] | None = File(None),
    ranges: str = Form(""),          # e.g. "1-3,5,7-9" — empty = one page each
    pages: str = Form(""),
    mode: str = Form(""),
):
    """Split a PDF by page ranges. Empty ranges = one file per page."""
    actual_file = file or (files[0] if files else None)
    if not actual_file:
        raise HTTPException(400, "A PDF file is required to split.")

    tmp = make_temp_dir()
    try:
        data = await validate_upload(actual_file, ACCEPTED_PDF_EXTENSIONS)
        src = tmp / "input.pdf"
        src.write_bytes(data)
        reader = PdfReader(str(src))
        total = len(reader.pages)

        range_spec = ranges.strip() or pages.strip()
        if range_spec:
            groups = _parse_ranges(range_spec, total)
        else:
            groups = [[i] for i in range(total)]

        out_dir = tmp / "split"
        out_dir.mkdir(exist_ok=True)
        out_files: list[Path] = []
        for i, group in enumerate(groups, 1):
            writer = PdfWriter()
            for pg in group:
                writer.add_page(reader.pages[pg])
            fname = f"part_{i:03d}.pdf"
            out_path = safe_output_path(out_dir, fname)
            with open(out_path, "wb") as fh:
                writer.write(fh)
            out_files.append(out_path)

        # If single output, return directly; else zip
        if len(out_files) == 1:
            background_tasks.add_task(cleanup_temp_dir, tmp)
            return FileResponse(str(out_files[0]), media_type="application/pdf",
                                filename="split.pdf")

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in out_files:
                zf.write(f, f.name)
        buf.seek(0)
        background_tasks.add_task(cleanup_temp_dir, tmp)
        return StreamingResponse(buf, media_type="application/zip",
                                 headers={"Content-Disposition": 'attachment; filename="split_pages.zip"'})
    except (HTTPException, ValueError) as exc:
        cleanup_temp_dir(tmp)
        if isinstance(exc, ValueError):
            raise HTTPException(400, str(exc))
        raise
    except Exception as exc:
        cleanup_temp_dir(tmp)
        raise HTTPException(500, f"Split failed: {exc}") from exc
