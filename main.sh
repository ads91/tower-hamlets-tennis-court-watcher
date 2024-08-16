#!/bin/bash
# export CONFIG_EXTRAS=".st_johns_park" && sh /Users/andrewsanderson/Documents/dev/tower-hamlets-tennis-court-watcher/main.sh
# export CONFIG_EXTRAS=".poplar_rec_ground" && sh /Users/andrewsanderson/Documents/dev/tower-hamlets-tennis-court-watcher/main.sh

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
