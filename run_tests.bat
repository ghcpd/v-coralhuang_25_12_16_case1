@echo off
REM Create virtual environment if it doesn't exist
if not exist venv (
    python -m venv venv
)

REM Activate virtual environment
call venv\Scripts\activate

REM Install dependencies
pip install -r requirements.txt

REM Run tests
python -m pytest tests/ -v

REM Deactivate (optional)
call deactivate