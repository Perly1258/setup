#!/bin/bash

# Dynamic Paths
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
VENV_PATH="${VENV_PATH:-/workspace/rag_env}"
DATA_DIR="${DATA_DIR:-$SCRIPT_DIR/webui_data}"
TOOL_SCRIPT="${TOOL_SCRIPT:-$SCRIPT_DIR/rag_retrieval_tool.py}"
REGISTER_SCRIPT="${REGISTER_SCRIPT:-$SCRIPT_DIR/register_webui_tool.py}"

# Hardcoded Env Vars
export POSTGRES_USER="${POSTGRES_USER:-postgres}"
export POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-postgres}"
export DB_HOST="${DB_HOST:-localhost}"
export DB_PORT="${DB_PORT:-5432}"
export DB_NAME="${DB_NAME:-rag_db}"
export OLLAMA_HOST="localhost:21434"
export DATA_DIR="$DATA_DIR"

# Ensure directories exist
mkdir -p "$DATA_DIR"
mkdir -p documents
mkdir -p storage_pdf

# Kill any existing processes on ports
fuser -k 8000/tcp > /dev/null 2>&1
fuser -k 9000/tcp > /dev/null 2>&1
fuser -k 8080/tcp > /dev/null 2>&1

# Activate Venv
source "$VENV_PATH/bin/activate"

# Start Backend (RAG API) on 9000
uvicorn src.api_server:app --host 0.0.0.0 --port 9000 &
RAG_PID=$!

# Start Frontend (Open WebUI) on 8000
# EXPLICITLY passing DATA_DIR here guarantees the process receives it
# ADDED: WEBUI_SECRET_KEY to prevent startup errors or session invalidation
export WEBUI_SECRET_KEY="${WEBUI_SECRET_KEY:-t0p-s3cr3t-k3y-fix}"
export WEBUI_AUTH="${WEBUI_AUTH:-True}"
export ENABLE_SIGNUP="${ENABLE_SIGNUP:-True}"

# Force Open WebUI to use Postgres instead of SQLite
export DATABASE_URL="postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}"

DATA_DIR="$DATA_DIR" open-webui serve --host 0.0.0.0 --port 17500 &
WEBUI_PID=$!

# Wait for Frontend to be ready
COUNT=0
while [ $COUNT -lt 30 ]; do
    if curl -s "http://localhost:7500/health" > /dev/null; then
        break
    fi
    sleep 2
    COUNT=$((COUNT+1))
done

# Register Tool if scripts exist
if [ -f "$REGISTER_SCRIPT" ] && [ -f "$TOOL_SCRIPT" ]; then
    python3 "$REGISTER_SCRIPT" "$TOOL_SCRIPT"
fi

# Keep alive
echo "RAG Platform Running on 7500 (UI) and 9000 (API)"
wait $RAG_PID
kill $WEBUI_PID