#!/bin/bash

cd /Users/andrewsanderson/Documents/dev/tower-hamlets-tennis-court-watcher

# The command you want to run indefinitely
COMMAND="./venv/bin/python3 main.py"

# Loop indefinitely
while true; do
    # Run the command
    $COMMAND
    # Wait for a second before restarting (optional)
    sleep 10
done
