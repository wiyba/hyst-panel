#!/usr/bin/env bash
set -e
source venv/bin/activate
if [ "$1" = "run" ]; then
    python3 main.py run
elif [ "$1" = "generate" ] && [ -n "$2" ]; then
    python3 main.py generate "$2"
elif [ "$1" = "edit" ] && [ -n "$2" ]; then
    python3 main.py edit "$2"
elif [ "$1" = "info" ]; then
    if [ -n "$2" ]; then
        python3 main.py info "$2"
    else
        python3 main.py info
    fi
else
    echo "Usage:"
    echo "  $0 run"
    echo "  $0 generate <username>"
    echo "  $0 edit <username>"
    echo "  $0 info"
    echo "  $0 info all"
    echo "  $0 info <username>"
    exit 1
fi