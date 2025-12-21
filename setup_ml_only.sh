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
git config --global user.email "alexander_foster@yahoo.com"
git config --global user.name "Perly1258"

PG_VERSION=$(psql --version | grep -oE '[0-9]+' | head -1)
echo "✅ Detected PostgreSQL version: $PG_VERSION"
apt-get install -y postgresql-${PG_VERSION}-pgvector

sudo service postgresql start

# --- NEW: CLEANUP EXISTING DATABASES ---
# -f forces disconnection of active users
sudo -u postgres dropdb --if-exists -f rag_db 
sudo -u postgres dropdb --if-exists -f private_markets_db 

# Recreate fresh
sudo -u postgres createdb rag_db
sudo -u postgres createdb private_markets_db

# Enable Extension
sudo -u postgres psql -d rag_db -c "CREATE EXTENSION IF NOT EXISTS vector;"
sudo -u postgres psql -c "ALTER USER postgres WITH PASSWORD 'postgres';"
sudo -u postgres PGPASSWORD='postgres' psql -U postgres -d private_markets_db -f /workspace/setup/db/setup/private_market_setup.sql
sudo -u postgres PGPASSWORD='postgres' psql -U postgres -d private_markets_db -f /workspace/setup/db/setup/rag_annotations.sql

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
pip install spyder-kernels numpy matplotlib
pip install llama-index-core llama-index-llms-ollama llama-index-embeddings-ollama \
            llama-index-vector-stores-postgres sqlalchemy psycopg2-binary \
            llama-index-readers-file pymupdf tabulate llama-index open-webui

echo "--- 3. Ollama Model Downloads and Server Start ---"
export OLLAMA_HOST="${OLLAMA_HOST:-0.0.0.0:21434}"
echo "Starting Ollama on: $OLLAMA_HOST"

ollama serve &
sleep 5 

ollama pull deepseek-r1:70b
ollama pull nomic-embed-text

CONNECTION_FILE="/workspace/setup/remotekernel.json"
echo "Starting remote Python kernel and saving connection details to $CONNECTION_FILE"
python -m spyder_kernels.console --ip 0.0.0.0 -f "$CONNECTION_FILE" &


#  Start JupyterLab (Development Environment) ---
# Kill any process whose command contains 'jupyter-notebook' or 'jupyter-lab'
#pkill -f "jupyter-notebook" || echo "No jupyter-notebook process found."
#pkill -f "jupyter-lab" || echo "No jupyter-lab process found."

JUPYTER_INTERNAL_PORT="18080"
echo "Starting JupyterLab (Port $JUPYTER_INTERNAL_PORT) ---"
# FIX: Launch Jupyter on the port Caddy is EXPECTING to proxy from (18080)
#nohup jupyter lab --port 18080 --ip=0.0.0.0 --no-browser --ServerApp.token='' --ServerApp.password='' > jupyter.log 2>&1 &
python -m ipykernel install --user --name=rag_env --display-name "Python (RAG Project)"

# --- START: AUTO-ACTIVATE VENV IN BASHRC ---
VENV_ACTIVATE_PATH="$VENV_PATH/bin/activate" 
ACTIVATE_CMD="source $VENV_ACTIVATE_PATH"

echo "Attempting to set auto-activation in ~/.bashrc..."

if [ -f "$VENV_ACTIVATE_PATH" ]; then
    if ! grep -q "$ACTIVATE_CMD" ~/.bashrc; then
        echo "" >> ~/.bashrc
        echo "# --- Auto-Activated Python Virtual Environment ---" >> ~/.bashrc
        echo "if [ -f \"$VENV_ACTIVATE_PATH\" ]; then" >> ~/.bashrc
        echo "    $ACTIVATE_CMD" >> ~/.bashrc
        echo "fi" >> ~/.bashrc
        echo "# -----------------------------------------------" >> ~/.bashrc
        echo "✅ Future terminals will auto-activate the venv."
    else
        echo "⚠️ Auto-activation command already exists in ~/.bashrc. Skipping."
    fi
else
    echo "❌ WARNING: Venv activation script not found at $VENV_ACTIVATE_PATH. Auto-activation skipped."
fi
# --- END: AUTO-ACTIVATE VENV IN BASHRC ---

source "$VENV_PATH/bin/activate"

echo "Downloading companion onstart script from $ONSTART_SCRIPT_URL"
wget -O /workspace/onstart.sh "$ONSTART_SCRIPT_URL"
chmod +x /workspace/setup/*.sh
