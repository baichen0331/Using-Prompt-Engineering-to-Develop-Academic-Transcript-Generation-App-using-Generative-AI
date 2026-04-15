@echo off
setlocal
cd /d "D:\code\transcript"

if not exist ".venv\Scripts\activate.bat" (
    echo Virtual environment not found at .venv\Scripts\activate.bat
    echo Please create it first, for example:
    echo python -m venv .venv
    echo .venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

if not exist ".env" (
    echo .env was not found. Please copy .env.example to .env and fill in your settings.
    pause
    exit /b 1
)

echo Starting the backend service (FastAPI)...
start "Backend" cmd /k "cd /d D:\code\transcript && call .venv\Scripts\activate.bat && uvicorn app.main:app --reload"

echo Waiting for backend to initialize...
timeout /t 4 /nobreak >nul

echo Starting the front-end interface (Streamlit)...
start "Frontend" cmd /k "cd /d D:\code\transcript && call .venv\Scripts\activate.bat && streamlit run frontend_app/main.py"

echo Project launch complete.
echo Backend:  http://127.0.0.1:8000
echo Frontend: usually http://localhost:8501
echo If 8501 is already occupied, Streamlit may automatically switch to another port such as 8502 or 8505.
endlocal

