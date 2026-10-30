#!/usr/bin/env bash
set -e

echo "==================================================="
echo "              LocalToolkit Launcher"
echo "==================================================="
echo ""

# Find Python 3
if command -v python3 &>/dev/null; then
    PYTHON_CMD=python3
elif command -v python &>/dev/null; then
    PYTHON_CMD=python
else
    echo "[ERROR] Python is not installed or not in your PATH."
    echo "Please install Python 3.10+ from https://www.python.org/ or your package manager."
    exit 1
fi

# Create virtual environment if missing
if [ ! -d "venv" ]; then
    echo "[1/3] Creating virtual environment (venv)..."
    "$PYTHON_CMD" -m venv venv
fi

# Activate virtual environment
echo "[2/3] Activating virtual environment..."
source venv/bin/activate

# Install requirements
echo "[3/3] Checking and installing dependencies..."
python -m pip install --upgrade pip --quiet
python -m pip install -r requirements.txt --quiet

# Start application
echo ""
echo "Starting LocalToolkit..."
echo ""
python run.py

