#!/bin/bash

# 1. Wait for the Desktop to load
sleep 10

# 2. Set Environment Variables for Display
export DISPLAY=:0
export XAUTHORITY="$HOME/.Xauthority"
export XDG_RUNTIME_DIR=/run/user/$(id -u)

# 3. Go to the project directory (wherever this script lives)
cd "$(dirname "$(readlink -f "$0")")"

# 4. Activate the Virtual Environment
source biometric_env/bin/activate

# 5. Run the Kiosk (and log any errors to a file for debugging)
# This loop ensures that if the code crashes, it restarts automatically after 5 seconds
while true; do
    echo "Starting Attendance Kiosk..." > bot_log.txt
    python main.py >> bot_log.txt 2>&1

    echo "Kiosk crashed or closed. Restarting in 5 seconds..." >> bot_log.txt
    sleep 5
done
