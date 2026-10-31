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


def test_compress_no_image_corruption_or_black_blocks(client):
    """Regression test: verify compressed PDF does not render black blocks where transparent/masked images are."""
    import fitz
    from PIL import Image

    doc = fitz.open()
    page = doc.new_page(width=300, height=300)

    # RGBA image with red circle and transparent background
    rgba = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
    for x in range(100):
        for y in range(100):
            if (x - 50) ** 2 + (y - 50) ** 2 <= 35 ** 2:
                rgba.putpixel((x, y), (255, 30, 30, 255))
    buf = io.BytesIO()
    rgba.save(buf, format="PNG")

    page.insert_image(fitz.Rect(50, 50, 150, 150), stream=buf.getvalue())
    pdf_in = doc.tobytes()
    doc.close()

    r = client.post(
        "/api/pdf/compress",
        files=[("file", ("smask_doc.pdf", pdf_in, "application/pdf"))],
        data={"quality": "low"},
    )
    assert r.status_code == 200

    out_doc = fitz.open(stream=r.content, filetype="pdf")
    pix = out_doc[0].get_pixmap()

    # Sample the center of the red circle (should be red/white, NEVER black)
    center_pixel = pix.pixel(100, 100)
    assert center_pixel[0] > 180, f"Expected red channel > 180, got {center_pixel}"
    assert center_pixel[1] < 100 and center_pixel[2] < 100, f"Expected non-black red pixel, got {center_pixel}"

    # Verify background around circle is white, not black
    corner_pixel = pix.pixel(60, 60)
    assert corner_pixel[0] > 200 and corner_pixel[1] > 200 and corner_pixel[2] > 200, f"Expected white background, got {corner_pixel}"

    # Count dark pixels in the 100x100 image area: must not be mostly black
    dark_pixels = sum(
        1 for x in range(50, 150) for y in range(50, 150)
        if pix.pixel(x, y)[0] < 40 and pix.pixel(x, y)[1] < 40 and pix.pixel(x, y)[2] < 40
    )
    assert dark_pixels < 100, f"Image rendered as black blocks! Dark pixels count: {dark_pixels}/10000"
    out_doc.close()


