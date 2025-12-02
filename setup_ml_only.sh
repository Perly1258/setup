#!/bin/bash
set -e

VENV_PATH="/workspace/rag_env"
MODEL_BASE_DIR="/workspace/models"
REPO_URL="https://github.com/Perly1258/setup.git"
ONSTART_SCRIPT_URL="https://raw.githubusercontent.com/Perly1258/setup/refs/heads/main/onstart.sh"

echo "--- 1. Installing System Dependencies & Cloning Repository ---"
cd /workspace
apt-get update
apt-get install -y --no-install-recommends \
    python3-venv git poppler-utils curl postgresql postgresql-contrib postgresql-16-pgvector
    
echo "Cloning repository $REPO_URL into /workspace/setup"
git clone "$REPO_URL"
cd /workspace/setup/db
sudo service postgresql start
sudo -u postgres createdb rag_db
sudo -u postgres psql -d rag_db -c "CREATE EXTENSION IF NOT EXISTS vector;"
sudo -u postgres psql -c "ALTER USER postgres WITH PASSWORD 'postgres';"
sudo -u postgres PGPASSWORD='postgres' psql -U postgres -d postgres -f /workspace/setup/db/setup/private_market_setup.sql
sudo -u postgres PGPASSWORD='postgres' psql -U postgres -d postgres -f /workspace/setup/db/setup/rag_annotations.sql

echo "--- 2. Setting up Python Virtual Environment and RAG Tools ---"
mkdir -p "$VENV_PATH"
mkdir -p "$MODEL_BASE_DIR"

if [ ! -f "$VENV_PATH/bin/activate" ]; then
    echo "Creating Python Virtual Environment: $VENV_PATH"
    python3 -m venv "$VENV_PATH"
fi

source "$VENV_PATH/bin/activate"

echo "Installing core Python packages..."
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
pip install transformers accelerate ipykernel psycopg2-binary sentence-transformers
pip install langchain langchain-ollama pypdf pydantic huggingface-hub
pip install spyder-kernels
pip install llama-index-core llama-index-llms-ollama llama-index-embeddings-ollama \
            llama-index-vector-stores-postgres sqlalchemy psycopg2-binary \
            llama-index-readers-file pymupdf tabulate open-webui

echo "--- 3. Ollama Model Downloads and Server Start ---"
export OLLAMA_HOST="${OLLAMA_HOST:-0.0.0.0:21434}"
echo "Starting Ollama on: $OLLAMA_HOST"

ollama serve &
sleep 5 

ollama pull mistral
ollama pull nomic-embed-text

CONNECTION_FILE="/workspace/setup/remotekernel.json"
echo "Starting remote Python kernel and saving connection details to $CONNECTION_FILE"
python -m spyder_kernels.console --ip 0.0.0.0 -f "$CONNECTION_FILE" &

source "$VENV_PATH/bin/activate"

echo "Downloading companion onstart script from $ONSTART_SCRIPT_URL"
wget -O /workspace/onstart.sh "$ONSTART_SCRIPT_URL"
chmod +x /workspace/setup/*.sh

# --- 4. START RAG API & OPEN WEBUI (Auto-Connected) ---
echo "🚀 Launching RAG API & WebUI..."

# A. Start the RAG API Server (Backend)
# FIX: Use the virtual environment python explicitly
echo "   - Starting RAG API on Port 9000..."
cd /workspace/setup/src
nohup "$VENV_PATH/bin/python" rag_api_server.py > /workspace/rag_api.log 2>&1 &
sleep 5

# B. Start Open WebUI (Frontend)
# We use environment variables to PRE-CONFIGURE the connection to Port 9000
echo "   - Starting Open WebUI on Port 8080..."
fuser -k 8080/tcp > /dev/null 2>&1 || true

# CRITICAL: We extract the Ollama Port and set OPENAI_API_BASE_URL
OLLAMA_PORT=${OLLAMA_HOST##*:}

# We also use the venv python/bin path for open-webui to be safe
nohup env \
  HOST=0.0.0.0 \
  PORT=8080 \
  DATA_DIR=/workspace/webui_data \
  OLLAMA_BASE_URL=http://127.0.0.1:$OLLAMA_PORT \
  ENABLE_OPENAI_API=true \
  OPENAI_API_BASE_URL="http://127.0.0.1:9000/v1" \
  OPENAI_API_KEY="sk-auto-config" \
  "$VENV_PATH/bin/open-webui" serve > /workspace/webui.log 2>&1 &

echo "✅ ALL SYSTEMS GO!"
echo "   - WebUI: http://localhost:8080"
echo "   - RAG API: http://localhost:9000"
echo "   - Database: localhost:5432"
echo "--- PROVISIONING SCRIPT COMPLETE ---"