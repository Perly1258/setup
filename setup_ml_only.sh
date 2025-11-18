#!/bin/bash
set -e

VENV_PATH="/workspace/rag_env"
MODEL_BASE_DIR="/workspace/models"
REPO_URL="https://github.com/Perly1258/setup.git"
ONSTART_SCRIPT_URL="https://raw.githubusercontent.com/Perly1258/setup/refs/heads/main/onstart.sh"

echo "--- 1. Installing System Dependencies & Cloning Repository ---"
cd /workspace
# FIX: Corrected the update command
apt-get update
# Cleaned up the redundant install line
apt-get install -y --no-install-recommends \
    python3-venv git poppler-utils curl postgresql postgresql-contrib postgresql-16-pgvector
    
echo "Cloning repository $REPO_URL into /workspace/setup"
git clone "$REPO_URL"
cd /workspace/setup/db
# PostgreSQL Setup (Relocated and kept clean)
sudo service postgresql start
sudo -u postgres createdb rag_db
sudo -u postgres psql -d rag_db -c "CREATE EXTENSION IF NOT EXISTS vector;"
sudo -u postgres psql -c "ALTER USER postgres WITH PASSWORD 'postgres';"
sudo -u postgres PGPASSWORD='postgres' psql -U postgres -d postgres -f private_market_setup.sql


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
pip install spyder-kernels==3.0.5
pip install llama-index-core llama-index-llms-ollama llama-index-embeddings-ollama \
            llama-index-vector-stores-postgres sqlalchemy psycopg2-binary \
            llama-index-readers-file pymupdf

echo "--- 3. Ollama Model Downloads and Server Start ---"
# Start the Ollama server in the background
ollama serve &
# Give the server a moment to start (optional, but safer)
sleep 5 

ollama pull mistral
ollama pull nomic-embed-text
# Note: bge-small is often superseded by nomic-embed-text, but kept for completeness
# ollama pull bge-small 

CONNECTION_FILE="/workspace/setup/remotekernel.json"
echo "Starting remote Python kernel and saving connection details to $CONNECTION_FILE"

# Start the remote kernel in the background
python -m spyder_kernels.console --ip 0.0.0.0 -f "$CONNECTION_FILE" &

# FIX: Deactivate the virtual environment
deactivate

echo "Downloading companion onstart script from $ONSTART_SCRIPT_URL"
# Note: Changed /Workspace/ to /workspace/
wget -O /workspace/onstart.sh "$ONSTART_SCRIPT_URL"
chmod +x /workspace/onstart.sh
echo "Onstart script installed and made executable."

echo "--- PROVISIONING SCRIPT COMPLETE (ML Stack Ready) ---"
