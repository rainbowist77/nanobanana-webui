#!/usr/bin/env bash
set -euo pipefail

cd -- "$(dirname -- "${BASH_SOURCE[0]}")"

# Linux/macOS use bin; Git Bash on Windows uses Scripts.
if [[ -x .venv/bin/python ]]; then
    venv_python=.venv/bin/python
elif [[ -x .venv/Scripts/python.exe ]]; then
    venv_python=.venv/Scripts/python.exe
else
    if command -v python3 >/dev/null 2>&1; then
        python_command=python3
    elif command -v python >/dev/null 2>&1; then
        python_command=python
    else
        echo 'Python 3.10 or newer is required.' >&2
        exit 1
    fi
    "$python_command" -m venv .venv
    if [[ -x .venv/bin/python ]]; then
        venv_python=.venv/bin/python
    elif [[ -x .venv/Scripts/python.exe ]]; then
        venv_python=.venv/Scripts/python.exe
    else
        echo 'Could not find the project virtual environment interpreter.' >&2
        exit 1
    fi
fi

exec "$venv_python" app.py "$@"
