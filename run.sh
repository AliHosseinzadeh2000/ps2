#!/bin/bash
# Run script for the Arbitrage Trading Bot API

cd "$(dirname "$0")"

# Check if venv exists
if [ ! -d "venv" ]; then
    echo "Virtual environment not found. Please run ./setup.sh first."
    exit 1
fi

# Check if dependencies are installed
if ! ./venv/bin/python -c "import fastapi" 2>/dev/null; then
    echo "Dependencies not installed. Please run ./setup.sh first."
    exit 1
fi

# Run the API server
echo "Starting Arbitrage Trading Bot API..."
echo "API will be available at http://localhost:8000"
echo "Interactive docs at http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

./venv/bin/python -m uvicorn app.api.main:app --host 0.0.0.0 --port 8000 --reload

