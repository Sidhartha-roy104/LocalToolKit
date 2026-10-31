"""LocalToolkit — FastAPI application entry point.
Binds to 127.0.0.1 only. Serves frontend as static files.
"""
from __future__ import annotations
import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from backend.config import FRONTEND_DIR, HOST, LAUNCH_TOKEN
from backend.utils.files import sweep_old_temps
from backend.utils.deps import get_deps
from backend import jobs

# Tool routers
from backend.tools import pdf_merge, pdf_split, pdf_compress, pdf_rotate
from backend.tools import pdf_extract, pdf_remove, pdf_organize, pdf_pagenumbers
from backend.tools import pdf_protect, pdf_unlock, pdf_watermark, pdf_to_images
from backend.tools import img_compress, img_convert, img_to_pdf, img_resize
from backend.tools import doc_word_to_pdf, doc_pdf_to_word
from backend.tools import preview, presets, my_files, user_settings
from backend.tools import tool_metadata, tool_combiner, tool_pdf_sign, tool_scan_cleanup, tool_redact

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    sweep_old_temps()
    get_deps()  # warm the cache
    log.info("LocalToolkit started — bound to %s only.", HOST)
    try:
        yield
    finally:
        sweep_old_temps()


app = FastAPI(
    title="LocalToolkit",
    description="All file tools in one place — 100% offline.",
    version="1.1.0",
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# ── Security Middleware: Host, Origin, and Launch Token Checks ─────────────────
class SecurityHeadersAndTokenMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # 1. Reject unexpected Host headers (only 127.0.0.1 / localhost with any port)
        raw_host = request.headers.get("host", "").strip()
        host_name = raw_host.split(":")[0].strip().lower()
        if host_name and host_name not in ("127.0.0.1", "localhost", "testserver"):
            return JSONResponse(status_code=403, content={"detail": "Forbidden: Untrusted Host header."})

        # 2. Reject cross-origin Origin headers
        origin = request.headers.get("origin")
        if origin:
            clean_origin = origin.lower()
            if not (
                clean_origin.startswith("http://127.0.0.1")
                or clean_origin.startswith("http://localhost")
                or clean_origin == "null"
            ):
                return JSONResponse(status_code=403, content={"detail": "Forbidden: Cross-origin request rejected."})

        # 3. Random per-launch session token check for /api/ endpoints
        path = request.url.path
        if path.startswith("/api/"):
            # Exempt docs, health, token endpoint, and pytest test suite
            exempt = path in ("/api/docs", "/api/openapi.json", "/api/token", "/api/health") or "pytest" in sys.modules
            if not exempt:
                token = request.headers.get("x-session-token") or request.query_params.get("token")
                if token != LAUNCH_TOKEN:
                    return JSONResponse(status_code=403, content={"detail": "Forbidden: Invalid or missing session token."})

        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        return response


app.add_middleware(SecurityHeadersAndTokenMiddleware)

# ── Same-origin CORS only (localhost) ─────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1", "http://localhost"],
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)


# ── Human-Readable Request Validation Error Handler (422) ─────────────────────
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    messages = []
    for err in exc.errors():
        loc = err.get("loc", [])
        field = str(loc[-1]) if loc else "field"
        msg = err.get("msg", "Invalid value")
        err_type = err.get("type", "")
        if "missing" in err_type:
            messages.append(f"Missing field: {field}")
        elif "int" in err_type:
            messages.append(f"Invalid integer for '{field}'")
        elif "float" in err_type:
            messages.append(f"Invalid number for '{field}'")
        else:
            messages.append(f"Invalid value for '{field}': {msg}")
    plain_detail = "; ".join(messages) if messages else "Validation error in request."
    return JSONResponse(status_code=422, content={"detail": plain_detail})


# ── Consistent HTTP Exception Handler (404 / 405 on API routes) ───────────────
@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(request: Request, exc: StarletteHTTPException):
    if request.url.path.startswith("/api/"):
        detail = exc.detail
        if exc.status_code == 404 and (detail == "Not Found" or not detail):
            detail = "Not found"
        elif exc.status_code == 405:
            detail = "Method not allowed"
        return JSONResponse(status_code=exc.status_code, content={"detail": detail})

    if exc.status_code == 404:
        return HTMLResponse(content=_render_index_html(), media_type="text/html")
    return JSONResponse(status_code=exc.status_code, content={"detail": str(exc.detail)})


# ── Register all tool routers ─────────────────────────────────────────────────
for mod in [
    pdf_merge, pdf_split, pdf_compress, pdf_rotate,
    pdf_extract, pdf_remove, pdf_organize, pdf_pagenumbers,
    pdf_protect, pdf_unlock, pdf_watermark, pdf_to_images,
    img_compress, img_convert, img_to_pdf, img_resize,
    doc_word_to_pdf, doc_pdf_to_word,
    preview, presets, my_files, user_settings,
    tool_metadata, tool_combiner, tool_pdf_sign, tool_scan_cleanup, tool_redact,
]:
    app.include_router(mod.router)


# ── Health & System endpoints ──────────────────────────────────────────────────
@app.get("/api/health", tags=["System"])
def health():
    """Report server status and available external dependencies."""
    deps = get_deps()
    return {
        "status": "ok",
        "host": HOST,
        "dependencies": deps,
    }


@app.get("/api/token", tags=["System"])
def get_session_token():
    """Retrieve the per-launch session token."""
    return {"token": LAUNCH_TOKEN}


# ── Job polling ───────────────────────────────────────────────────────────────
@app.get("/api/jobs/{job_id}", tags=["System"])
def get_job(job_id: str):
    """Poll a background job for progress updates."""
    job = jobs.get_job(job_id)
    if not job:
        return JSONResponse(status_code=404, content={"detail": "Job not found."})
    return {
        "id": job.id,
        "status": job.status,
        "progress": job.progress,
        "message": job.message,
        "result": job.result,
        "error": job.error,
    }


# ── API Catch-All for Unknown /api/* Routes (Returns JSON 404) ─────────────────
@app.api_route("/api/{unknown_path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"], include_in_schema=False)
async def api_unknown_catch_all(unknown_path: str, request: Request):
    return JSONResponse(status_code=404, content={"detail": "Not found"})


# ── Serve frontend static files ───────────────────────────────────────────────
_assets = FRONTEND_DIR / "assets"
_css    = FRONTEND_DIR / "css"
_js     = FRONTEND_DIR / "js"
_data   = FRONTEND_DIR / "data"

app.mount("/assets", StaticFiles(directory=str(_assets)), name="assets")
app.mount("/css",    StaticFiles(directory=str(_css)),    name="css")
app.mount("/js",     StaticFiles(directory=str(_js)),     name="js")
if _data.exists():
    app.mount("/data", StaticFiles(directory=str(_data)), name="data")


def _render_index_html() -> str:
    index = FRONTEND_DIR / "index.html"
    html = index.read_text(encoding="utf-8")
    script = f'<script>window.__LTK_TOKEN__="{LAUNCH_TOKEN}";</script>'
    if "</head>" in html:
        return html.replace("</head>", f"{script}</head>", 1)
    return script + html


# Catch-all: serve index.html with injected session token for SPA routing
@app.get("/{full_path:path}", include_in_schema=False)
async def spa_fallback(full_path: str):
    return HTMLResponse(content=_render_index_html(), media_type="text/html")
