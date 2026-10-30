"""
Application configuration.
All settings are read from environment variables with sensible defaults.
No telemetry, no remote endpoints.
"""
from pathlib import Path
import tempfile, os
from backend.utils.files import resource_path, get_temp_root

BASE_DIR = resource_path()
FRONTEND_DIR = resource_path("frontend")
TEMP_ROOT = get_temp_root()

# Server — bind to loopback only, never expose to network
HOST = "127.0.0.1"
DEFAULT_PORT = 8787

# Upload limits
MAX_UPLOAD_BYTES = int(os.getenv("LTK_MAX_UPLOAD_MB", "200")) * 1024 * 1024

# Accepted MIME types (validated via magic bytes too)
ACCEPTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif", ".bmp"}
ACCEPTED_PDF_EXTENSIONS   = {".pdf"}
ACCEPTED_DOC_EXTENSIONS   = {".docx", ".doc", ".odt", ".rtf"}

# Job store TTL (seconds) — jobs older than this are purged on startup
JOB_TTL = 3600
