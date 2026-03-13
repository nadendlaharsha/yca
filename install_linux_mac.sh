#!/bin/bash

echo "========================================"
echo "YouTube Transcript Summarizer"
echo "Installation Script for Linux/Mac"
echo "========================================"
echo ""

# Check Python installation
echo "Checking Python installation..."
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed"
    echo "Please install Python 3.8 or higher"
    exit 1
fi

python3 --version
echo ""

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv venv
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to create virtual environment"
    exit 1
fi
echo "Virtual environment created successfully"
echo ""

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate
echo ""

# Upgrade pip
echo "Upgrading pip..."
python -m pip install --upgrade pip
echo ""

# Install requirements
echo "Installing Python packages..."
echo "This may take a few minutes..."
pip install -r requirements_enhanced.txt
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to install packages"
    echo "Please check your internet connection and try again"
    exit 1
fi
echo ""

# Setup NLTK
echo "Setting up NLTK data..."
python fix_nltk.py
echo ""

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "Creating .env file from template..."
    cp .env.example .env
    echo ""
    echo "IMPORTANT: Please edit .env file and add your GOOGLE_API_KEY"
    echo "You can get it from: https://makersuite.google.com/app/apikey"
    echo ""
fi

# Success message
echo "========================================"
echo "Installation Complete!"
echo "========================================"
echo ""
echo "Next steps:"
echo "1. Edit .env file and add your GOOGLE_API_KEY:"
echo "   nano .env"
echo ""
echo "2. Run the app:"
echo "   source venv/bin/activate"
echo "   streamlit run app_enhanced_fixed.py"
echo ""
echo "To start the virtual environment in future:"
echo "   source venv/bin/activate"
echo ""
