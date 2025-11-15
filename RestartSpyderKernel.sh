#!/bin/bash
# Exit immediately if a command exits with a non-zero status.
set -e

# --- Configuration ---
# Path to your virtual environment
VENV_PATH="/workspace/rag_env" 
# Path where the connection file is expected
CONNECTION_FILE="/workspace/setup/remotekernel.json"

echo "--- 1. Killing Existing Spyder Kernels ---"

# Use pkill with -f (full command line) to target all processes 
# running 'spyder_kernels.console'. -9 ensures a forceful kill (SIGKILL).
# The || true allows the script to continue if no process is found (pkill exits with status 1).
pkill -9 -f "spyder_kernels.console" || true

echo "✅ All existing Spyder kernel processes terminated."
sleep 1 # Wait briefly for processes to fully terminate

echo "--- 2. Starting New Spyder Kernel ---"

# Source the virtual environment to ensure we use the correct Python interpreter
source "$VENV_PATH/bin/activate"

# Start the kernel in the background (&) listening on all IPs (0.0.0.0)
# and saving connection details to the JSON file (-f).
python -m spyder_kernels.console --ip 0.0.0.0 -f "$CONNECTION_FILE" &

echo "🚀 New Spyder kernel started in the background."
echo "Connection details saved to $CONNECTION_FILE."

# Deactivate the virtual environment
deactivate

echo "--- SCRIPT COMPLETE ---"
