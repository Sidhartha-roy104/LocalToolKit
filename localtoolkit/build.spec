# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller specification for LocalToolkit (--onedir mode).
Packages FastAPI, Uvicorn, frontend assets, data files, and local tool dependencies
into a standalone directory (dist/LocalToolkit/).
"""
import os, sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_submodules

block_cipher = None

root_dir = os.path.abspath(SPECPATH)

# Data files: bundle the whole frontend folder and data JSONs
datas = [
    (os.path.join(root_dir, 'frontend'), 'frontend'),
    (os.path.join(root_dir, 'backend', 'data'), 'backend/data'),
    (os.path.join(root_dir, 'frontend', 'data'), 'frontend/data'),
]
binaries = []

hiddenimports = [
    'uvicorn',
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespans',
    'uvicorn.lifespans.on',
    'uvicorn.lifespans.off',
    'uvicorn.lifespan',
    'uvicorn.lifespan.on',
    'multipart',
    'python_multipart',
    'pypdf',
    'img2pdf',
    'pytesseract',
    'PIL',
    'PIL.WebPImagePlugin',
    'PIL.JpegImagePlugin',
    'PIL.PngImagePlugin',
    'PIL.BmpImagePlugin',
    'secrets',
    'starlette.middleware.base',
]

# Ensure every tool module inside backend and backend.tools is bundled
hiddenimports += collect_submodules('backend')
hiddenimports += collect_submodules('backend.tools')

# Collect all data, binaries, and submodules for heavy packages
for pkg in ['pillow_heif', 'pdf2docx', 'pikepdf', 'fitz', 'pymupdf']:
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception as e:
        print(f"collect_all({pkg}) notice: {e}")

icon_file = os.path.join(root_dir, 'frontend', 'assets', 'icon.ico')
if not os.path.exists(icon_file):
    icon_file = None

a = Analysis(
    [os.path.join(root_dir, 'run.py')],
    pathex=[root_dir],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tensorflow',
        'tensorboard',
        'torch',
        'torchvision',
        'scipy',
        'matplotlib',
        'tkinter',
        'IPython',
        'jupyter',
        'numpy.tests',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='LocalToolkit',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # No black terminal window
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_file,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='LocalToolkit',
)
