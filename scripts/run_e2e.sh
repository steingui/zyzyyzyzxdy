#!/bin/bash
# scripts/run_e2e.sh
# Runs E2E integration tests from the project root context

# Ensure we are in the project root
cd "$(dirname "$0")/.."

# Environment setup
VENV_DIR=".venv"
if [ -d "venv" ]; then
    VENV_DIR="venv"
fi

PYTHON_CMD="python3"
if [ -d "$VENV_DIR" ]; then
    PYTHON_CMD="$VENV_DIR/bin/python"
    echo -e "\033[0;32mUsing virtualenv: $VENV_DIR\033[0m"
fi

echo -e "\033[0;32mRunning E2E API Tests...\033[0m"
# Run tests with discover from root
$PYTHON_CMD -m unittest discover -s tests -p "test_e2e*.py"
