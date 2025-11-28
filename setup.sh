#!/bin/bash
# Setup script for Python 3.12 virtual environment
# This script handles the case where ensurepip is not available

set -e

echo "Setting up virtual environment for Python 3.12..."

# Remove old venv if it exists
if [ -d "venv" ]; then
    echo "Removing existing venv..."
    rm -rf venv
fi

# Create new virtual environment without pip (since ensurepip may not be available)
echo "Creating virtual environment with Python 3.12 (without pip)..."
python3.12 -m venv venv --without-pip

# Download and install pip manually
echo "Installing pip manually..."
python3.12 -c "import urllib.request; urllib.request.urlretrieve('https://bootstrap.pypa.io/get-pip.py', 'get-pip.py')"
./venv/bin/python3.12 get-pip.py
rm -f get-pip.py

# Upgrade pip
echo "Upgrading pip..."
./venv/bin/pip install --upgrade pip setuptools wheel

# Install dependencies
echo "Installing dependencies from requirements.txt..."
./venv/bin/pip install -r requirements.txt

echo ""
echo "✓ Setup complete!"
echo ""
echo "To activate the virtual environment in the future, run:"
echo "  source venv/bin/activate"
echo ""
echo "Or use the venv Python directly:"
echo "  ./venv/bin/python -m uvicorn app.api.main:app --host 0.0.0.0 --port 8000 --reload"
echo ""

