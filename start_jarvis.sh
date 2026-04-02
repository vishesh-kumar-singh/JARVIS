#!/bin/bash

# If the user presses their global shortcut or runs this manually outside systemd,
# safely redirect the request to restart the background service instead of spawning
# a new overlapping rogue Python process!
if [ -z "$JARVIS_SERVICE_ACTIVE" ]; then
    systemctl --user restart jarvis
    exit 0
fi

source /home/vishesh/anaconda3/etc/profile.d/conda.sh
conda activate langchain
cd "/home/vishesh/My Stuff/BCS-2025-26/Inter-IIT/Google Agent"
python live_audio.py
