"""
tests/conftest.py — Shared pytest fixtures.
Creates a FastAPI test client and sample files in memory.
"""
from __future__ import annotations
import io, pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def client():
    from backend.main import app
    with TestClient(app) as c:
        yield c


def make_minimal_pdf() -> bytes:
    """Return the bytes of a minimal valid 1-page PDF."""
    return (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>endobj\n"
        b"4 0 obj<</Length 44>>stream\nBT /F1 12 Tf 100 700 Td (Hello, LocalToolkit!) Tj ET\nendstream\nendobj\n"
        b"5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\n"
        b"xref\n0 6\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n"
        b"0000000115 00000 n \n0000000274 00000 n \n0000000368 00000 n \n"
        b"trailer<</Size 6/Root 1 0 R>>\nstartxref\n441\n%%EOF\n"
    )


def make_png_1x1() -> bytes:
    """Return bytes of a valid 1×1 red PNG."""
    from PIL import Image
    img = Image.new("RGB", (100, 100), color=(255, 80, 80))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def make_jpg() -> bytes:
    """Return bytes of a small JPEG."""
    from PIL import Image
    img = Image.new("RGB", (100, 100), color=(80, 150, 200))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


@pytest.fixture
def pdf_bytes():
    return make_minimal_pdf()


@pytest.fixture
def png_bytes():
    return make_png_1x1()


@pytest.fixture
def jpg_bytes():
    return make_jpg()

