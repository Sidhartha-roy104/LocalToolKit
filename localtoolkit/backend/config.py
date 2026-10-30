"""
Application configuration.
All settings are read from environment variables with sensible defaults.
No telemetry, no remote endpoints.
"""
from pathlib import Path
import tempfile, os

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
TEMP_ROOT = Path(tempfile.gettempdir()) / "localtoolkit"

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
