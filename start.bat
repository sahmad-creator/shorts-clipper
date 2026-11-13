@echo off
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
  echo Pehle Python install karo: https://www.python.org/downloads/
  echo Install karte waqt "Add Python to PATH" ko TICK karna. Phir ye file dubara chalao.
  pause
  exit /b
)
if not exist venv (
  echo Pehli baar setup ho raha hai, 5-10 minute lagenge...
  python -m venv venv
)
call venv\Scripts\activate
python -m pip install -q --upgrade yt-dlp
pip install -q -r requirements.txt
python app.py
pause
