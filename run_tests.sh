#!/usr/bin/env bash
set -e

# Create/activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Run tests
pytest -q
