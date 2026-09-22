@echo off
title PaperAssistant
cd /d "%~dp0"

rem ===== First run: create venv and install deps =====
if not exist ".venv\Scripts\pythonw.exe" (
    echo [Setup] Creating virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo [Error] Python not found. Install Python 3.10+ and check "Add to PATH".
        pause
        exit /b 1
    )
    echo [Setup] Installing dependencies, 1-3 min...
    .venv\Scripts\python.exe -m pip install -r requirements.txt -q
    .venv\Scripts\python.exe -m pip install -r requirements-desktop.txt -q
    if errorlevel 1 (
        echo [Error] Failed to install dependencies. Check network and retry.
        pause
        exit /b 1
    )
)

rem ===== First run: create .env from template =====
if not exist ".env" (
    copy .env.example .env >nul
    echo [Setup] Created .env - fill in your API key, save and close.
    notepad .env
)

rem ===== Launch desktop window (no console) =====
start "" .venv\Scripts\pythonw.exe desktop.py
