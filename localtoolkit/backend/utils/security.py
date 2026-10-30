"""Security helpers: size limits, extension checks, magic-byte validation."""
from __future__ import annotations
import struct
from pathlib import Path
from fastapi import UploadFile, HTTPException
from backend.config import MAX_UPLOAD_BYTES

# Magic-byte signatures  (offset, bytes)
_MAGIC: dict[str, tuple[int, bytes]] = {
    ".pdf":  (0, b"%PDF"),
    ".jpg":  (0, b"\xff\xd8\xff"),
    ".jpeg": (0, b"\xff\xd8\xff"),
    ".png":  (0, b"\x89PNG"),
    ".webp": (8, b"WEBP"),
    ".bmp":  (0, b"BM"),
    ".heic": (4, b"ftyp"),
    ".heif": (4, b"ftyp"),
    ".docx": (0, b"PK"),   # ZIP-based
    ".doc":  (0, b"\xd0\xcf"),
    ".odt":  (0, b"PK"),
    ".rtf":  (0, b"{\\rtf"),
}


async def validate_upload(file: UploadFile, allowed_extensions: set[str]) -> bytes:
    """
    Read the full file, validate size, extension, and magic bytes.
    Returns the raw bytes so callers don't re-read.
    Raises HTTPException on any violation.
    """
    data = await file.read()

    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"File exceeds {MAX_UPLOAD_BYTES // 1024 // 1024} MB limit.")

    ext = Path(file.filename or "").suffix.lower()
    if ext not in allowed_extensions:
        raise HTTPException(415, f"Unsupported file type '{ext}'.")

    magic = _MAGIC.get(ext)
    if magic:
        offset, sig = magic
        if data[offset: offset + len(sig)] != sig:
            raise HTTPException(415, "File content does not match its extension.")

    return data

