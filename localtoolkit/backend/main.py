"""
LocalToolkit — FastAPI application entry point.
Binds to 127.0.0.1 only. Serves frontend as static files.
"""
from __future__ import annotations
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from backend.config import FRONTEND_DIR, HOST
from backend.utils.files import sweep_old_temps
from backend.utils.deps import get_deps
from backend import jobs

# Tool routers
from backend.tools import pdf_merge, pdf_split, pdf_compress, pdf_rotate
from backend.tools import pdf_extract, pdf_remove, pdf_organize, pdf_pagenumbers
from backend.tools import pdf_protect, pdf_unlock, pdf_watermark, pdf_to_images
from backend.tools import img_compress, img_convert, img_to_pdf
from backend.tools import doc_word_to_pdf, doc_pdf_to_word

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
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# ── Same-origin CORS only (localhost) ────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1"],   # no wildcard
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# ── Register all tool routers ─────────────────────────────────────────────────
for mod in [
    pdf_merge, pdf_split, pdf_compress, pdf_rotate,
    pdf_extract, pdf_remove, pdf_organize, pdf_pagenumbers,
    pdf_protect, pdf_unlock, pdf_watermark, pdf_to_images,
    img_compress, img_convert, img_to_pdf,
    doc_word_to_pdf, doc_pdf_to_word,
]:
    app.include_router(mod.router)

# ── Health endpoint ───────────────────────────────────────────────────────────
@app.get("/api/health", tags=["System"])
def health():
    """Report server status and available external dependencies."""
    deps = get_deps()
    return {
        "status": "ok",
        "host": HOST,
        "dependencies": deps,
    }

# ── Job polling ───────────────────────────────────────────────────────────────
@app.get("/api/jobs/{job_id}", tags=["System"])
def get_job(job_id: str):
    """Poll a background job for progress updates."""
    job = jobs.get_job(job_id)
    if not job:
        return JSONResponse(status_code=404, content={"error": "Job not found."})
    return {
        "id": job.id,
        "status": job.status,
        "progress": job.progress,
        "message": job.message,
        "result": job.result,
        "error": job.error,
    }

# ── Serve frontend static files ───────────────────────────────────────────────
# Mount AFTER API routes so /api/* is handled first.
_assets = FRONTEND_DIR / "assets"
_css    = FRONTEND_DIR / "css"
_js     = FRONTEND_DIR / "js"

app.mount("/assets", StaticFiles(directory=str(_assets)), name="assets")
app.mount("/css",    StaticFiles(directory=str(_css)),    name="css")
app.mount("/js",     StaticFiles(directory=str(_js)),     name="js")

# Catch-all: serve index.html for hash-based SPA routing
@app.get("/{full_path:path}", include_in_schema=False)
async def spa_fallback(full_path: str):
    index = FRONTEND_DIR / "index.html"
    return FileResponse(str(index))
