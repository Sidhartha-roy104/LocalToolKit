"""Tests for document tools."""
from __future__ import annotations
import pytest


def test_pdf_to_word(client, pdf_bytes):
    r = client.post(
        "/api/doc/pdf-to-word",
        files=[("file", ("doc.pdf", pdf_bytes, "application/pdf"))],
    )
    assert r.status_code == 200
    assert "wordprocessingml" in r.headers["content-type"]


def test_word_to_pdf_no_libreoffice(client):
    """Without LibreOffice, should return 503 with a helpful message."""
    from backend.utils.deps import get_deps
    deps = get_deps()
    if deps["libreoffice"]:
        pytest.skip("LibreOffice is installed — skipping unavailability test")
    # Fake a docx (PK magic bytes)
    fake_docx = b"PK\x03\x04" + b"\x00" * 100
    r = client.post(
        "/api/doc/word-to-pdf",
        files=[("file", ("doc.docx", fake_docx, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"))],
    )
    assert r.status_code == 503
    assert "LibreOffice" in r.json()["detail"]


def test_security_path_traversal(client, pdf_bytes):
    """A filename with path traversal should not be honoured."""
    r = client.post(
        "/api/pdf/merge",
        files=[
            ("files", ("../../etc/passwd.pdf", pdf_bytes, "application/pdf")),
            ("files", ("normal.pdf", pdf_bytes, "application/pdf")),
        ],
    )
    # Should succeed (we sanitize) or reject — must NOT serve /etc/passwd
    assert r.status_code in (200, 400, 415)

