#!/bin/bash
# This script runs every time the instance starts (or restarts).

# --- Configuration ---
PG_DATA_PATH="/workspace/postgres_data"
PG_USER="vast_user"
PG_DB="vast_project_db"
VENV_PATH="/workspace/mistrdependenciesal_env"

# --- 1. START POSTGRESQL ---
echo "--- 1. RESTARTING POSTGRESQL SERVICE ---"
# Start the PostgreSQL cluster using the persistent data directory
# Note: /usr/bin/pg_ctl is used, which is a standard location
/usr/bin/pg_ctl -D "$PG_DATA_PATH" -o "-k /tmp" -l /workspace/postgres.log start

# Wait a moment for the service to fully initialize before accepting connections
sleep 5 

echo "PostgreSQL service started. Use the following commands to access:"
echo "psql -d $PG_DB -U $PG_USER"

# --- 2. PREPARE PYTHON ENVIRONMENT ---
echo "--- 2. ACTIVATE PYTHON VIRTUAL ENVIRONMENT ---"
if [ -f "$VENV_PATH/bin/activate" ]; then
    # Activate the environment in the current shell context
    # This prepares the environment for any custom Python applications you launch
    source "$VENV_PATH/bin/activate"
    echo "Python virtual environment 'mistral_venv' activated."
    echo "Current directory changed to the cloned repository for convenience."
    
    # Change into the cloned project directory
    cd /workspace/setup 
else
    echo "ERROR: Python virtual environment not found at $VENV_PATH."
fi

echo "--- INSTANCE READY ---"
# The SSH daemon and Jupyter server (if selected) continue running now.
