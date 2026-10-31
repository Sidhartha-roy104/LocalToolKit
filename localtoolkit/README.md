# LocalToolkit 🛠️

[![100% Offline](https://img.shields.io/badge/Privacy-100%25%20Offline-2563EB?style=for-the-badge&logo=shield)](https://github.com/Sidhartha-roy104/LocalToolKit)
[![Govt Portal Presets](https://img.shields.io/badge/Govt%20Forms-UPSC%20%7C%20SSC%20%7C%20IBPS-10B981?style=for-the-badge)](https://github.com/Sidhartha-roy104/LocalToolKit)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-blue.svg?style=for-the-badge&logo=python)](https://www.python.org/)

**A beautiful, simple, 100% offline all-in-one file utility and Indian government-form helper running locally on your computer.**

Files **NEVER** leave your machine. No telemetry, no remote uploads, no account required, and zero cloud dependencies. It binds strictly to `127.0.0.1` and operates with full fidelity offline.

---

## 🇮🇳 Special Indian Government Form & Exam Portal Features

LocalToolkit is optimized for Indian exam and government portal uploads (UPSC, SSC, IBPS, GATE, Passport Seva, PAN, RRB, State PSCs):

- **🏛️ Built-in Portal Presets:** Instant 1-click presets configuring exact pixel dimensions, aspect ratio, DPI, format, and min/max KB limits.
- **🎯 Compress to Target Size:** Binary-search compression hits exact file limits (e.g. *exactly under 50 KB* or *between 20 KB - 50 KB*) with a live size estimate before downloading.
- **✂️ Interactive Live Canvas Crop:** Drag-and-drop crop handles with aspect ratio locks and live readouts in **px**, **cm**, **mm**, or **inches** at target DPI.
- **📁 "My Files" Local Auto-Organized Storage:** Output files can be saved with 1-click directly to `~/Documents/LocalToolkit/`, automatically sorted into smart folders (`Under 50 KB`, `Under 100 KB`, `Under 200 KB`, `Photos`, `Signatures`). Open directly in Windows File Explorer!
- **🌐 Multilingual & Simple Mode:** Full interface translation for **English**, **Hindi (हिन्दी)**, and **Telugu (తెలుగు)**, plus a high-contrast **Simple Mode** with larger fonts and clear instructions.

---

## 📸 Screenshots

### Light Mode & Dark Mode
| Light Mode (Clean pastel interface) | Dark Mode (Full dark theme) |
| :---: | :---: |
| ![Home Light](docs/screenshots/home-light.png) | ![Home Dark](docs/screenshots/home-dark.png) |

### Minimal-Scroll Workspace
| Two-Column Tool Workspace | Batch Processing & Reordering |
| :---: | :---: |
| ![Tool Page](docs/screenshots/tool-page.png) | ![Result State](docs/screenshots/result-state.png) |

---

## ⚡ Run in 3 Steps (Quick Start)

### Windows
1. Ensure [Python 3.11+](https://www.python.org/downloads/) is installed (check *"Add Python to PATH"* during install).
2. Double-click **`setup_and_run.bat`** (or run `.\setup_and_run.bat` from terminal).
3. The script automatically creates an isolated virtual environment, installs the lightweight dependencies, and launches your browser to `http://127.0.0.1:8787/`.

### macOS / Linux
1. Ensure Python 3.11+ is installed.
2. In terminal, run:
   ```bash
   chmod +x setup_and_run.sh
   ./setup_and_run.sh
   ```
3. Your default browser opens automatically to the LocalToolkit workspace.

---

## 🚀 Download Ready-Made Windows .exe

No Python installed? You can download the pre-packaged standalone Windows application directly from GitHub Releases:

👉 **[Download Latest LocalToolkit.exe (GitHub Releases)](https://github.com/Sidhartha-roy104/LocalToolKit/releases)**

1. Download `LocalToolkit.zip` from the latest release.
2. Extract the folder to any location on your PC.
3. Double-click **`LocalToolkit.exe`** to start.

> **🛡️ Note on Windows SmartScreen:**  
> Because this is a newly built, community open-source executable without an expensive commercial code-signing certificate, Windows Defender SmartScreen may display an alert on first launch (*"Windows protected your PC"*).  
> Click **"More info"** and then select **"Run anyway"**. LocalToolkit contains zero network access code, binds exclusively to loopback `127.0.0.1`, and processes all files in local temporary memory.

---

## 🧰 All Tools Included (22+ Tools)

### 🏛️ Govt Form & ID Tools
- **Resize & Live Crop:** Crop with live handles, aspect ratio presets (1:1, 3.5×4.5 cm, 4×2 cm), and live readouts in px/cm/mm at target DPI.
- **Photo + Signature Combiner:** Combine candidate photo and signature vertically or horizontally with name & date caption box.
- **Add Signature to PDF:** Stamp candidate signature or photo onto any PDF page with customizable coordinates and dimensions.
- **Scan Clean-up to PDF:** Turn mobile camera photos into clean, high-contrast B&W or grayscale documents with shadow suppression.
- **Redact & Mask Sensitive Details:** Permanently blackout or heavy-blur sensitive Aadhaar numbers, phone numbers, or addresses.
- **Remove Metadata & EXIF:** Strip GPS geolocation, camera model, and personal author data from photos and PDFs.

### 📄 PDF Tools
- **Merge PDF:** Combine multiple PDF documents in custom drag-and-drop order with visual thumbnails.
- **Split PDF:** Extract custom page ranges (`1-3, 5, 7-10`) or split all pages into separate PDFs.
- **Compress PDF:** Smart compression with target KB limits, live size estimation, and SMask soft-mask composite protection.
- **Rotate PDF:** Rotate all or specific pages clockwise by 90°, 180°, or 270° directly on thumbnail previews.
- **Extract Pages:** Pull specific pages out into a fresh document.
- **Remove Pages:** Delete unwanted pages from a PDF.
- **Organize Pages:** Reorder and arrange pages with intuitive drag-and-drop thumbnails.
- **Add Page Numbers:** Stamp page numbers onto headers or footers with customizable position, format, and font size.
- **Protect PDF:** Encrypt a PDF with password protection (AES-128).
- **Unlock PDF:** Remove password restriction from password-protected PDFs.
- **Watermark PDF:** Add angled, semi-transparent text watermarks across document pages with live preview.
- **PDF to JPG / PNG:** Render PDF pages into crisp high-resolution images bundled in a ZIP.

### 🖼️ Image Tools
- **Compress Image:** Target-size compression (slider + target KB input) with live debounced size estimation.
- **Convert Image:** Convert images across JPG, PNG, WEBP, and BMP formats.
- **JPG to PDF:** Convert image collections into a unified multi-page PDF document.

### 📝 Document Tools
- **Word to PDF:** Convert `.docx`, `.doc`, `.odt`, or `.rtf` documents using headless LibreOffice.
- **PDF to Word:** Convert PDFs into editable `.docx` files using `pdf2docx`.

---

## 📂 "My Files" Local Storage System

LocalToolkit includes a built-in offline file manager stored locally at:
`~/Documents/LocalToolkit/`

- **Smart Auto-Size Sorting:** Files saved from result screens are automatically routed into `Under 100 KB`, `Under 200 KB`, `Under 500 KB`, `Under 1 MB`, etc., matching exam portal criteria.
- **Dedicated Categories:** Preset folders for `Photos`, `Signatures`, and `Certificates`.
- **Integrated File Operations:** Search, filter, rename, move, and download files directly from the web interface.
- **One-Click Native Explorer:** Click **"Open Folder in Explorer"** to reveal the folder instantly in Windows File Explorer (or macOS Finder / Linux file manager).

---

## 🔌 Optional External Dependencies

LocalToolkit runs 100% standalone for all core PDF, Image, and Govt Form tools. Advanced document conversions leverage standard local tools if installed:

| Tool / Feature | External Utility | Status | Download Link |
| :--- | :--- | :--- | :--- |
| **Word to PDF** (`.docx` / `.doc` / `.odt` → `.pdf`) | **LibreOffice** (`soffice`) | *Optional* | [Download LibreOffice](https://www.libreoffice.org/download/libreoffice-fresh/) |
| **PDF PostScript processing** | **Ghostscript** (`gs`) | *Optional* | [Download Ghostscript](https://www.ghostscript.com/releases/index.html) |
| **OCR Image to Text** | **Tesseract OCR** (`tesseract`) | *Optional* | [Download Tesseract](https://github.com/UB-Mannheim/tesseract/wiki) |

> If an optional dependency is not found, LocalToolkit will **never crash** — it displays a friendly in-app status card with direct download guidance.

---

## 🔒 Security & Privacy Guarantees

> **LocalToolkit never uploads your files. Everything runs on your computer. A few tools need free helper programs (LibreOffice, Ghostscript, Tesseract). History stays on your device; pause or clear it anytime.**

1. **Loopback Only:** Strict binding to `127.0.0.1` prevents remote access over local Wi-Fi or LAN.
2. **Per-Launch Security Token:** Random cryptographic session token required on every API call to protect against unauthorized local requests.
3. **Zero Remote Requests:** No CDNs, no Google Fonts, no external JavaScript dependencies, and no remote telemetry.
4. **Strict Validation:** File sizes, extensions, and magic-byte headers are verified before processing.
5. **Path-Traversal Guard:** Strict output validation ensures files are confined to designated session directories and user-configured storage.
6. **Auto-Cleaning Temp Storage:** Work files are written to unique UUID subdirectories in the operating system's temporary directory (`%TEMP%/localtoolkit`) and cleaned up immediately after each request.

### 🔍 How to Verify Offline Privacy
- **Turn off Wi-Fi:** Disconnect your Wi-Fi or unplug your network cable, then launch LocalToolkit and run any file conversion or compression. Everything operates with 100% fidelity offline.
- **Inspect Network Traffic:** In your browser, open Developer Tools (`F12`), switch to the **Network** tab, and process files. You will observe that all requests go exclusively to `http://127.0.0.1:<port>` and zero packets are sent to third parties or remote servers.

---

## 🛠️ Developer & Manual Setup

### Clone and Install
```bash
git clone https://github.com/Sidhartha-roy104/LocalToolKit.git
cd LocalToolKit
python -m venv venv

# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

pip install -r requirements.txt
```

### Run Locally
```bash
python run.py
```

### Running Tests
```bash
python -m pytest tests/test_govt_tools.py tests/test_preview.py -v
```

---

## 📜 License

Distributed under the [MIT License](LICENSE). Copyright &copy; 2026 Sidhartha-roy104.
