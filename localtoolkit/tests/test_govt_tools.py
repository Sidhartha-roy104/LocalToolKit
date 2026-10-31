"""
tests/test_govt_tools.py - Comprehensive tests for Indian Govt Form tools:
Resize/Crop, Size Estimation, Presets, My Files storage, Metadata Removal,
Photo+Signature Combiner, PDF Signature, Scan Clean-up, and Redact/Mask.
"""
from __future__ import annotations
import io
import json
import pytest
from PIL import Image


def _make_test_image(width: int = 400, height: int = 500, color=(100, 150, 200), fmt: str = "JPEG") -> bytes:
    img = Image.new("RGB", (width, height), color=color)
    buf = io.BytesIO()
    img.save(buf, format=fmt, quality=90)
    return buf.getvalue()


def test_resize_crop_px(client):
    img_data = _make_test_image(400, 500)
    r = client.post(
        "/api/image/resize-crop",
        files=[("file", ("photo.jpg", img_data, "image/jpeg"))],
        data={
            "crop_x": "50",
            "crop_y": "50",
            "crop_w": "200",
            "crop_h": "200",
            "target_w": "100",
            "target_h": "100",
            "unit": "px",
            "dpi": "300",
            "output_format": "jpg",
            "quality": "85",
        },
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/jpeg")
    out = Image.open(io.BytesIO(r.content))
    assert out.size == (100, 100)


def test_resize_crop_cm(client):
    img_data = _make_test_image(500, 600)
    r = client.post(
        "/api/image/resize-crop",
        files=[("file", ("passport.jpg", img_data, "image/jpeg"))],
        data={
            "target_w": "3.5",
            "target_h": "4.5",
            "unit": "cm",
            "dpi": "200",
            "output_format": "jpg",
        },
    )
    assert r.status_code == 200
    out = Image.open(io.BytesIO(r.content))
    # 3.5 cm at 200 DPI = 3.5 / 2.54 * 200 ~= 275 px
    # 4.5 cm at 200 DPI = 4.5 / 2.54 * 200 ~= 354 px
    assert 260 <= out.size[0] <= 290
    assert 340 <= out.size[1] <= 370


def test_image_estimate_size(client):
    img_data = _make_test_image(800, 800)
    r = client.post(
        "/api/image/estimate-size",
        files=[("file", ("large.jpg", img_data, "image/jpeg"))],
        data={"target_kb": "50"},
    )
    assert r.status_code == 200
    data = r.json()
    assert "original_bytes" in data
    assert "estimated_bytes" in data
    assert "reachable" in data


def test_pdf_estimate_size(client, pdf_bytes):
    r = client.post(
        "/api/pdf/estimate-size",
        files=[("file", ("doc.pdf", pdf_bytes, "application/pdf"))],
        data={"target_kb": "100"},
    )
    assert r.status_code == 200
    data = r.json()
    assert "original_bytes" in data
    assert "estimated_bytes" in data


def test_presets_list_and_save(client):
    # GET presets
    r = client.get("/api/presets")
    assert r.status_code == 200
    presets = r.json()
    assert isinstance(presets, list)
    assert len(presets) >= 5
    ids = [p["id"] for p in presets]
    assert "upsc-photo" in ids or "ssc-photo" in ids

    # POST new custom preset to list
    custom_preset = {
        "id": "test-custom-preset",
        "name": "Test Custom Preset",
        "category": "Custom",
        "doc_type": "Photo",
        "width": 350,
        "height": 450,
        "unit": "px",
        "dpi": 300,
        "format": "JPG",
        "min_kb": 20,
        "max_kb": 100,
        "notes": "Custom test notes",
    }
    updated_presets = presets + [custom_preset]
    r2 = client.post("/api/presets", json=updated_presets)
    assert r2.status_code == 200
    saved = r2.json()
    assert saved.get("status") == "ok"


def test_my_files_flow(client):
    # Check info
    r_info = client.get("/api/files/info")
    assert r_info.status_code == 200
    info = r_info.json()
    assert "root_path" in info
    assert "total_files" in info

    # Save a small file (auto-categorized by size, e.g. < 100 KB)
    content = b"Mock output file content for testing local save"
    r_save = client.post(
        "/api/files/save",
        files=[("file", ("test_result.txt", content, "text/plain"))],
        data={"folder": ""},
    )
    assert r_save.status_code == 200
    res = r_save.json()
    assert res.get("status") == "ok"
    saved_filename = res["filename"]
    saved_folder = res["folder"]

    # List files
    r_list = client.get("/api/files/list", params={"folder": saved_folder})
    assert r_list.status_code == 200
    file_list = r_list.json()
    assert isinstance(file_list, list)
    found = [f for f in file_list if f["name"] == saved_filename]
    assert len(found) == 1

    # Rename file (use unique name)
    import time
    new_name = f"renamed_test_{int(time.time())}.txt"
    r_rename = client.post(
        "/api/files/rename",
        data={"folder": saved_folder, "old_name": saved_filename, "new_name": new_name},
    )
    assert r_rename.status_code == 200

    # Delete file
    r_del = client.delete(
        "/api/files/delete",
        params={"folder": saved_folder, "filename": new_name},
    )
    assert r_del.status_code == 200


def test_tool_remove_metadata(client):
    img = Image.new("RGB", (100, 100), color=(200, 200, 200))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    raw = buf.getvalue()

    r = client.post(
        "/api/tools/remove-metadata",
        files=[("file", ("image_with_exif.jpg", raw, "image/jpeg"))],
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/jpeg")


def test_tool_combine_photo_signature(client):
    photo = _make_test_image(300, 400, color=(200, 200, 250))
    sig = _make_test_image(300, 100, color=(250, 250, 200))

    r = client.post(
        "/api/tools/combine-photo-signature",
        files=[
            ("photo", ("photo.jpg", photo, "image/jpeg")),
            ("signature", ("sig.jpg", sig, "image/jpeg")),
        ],
        data={"layout": "vertical", "spacing": "10"},
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/jpeg")
    combined = Image.open(io.BytesIO(r.content))
    assert combined.height > 400


def test_tool_pdf_sign(client, pdf_bytes):
    sig = _make_test_image(150, 50, color=(0, 0, 0), fmt="JPEG")
    r = client.post(
        "/api/tools/pdf-sign",
        files=[
            ("pdf", ("doc.pdf", pdf_bytes, "application/pdf")),
            ("signature", ("sign.jpg", sig, "image/jpeg")),
        ],
        data={"page": "1", "x": "100", "y": "100", "width": "120", "height": "40"},
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/pdf")
    assert len(r.content) > 100


def test_tool_scan_cleanup(client):
    img = _make_test_image(200, 200, color=(210, 210, 215))
    r = client.post(
        "/api/tools/scan-cleanup",
        files=[("file", ("scan.jpg", img, "image/jpeg"))],
        data={"mode": "bw", "contrast": "1.5", "brightness": "1.1", "output_type": "pdf"},
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/pdf")


def test_tool_redact(client):
    img = _make_test_image(300, 300, color=(180, 180, 180))
    r = client.post(
        "/api/tools/redact",
        files=[("file", ("doc.jpg", img, "image/jpeg"))],
        data={
            "boxes": json.dumps([{"x": 20, "y": 20, "w": 50, "h": 50}]),
            "style": "black",
        },
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/jpeg")
