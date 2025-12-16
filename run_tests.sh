#!/bin/bash
# run_tests.sh
# One-click test runner for Linux/macOS
# This script sets up the environment and runs the full test suite

set -e

COVERAGE=false
VERBOSE=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --coverage)
            COVERAGE=true
            shift
            ;;
        --verbose)
            VERBOSE=true
            shift
            ;;
        *)
            shift
            ;;
    esac
done

echo "================================================"
echo "Content Moderation Service - Test Runner"
echo "================================================"
echo ""

# Detect Python executable
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    echo "ERROR: Python not found. Please install Python 3.8+"
    exit 1
fi

echo "Using Python: $PYTHON_CMD"
$PYTHON_CMD --version
echo ""

# Create/activate virtual environment
VENV_PATH="venv"
if [ ! -d "$VENV_PATH" ]; then
    echo "Creating virtual environment..."
    $PYTHON_CMD -m venv $VENV_PATH
fi

echo "Activating virtual environment..."
source $VENV_PATH/bin/activate

# Upgrade pip
echo "Upgrading pip..."
$PYTHON_CMD -m pip install --upgrade pip -q 2>/dev/null || true

# Install requirements
echo "Installing dependencies from requirements.txt..."
$PYTHON_CMD -m pip install -r requirements.txt -q
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to install dependencies"
    exit 1
fi

echo "Dependencies installed successfully"
echo ""

# Run pytest
echo "Running test suite..."
echo "================================================"

TEST_ARGS="tests/ -v"

if [ "$COVERAGE" = true ]; then
    TEST_ARGS="$TEST_ARGS --cov=src --cov=moderation_service --cov-report=term-missing"
    echo "Running with coverage report..."
fi

if [ "$VERBOSE" = true ]; then
    TEST_ARGS="$TEST_ARGS -vv -s"
fi

$PYTHON_CMD -m pytest $TEST_ARGS
TEST_RESULT=$?

echo ""
echo "================================================"
if [ $TEST_RESULT -eq 0 ]; then
    echo "All tests PASSED!"
else
    echo "Some tests FAILED (exit code: $TEST_RESULT)"
fi
echo "================================================"

exit $TEST_RESULT
