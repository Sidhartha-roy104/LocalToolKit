"""Tests for the universal preview endpoints."""
from __future__ import annotations


def test_preview_pdf_thumbnails(client, pdf_bytes):
    r = client.post(
        "/api/preview/pdf-thumbnails",
        files=[("file", ("doc.pdf", pdf_bytes, "application/pdf"))],
        data={"max_pages": "5", "dpi": "54"},
    )
    assert r.status_code == 200
    data = r.json()
    assert "total_pages" in data
    assert data["total_pages"] >= 1
    assert "thumbnails" in data
    assert len(data["thumbnails"]) >= 1
    assert data["thumbnails"][0]["data"].startswith("data:image/jpeg;base64,")


def test_preview_watermark(client, pdf_bytes):
    r = client.post(
        "/api/preview/watermark",
        files=[("file", ("doc.pdf", pdf_bytes, "application/pdf"))],
        data={"text": "PREVIEW", "opacity": "0.3", "font_size": "28", "angle": "45"},
    )
    assert r.status_code == 200
    data = r.json()
    assert "data" in data
    assert data["data"].startswith("data:image/jpeg;base64,")


def test_preview_page_numbers(client, pdf_bytes):
    r = client.post(
        "/api/preview/page-numbers",
        files=[("file", ("doc.pdf", pdf_bytes, "application/pdf"))],
        data={"position": "bottom-center", "start": "1", "font_size": "12"},
    )
    assert r.status_code == 200
    data = r.json()
    assert "data" in data
    assert data["data"].startswith("data:image/jpeg;base64,")


def test_preview_doc_page_graceful_when_missing(client):
    r = client.post(
        "/api/preview/doc-page",
        files=[("file", ("test.docx", b"fake docx content", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"))],
    )
    assert r.status_code in (200, 415)

