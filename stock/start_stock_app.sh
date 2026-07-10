#!/bin/bash

# Stock Analysis Web App Startup Script

echo "======================================"
echo "🚀 Starting Stock Analysis Web App"
echo "======================================"

# Get the directory of the script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Check if Python is installed
if ! command -v python3 &> /dev/null
then
    echo "❌ Python3 is not installed. Please install Python 3.7 or higher."
    exit 1
fi

echo "✓ Python3 found: $(python3 --version)"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
    echo "✓ Virtual environment created"
fi

# Activate virtual environment
echo "🔄 Activating virtual environment..."
source venv/bin/activate

# Install/Update dependencies
echo "📥 Installing dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements_stock_app.txt
echo "✓ Dependencies installed"

# Check if Flask is installed
if ! python3 -c "import flask" &> /dev/null; then
    echo "❌ Flask installation failed. Please check requirements_stock_app.txt"
    exit 1
fi

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p templates
mkdir -p static/css
mkdir -p static/js
echo "✓ Directories ready"

# Display information
echo ""
echo "======================================"
echo "✓ Application ready to start!"
echo "======================================"
echo ""
echo "📍 Access URL: http://127.0.0.1:5000"
echo "📍 Local:      http://localhost:5000"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""
echo "======================================"
echo ""

# Start the Flask application
python3 app.py

