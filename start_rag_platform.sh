#!/bin/bash
# start_rag_platform.sh

# ==============================================================================
# 🚀 RAG PLATFORM LAUNCHER
# ==============================================================================
# 1. RAG API (FastAPI Backend) -> Port 9000
# 2. Open WebUI (Frontend) -> Port 8000
# 3. Tool Bridge -> Auto-injects rag_tool.py
# ==============================================================================

# --- 1. ARCHITECTURE CONFIGURATION ---

WORKSPACE_DIR="/workspace"
SETUP_DIR="$WORKSPACE_DIR/setup"
VENV_PATH="$WORKSPACE_DIR/rag_env"

WEBUI_PORT=8000
RAG_API_PORT=9000
OLLAMA_PORT=21434

# Using the files you provided
TOOL_PAYLOAD="$SETUP_DIR/rag_tool.py"
REGISTER_SCRIPT="$SETUP_DIR/register_webui_tool.py"

export POSTGRES_USER="postgres"
export POSTGRES_PASSWORD="postgres"
export DB_HOST="localhost"
export DB_PORT="5432"
export OLLAMA_HOST="localhost:$OLLAMA_PORT"

# --- 2. INITIALIZATION ---

echo "--- [1/5] Initializing Environment ---"
if [ ! -f "$VENV_PATH/bin/activate" ]; then
    echo "❌ CRITICAL ERROR: Virtual environment missing at $VENV_PATH"
    exit 1
fi
source "$VENV_PATH/bin/activate"

# --- 3. STARTING BACKEND (RAG API) ---

echo "--- [2/5] Launching RAG API Backend (Port $RAG_API_PORT) ---"
# Uses the updated src/api_server.py
uvicorn src.api_server:app --host 0.0.0.0 --port $RAG_API_PORT &
RAG_PID=$!
echo "✅ Backend Service Started (PID: $RAG_PID)"

# --- 4. STARTING FRONTEND (OPEN WEBUI) ---

echo "--- [3/5] Launching Open WebUI Frontend (Port $WEBUI_PORT) ---"
if ! command -v open-webui &> /dev/null; then
    echo "❌ CRITICAL ERROR: 'open-webui' package not installed."
    kill $RAG_PID
    exit 1
fi

# FIX: Use Environment Variables and 'serve' command
export HOST=0.0.0.0
export PORT=$WEBUI_PORT
open-webui serve &
WEBUI_PID=$!

echo "✅ Frontend Service Started (PID: $WEBUI_PID)"

# --- 5. HEALTH CHECK ---

echo "--- [4/5] Waiting for System Readiness ---"
MAX_RETRIES=30
COUNT=0
WEBUI_READY=false

while [ $COUNT -lt $MAX_RETRIES ]; do
    if curl -s "http://localhost:$WEBUI_PORT/health" > /dev/null; then
        WEBUI_READY=true
        echo "✅ System Online."
        break
    fi
    echo -n "."
    sleep 2
    COUNT=$((COUNT+1))
done

# --- 6. TOOL REGISTRATION ---

if [ "$WEBUI_READY" = true ]; then
    echo "--- [5/5] Registering RAG Tool ---"
    if [ -f "$REGISTER_SCRIPT" ] && [ -f "$TOOL_PAYLOAD" ]; then
        python3 "$REGISTER_SCRIPT" "$TOOL_PAYLOAD"
    else
        echo "❌ Error: Tool scripts missing."
    fi
else
    echo "⚠️  WARNING: Frontend initialization timed out."
fi

# --- 7. KEEP ALIVE ---

echo "========================================================"
echo "🚀 RAG PLATFORM IS LIVE"
echo "========================================================"
echo "🖥️  Frontend:  http://localhost:$WEBUI_PORT"
echo "🔌  API:       http://localhost:$RAG_API_PORT"
echo "========================================================"
echo "Press CTRL+C to stop."

wait $RAG_PID
kill $WEBUI_PID