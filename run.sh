#!/usr/bin/env bash
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
if [ ! -d "$DIR/venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$DIR/venv"
    "$DIR/venv/bin/pip" install -r "$DIR/requirements.txt"
fi

exec "$DIR/venv/bin/python3" "$DIR/cka_agent.py" "$@"
