@echo off
title StocX Offline Dashboard Launcher
echo ===================================================================
echo Starting StocX Market-Neutral Hedge Builder (Offline Demo Mode)...
echo ===================================================================
echo.
cd /d "%~dp0\.."

if exist ".venv\Scripts\streamlit.exe" (
    echo Launching Streamlit dashboard via local virtual environment...
    .venv\Scripts\streamlit.exe run app.py
) else (
    echo Launching Streamlit dashboard via system Python...
    python -m streamlit run app.py
)

pause
