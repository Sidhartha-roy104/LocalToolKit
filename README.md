# 🔒 LocalToolKit

**All your file tools in one place. 100% offline. 100% private. Free forever.**

Compress images, merge PDFs, convert Word to PDF and more, all on your own computer. Your files **never leave your device**: no uploads, no cloud, no accounts, no tracking.

---

## 🛑 Stop uploading your files to random websites

Most "free online tools" work by uploading your files to someone else's server. That can include your ID cards, bank statements, resumes, contracts, medical reports and personal photos. Once uploaded, you don't control where the file goes, who can see it, or how long it's kept.

**LocalToolKit does the same job on your own laptop.**

- ✅ Files are processed on your device only
- ✅ No internet needed (works with Wi-Fi turned off)
- ✅ No sign-up, no ads, no limits, no watermarks
- ✅ No analytics or telemetry
- ✅ Temporary files are deleted right after each task
- ✅ The server listens only on `127.0.0.1`, so other devices on your network cannot reach it
- ✅ Open source: you can read every line of code and verify it yourself

> 💡 **Our advice:** For anything personal or confidential, avoid online converters. Use a local tool like this one instead.

---

## 🧰 Tools included

| Category | Tools |
|---|---|
| **Images** | Compress Image · Convert Image (JPG/PNG/WEBP/HEIC/BMP/TIFF) · Image to PDF |
| **PDF** | PDF to Images · Merge · Split / Extract Pages · Compress · Rotate / Reorder · Add or Remove Password · Watermark |
| **Documents** | Word to PDF · PDF to Word · OCR (scanned PDF/image to searchable PDF or text) · Text / Markdown / HTML to PDF |

---

## 🚀 Quick start

### 1. Requirements

- **Python 3.11 or newer** → [python.org/downloads](https://www.python.org/downloads/)
- **Git** (optional, only to clone the repo)

### 2. Download

```bash
git clone https://github.com/YOUR_USERNAME/LocalToolKit.git
cd LocalToolKit
```

(Or click **Code → Download ZIP** on GitHub and unzip it.)

### 3. Install

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
```

### 4. Run

```bash
python run.py
```

Your browser opens automatically at `http://127.0.0.1:8000`. That's it! 🎉

---

## 🧩 Optional programs (for a few tools)

Most tools work right after install. These three tools need a free program installed on your computer. If one is missing, the app shows a friendly message instead of crashing.

| Needed for | Install | Notes |
|---|---|---|
| **Word to PDF** | [LibreOffice](https://www.libreoffice.org/download/) | Free, gives the best layout quality |
| **Better PDF compression** | [Ghostscript](https://ghostscript.com/releases/gsdnld.html) | Optional; a built-in fallback is used if missing |
| **OCR (scanned documents)** | [Tesseract](https://github.com/tesseract-ocr/tesseract) | Free OCR engine |

Check the **System Status** page in the app to see what's detected on your machine.

---

## 🔐 Privacy and security promise

- **No external requests:** no CDNs, remote fonts, analytics, or cloud APIs
- **Local only:** the server binds to `127.0.0.1`, never `0.0.0.0`
- **Auto-cleanup:** temp files are removed after every request, and leftovers are swept on startup
- **Safe file handling:** sanitized filenames, file type checks, and upload size limits
- **Nothing is logged** about your file contents or names

### Verify it yourself

1. Turn off your Wi-Fi or unplug the network and use the app. Everything still works.
2. Open your browser's Network tab. You'll only see requests to `127.0.0.1`.
3. Search the code for outbound network calls. There are none.

---

## 🛠️ Troubleshooting

| Problem | Fix |
|---|---|
| `python` not found | Reinstall Python and tick **"Add Python to PATH"**, or try `python3` |
| Port already in use | Close the other app, or run with a different port in `config.py` |
| Word to PDF says "LibreOffice not found" | Install LibreOffice, then restart the app |
| PDF to Word layout looks off | Complex layouts and tables may need manual cleanup. This is a limit of PDF format conversion |
| HEIC images won't open | Run `pip install pillow-heif` again inside your virtual environment |

---

## 🧱 Add your own tool

Each tool is one backend file plus one UI card:

1. Create `backend/tools/your_tool.py` with its own FastAPI router
2. Add an entry (id, name, category, colors, icon) to the tools registry in `frontend/js/tools.js`
3. Restart the app. Your tool appears in the grid.

---

## 📦 Build a one-click app (optional)

```bash
pip install pyinstaller
pyinstaller build.spec
```

Your double-click executable will be in the `dist/` folder.

---

## 🤝 Contributing

Issues and pull requests are welcome. Please keep the core promise: **no tracking, no cloud, no third-party services.**

---

## 📄 License

MIT License. Free to use, modify, and share.

---

<p align="center"><b>Your files. Your device. Your privacy.</b> 🔒</p>
