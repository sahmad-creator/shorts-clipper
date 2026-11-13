#!/usr/bin/env bash
# Mac / Linux: double-click (start.command) ya terminal mein: bash start.sh
cd "$(dirname "$0")"
if ! command -v python3 >/dev/null; then
  echo "Pehle Python 3 install karo: https://www.python.org/downloads/"; exit 1
fi
if [ ! -d venv ]; then
  echo "Pehli baar setup ho raha hai, 5-10 minute lagenge..."
  python3 -m venv venv
fi
source venv/bin/activate
python -m pip install -q --upgrade yt-dlp
pip install -q -r requirements.txt
python app.py
