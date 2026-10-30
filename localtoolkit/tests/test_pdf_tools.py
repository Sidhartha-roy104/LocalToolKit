"""Tests for PDF tools."""
from __future__ import annotations
import io, zipfile


def test_merge_pdf(client, pdf_bytes):
    r = client.post(
        "/api/pdf/merge",
        files=[
            ("files", ("a.pdf", pdf_bytes, "application/pdf")),
            ("files", ("b.pdf", pdf_bytes, "application/pdf")),
        ],
    )
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/pdf"
    assert len(r.content) > 100


def test_merge_requires_two(client, pdf_bytes):
    r = client.post(
        "/api/pdf/merge",
        files=[("files", ("a.pdf", pdf_bytes, "application/pdf"))],
    )
    assert r.status_code == 400


def test_split_pdf_all(client, pdf_bytes):
    r = client.post(
        "/api/pdf/split",
        files=[("file", ("doc.pdf", pdf_bytes, "application/pdf"))],
        data={"ranges": ""},
    )
    assert r.status_code == 200


def test_compress_pdf(client, pdf_bytes):
    r = client.post(
        "/api/pdf/compress",
        files=[("file", ("doc.pdf", pdf_bytes, "application/pdf"))],
        data={"quality": "medium"},
    )
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"


def test_rotate_pdf(client, pdf_bytes):
    r = client.post(
        "/api/pdf/rotate",
        files=[("file", ("doc.pdf", pdf_bytes, "application/pdf"))],
        data={"angle": "90", "pages": "all"},
    )
    assert r.status_code == 200


def test_extract_pages(client, pdf_bytes):
    r = client.post(
        "/api/pdf/extract",
        files=[("file", ("doc.pdf", pdf_bytes, "application/pdf"))],
        data={"pages": "1"},
    )
    assert r.status_code == 200


def test_remove_pages_fails_all(client, pdf_bytes):
    """Removing all pages should return 400."""
    r = client.post(
        "/api/pdf/remove-pages",
        files=[("file", ("doc.pdf", pdf_bytes, "application/pdf"))],
        data={"pages": "1"},
    )
    assert r.status_code == 400  # only 1 page, removing it = empty


def test_page_numbers(client, pdf_bytes):
    r = client.post(
        "/api/pdf/page-numbers",
        files=[("file", ("doc.pdf", pdf_bytes, "application/pdf"))],
        data={"position": "bottom-center", "start": "1", "font_size": "10"},
    )
    assert r.status_code == 200


def test_protect_and_unlock(client, pdf_bytes):
    # Protect
    rp = client.post(
        "/api/pdf/protect",
        files=[("file", ("doc.pdf", pdf_bytes, "application/pdf"))],
        data={"password": "test123"},
    )
    assert rp.status_code == 200
    protected = rp.content

    # Unlock
    ru = client.post(
        "/api/pdf/unlock",
        files=[("file", ("protected.pdf", protected, "application/pdf"))],
        data={"password": "test123"},
    )
    assert ru.status_code == 200


def test_pdf_to_images(client, pdf_bytes):
    r = client.post(
        "/api/pdf/to-images",
        files=[("file", ("doc.pdf", pdf_bytes, "application/pdf"))],
        data={"fmt": "jpg", "dpi": "72"},
    )
    assert r.status_code == 200


def test_watermark_pdf(client, pdf_bytes):
    r = client.post(
        "/api/pdf/watermark",
        files=[("file", ("doc.pdf", pdf_bytes, "application/pdf"))],
        data={"text": "TEST", "opacity": "0.15", "font_size": "24"},
    )
    assert r.status_code == 200


def test_wrong_type_rejected(client, pdf_bytes):
    """Uploading a PDF as an image should be rejected."""
    r = client.post(
        "/api/image/compress",
        files=[("files", ("doc.pdf", pdf_bytes, "application/pdf"))],
        data={"quality": "75"},
    )
    assert r.status_code == 415

