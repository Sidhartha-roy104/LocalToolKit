"""Tests for image tools."""
from __future__ import annotations
import io


def test_compress_image_jpg(client, jpg_bytes):
    r = client.post(
        "/api/image/compress",
        files=[("files", ("photo.jpg", jpg_bytes, "image/jpeg"))],
        data={"quality": "60", "max_width": "0", "max_height": "0"},
    )
    assert r.status_code == 200
    assert len(r.content) > 0


def test_compress_image_png(client, png_bytes):
    r = client.post(
        "/api/image/compress",
        files=[("files", ("img.png", png_bytes, "image/png"))],
        data={"quality": "75"},
    )
    assert r.status_code == 200


def test_compress_batch(client, jpg_bytes, png_bytes):
    r = client.post(
        "/api/image/compress",
        files=[
            ("files", ("a.jpg", jpg_bytes, "image/jpeg")),
            ("files", ("b.jpg", jpg_bytes, "image/jpeg")),
        ],
        data={"quality": "75"},
    )
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/zip"


def test_convert_image(client, jpg_bytes):
    r = client.post(
        "/api/image/convert",
        files=[("files", ("photo.jpg", jpg_bytes, "image/jpeg"))],
        data={"to_format": "png"},
    )
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"


def test_convert_to_webp(client, jpg_bytes):
    r = client.post(
        "/api/image/convert",
        files=[("files", ("photo.jpg", jpg_bytes, "image/jpeg"))],
        data={"to_format": "webp"},
    )
    assert r.status_code == 200


def test_images_to_pdf(client, jpg_bytes, png_bytes):
    r = client.post(
        "/api/image/to-pdf",
        files=[
            ("files", ("a.jpg", jpg_bytes, "image/jpeg")),
            ("files", ("b.png", png_bytes, "image/png")),
        ],
    )
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"


def test_invalid_quality(client, jpg_bytes):
    r = client.post(
        "/api/image/compress",
        files=[("files", ("photo.jpg", jpg_bytes, "image/jpeg"))],
        data={"quality": "200"},
    )
    assert r.status_code == 400

