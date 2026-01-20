@echo off
REM Run tests in a virtual environment (Windows)
setlocal

:: Create virtual env if not exists
if not exist .venv (python -m venv .venv)

call .venv\Scripts\activate

python -m pip install --upgrade pip
pip install -r requirements.txt

pytest -q
endlocal
