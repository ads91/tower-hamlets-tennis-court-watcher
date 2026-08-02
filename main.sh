#!/bin/bash
# export CONFIG_EXTRAS=".st_johns_park" && sh /Users/andrewsanderson/Documents/dev/tower-hamlets-tennis-court-watcher/main.sh
# export CONFIG_EXTRAS=".poplar_rec_ground" && sh /Users/andrewsanderson/Documents/dev/tower-hamlets-tennis-court-watcher/main.sh
# export CONFIG_EXTRAS=".king_edward_memorial_park" && sh /Users/andrewsanderson/Documents/dev/tower-hamlets-tennis-court-watcher/main.sh

PROJECT_DIR="/Users/andrewsanderson/Documents/dev/tower-hamlets-tennis-court-watcher"
cd "$PROJECT_DIR" || exit 1

# Pick a Python interpreter that exists on this machine.
if [ -x "$PROJECT_DIR/.venv/bin/python" ]; then
    PYTHON_BIN="$PROJECT_DIR/.venv/bin/python"
elif [ -x "$PROJECT_DIR/venv/bin/python" ]; then
    PYTHON_BIN="$PROJECT_DIR/venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
else
    echo "No Python interpreter found (.venv, venv, or python3)." >&2
    exit 1
fi

echo "Using Python interpreter: $PYTHON_BIN"

# Loop indefinitely
while true; do
    # Run the command
    "$PYTHON_BIN" main.py
    # Wait for a second before restarting (optional)
    sleep 10
done
