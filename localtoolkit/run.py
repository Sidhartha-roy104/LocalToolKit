"""
run.py — LocalToolkit launcher.
Finds a free port, waits until the server is ready, opens the browser automatically, starts Uvicorn.
Supports frozen mode (PyInstaller) and standard python execution.
"""
from __future__ import annotations
import os, sys, multiprocessing

# Redirect std streams if None (PyInstaller windowed mode / console=False)
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")
if sys.stdin is None:
    sys.stdin = open(os.devnull, "r")

import logging, tempfile
from pathlib import Path

# Configure file-based logging in system temp folder
log_dir = Path(tempfile.gettempdir()) / "LocalToolkit"
try:
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=str(log_dir / "app.log"),
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        force=True,
    )
except Exception:
    pass

logger = logging.getLogger("localtoolkit")

# Multiprocessing freeze support for PyInstaller Windows executables
multiprocessing.freeze_support()

# Ensure project root / bundle root is in sys.path
if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    PROJECT_ROOT = sys._MEIPASS
elif getattr(sys, "frozen", False):
    PROJECT_ROOT = os.path.dirname(sys.executable)
else:
    PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
try:
    os.chdir(PROJECT_ROOT)
except Exception:
    pass

import socket, time, threading, webbrowser, urllib.request
import uvicorn
from backend.config import HOST, DEFAULT_PORT
from backend.main import app


def find_free_port(start: int = DEFAULT_PORT, attempts: int = 50) -> int:
    """Find an available TCP port starting at `start`."""
    for port in range(start, start + attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((HOST, port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"No free port found in range {start}–{start + attempts}")


def wait_and_open_browser(url: str, timeout: float = 12.0) -> None:
    """Poll the server until ready, then open the browser."""
    def _poll_and_open():
        start_time = time.time()
        health_url = f"{url}/api/health"
        opened = False
        while time.time() - start_time < timeout:
            try:
                with urllib.request.urlopen(health_url, timeout=0.8) as resp:
                    if resp.status == 200:
                        webbrowser.open(url)
                        opened = True
                        break
            except Exception:
                time.sleep(0.15)
        if not opened:
            # Fallback open
            webbrowser.open(url)

    threading.Thread(target=_poll_and_open, daemon=True).start()


def main() -> None:
    port = find_free_port()
    url = f"http://{HOST}:{port}"
    print(f"\n{'='*50}")
    print(f"  LocalToolkit")
    print(f"  Running at: {url}")
    print(f"  Press Ctrl+C to stop.")
    print(f"{'='*50}\n")

    logger.info("LocalToolkit starting on %s", url)

    wait_and_open_browser(url)

    # Run uvicorn directly with the app instance (no string import, no reload)
    config = uvicorn.Config(
        app=app,
        host=HOST,
        port=port,
        log_level="info",
        log_config=None,
        access_log=False,
    )
    server = uvicorn.Server(config)
    server.run()


if __name__ == "__main__":
    main()
