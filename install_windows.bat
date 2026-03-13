@echo off
echo ========================================
echo YouTube Transcript Summarizer
echo Installation Script for Windows
echo ========================================
echo.

REM Check Python installation
echo Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8 or higher from python.org
    pause
    exit /b 1
)

python --version
echo.

REM Create virtual environment
echo Creating virtual environment...
python -m venv venv
if errorlevel 1 (
    echo ERROR: Failed to create virtual environment
    pause
    exit /b 1
)
echo Virtual environment created successfully
echo.

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat
echo.

REM Upgrade pip
echo Upgrading pip...
python -m pip install --upgrade pip
echo.

REM Install requirements
echo Installing Python packages...
echo This may take a few minutes...
pip install -r requirements_enhanced.txt
if errorlevel 1 (
    echo ERROR: Failed to install packages
    echo Please check your internet connection and try again
    pause
    exit /b 1
)
echo.

REM Setup NLTK
echo Setting up NLTK data...
python fix_nltk.py
echo.

REM Create .env file if it doesn't exist
if not exist .env (
    echo Creating .env file from template...
    copy .env.example .env
    echo.
    echo IMPORTANT: Please edit .env file and add your GOOGLE_API_KEY
    echo You can get it from: https://makersuite.google.com/app/apikey
    echo.
)

REM Success message
echo ========================================
echo Installation Complete!
echo ========================================
echo.
echo Next steps:
echo 1. Edit .env file and add your GOOGLE_API_KEY
echo 2. Run: streamlit run app_enhanced_fixed.py
echo.
echo To start the virtual environment in future:
echo   venv\Scripts\activate.bat
echo.
pause
