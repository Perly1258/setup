#!/bin/bash
# start_rag_platform.sh

# ==============================================================================
# 🚀 RAG PLATFORM LAUNCHER
# ==============================================================================
# Orchestrates the complete RAG Application Stack:
# 1. RAG API (FastAPI Backend) -> Processes vector search & LLM logic
# 2. Open WebUI (Frontend) -> Provides the chat interface
# 3. Tool Bridge -> Auto-injects the Python tool to connect Frontend to Backend
# ==============================================================================

# --- 1. ARCHITECTURE CONFIGURATION ---

# Directory Paths
WORKSPACE_DIR="/workspace"
SETUP_DIR="$WORKSPACE_DIR/setup"
VENV_PATH="$WORKSPACE_DIR/rag_env"

# Network Ports (Service Bindings)
WEBUI_PORT=8000        # Frontend User Interface
RAG_API_PORT=9000      # RAG Backend API
OLLAMA_PORT=21434      # LLM Inference Service

# Component Scripts
TOOL_PAYLOAD="$SETUP_DIR/rag_retrieval_tool.py"      # The "Bridge" code
REGISTER_SCRIPT="$SETUP_DIR/register_webui_tool.py"  # The "Installer" script

# Credentials & Service Links
export POSTGRES_USER="postgres"
export POSTGRES_PASSWORD="postgres"
export DB_HOST="localhost"
export DB_PORT="5432"
export OLLAMA_HOST="localhost:$OLLAMA_PORT"

# --- 2. INITIALIZATION ---

echo "--- [1/5] Initializing Environment ---"

if [ ! -f "$VENV_PATH/bin/activate" ]; then
    echo "❌ CRITICAL ERROR: Virtual environment missing at $VENV_PATH"
    echo "   Please run setup_ml_only.sh first."
    exit 1
fi

echo "✅ Activating Python Virtual Environment..."
source "$VENV_PATH/bin/activate"

# --- 3. STARTING BACKEND (RAG API) ---

echo ""
echo "--- [2/5] Launching RAG API Backend ---"
echo "   Endpoint: http://0.0.0.0:$RAG_API_PORT"

# Start FastAPI/Uvicorn in background
uvicorn src.api_server:app --host 0.0.0.0 --port $RAG_API_PORT &
RAG_PID=$!
echo "✅ Backend Service Started (PID: $RAG_PID)"

# --- 4. STARTING FRONTEND (OPEN WEBUI) ---

echo ""
echo "--- [3/5] Launching Open WebUI Frontend ---"
echo "   Interface: http://0.0.0.0:$WEBUI_PORT"

if ! command -v open-webui &> /dev/null; then
    echo "❌ CRITICAL ERROR: 'open-webui' package not installed."
    kill $RAG_PID
    exit 1
fi

# Start WebUI in background
open-webui --host 0.0.0.0 --port $WEBUI_PORT &
WEBUI_PID=$!
echo "✅ Frontend Service Started (PID: $WEBUI_PID)"

# --- 5. HEALTH CHECK & SYNC ---

echo ""
echo "--- [4/5] Waiting for System Readiness ---"
echo "   Polling WebUI health status..."

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

if [ "$WEBUI_READY" = false ]; then
    echo ""
    echo "⚠️  WARNING: Frontend initialization timed out."
    echo "   Auto-configuration may fail."
fi

# --- 6. TOOL REGISTRATION ---

echo ""
echo "--- [5/5] Registering RAG Tool ---"

if [ -f "$REGISTER_SCRIPT" ] && [ -f "$TOOL_PAYLOAD" ]; then
    echo "   Injecting Retrieval Tool into WebUI..."
    python3 "$REGISTER_SCRIPT" "$TOOL_PAYLOAD"
else
    echo "❌ Error: Tool installation scripts missing."
    echo "   Skipping tool registration."
fi

# --- 7. PLATFORM STATUS ---

echo ""
echo "========================================================"
echo "🚀 RAG PLATFORM IS LIVE"
echo "========================================================"
echo "🖥️  Frontend:  http://localhost:$WEBUI_PORT"
echo "🔌  API:       http://localhost:$RAG_API_PORT"
echo "========================================================"
echo "   Log: Press CTRL+C to shutdown platform."

# Wait for RAG API. If it stops, script ends.
wait $RAG_PID

# --- 8. GRACEFUL SHUTDOWN ---
echo ""
echo "🔻 Shutting down platform..."
kill $WEBUI_PID
echo "Done."