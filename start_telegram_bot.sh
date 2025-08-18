#!/bin/bash
# Start Telegram Bot

echo "Starting Telegram Bot..."
cd "$(dirname "$0")"

# Set display for headless environment
export DISPLAY=:99

# Start the telegram bot
python main.py