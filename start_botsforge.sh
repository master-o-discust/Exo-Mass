#!/bin/bash
# Start BotsForge CloudFlare Solver Server

echo "Starting BotsForge CloudFlare Solver Server..."
cd "$(dirname "$0")"

# Set display for headless environment
export DISPLAY=:99

# Start the server using the proper launcher
python launch_botsforge.py