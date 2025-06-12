#!/bin/bash
# Start new tmux session
tmux new-session -d -s cherum-client
source .env

# Create windows for each USB device
tmux new-window -t cherum-client -n "controller" "source .venv/bin/activate && python3 controller.py -s $1"
tmux new-window -t cherum-client -n "poller" "source .venv/bin/activate && export TOKEN=$TOKEN && python3 poller.py -u $2"
tmux new-window -t cherum-client -n "telemetry" "source .venv/bin/activate && export TOKEN=$TOKEN && python3 telemetry.py -u $2"
