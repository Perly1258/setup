#!/bin/bash

VENV_PATH="/workspace/rag_env"
MODEL_BASE_DIR="/workspace/models"
REPO_URL="https://github.com/Perly1258/setup.git"
ONSTART_SCRIPT_URL="https://raw.githubusercontent.com/Perly1258/setup/refs/heads/main/onstart.sh"

echo "--- 1. Installing System Dependencies & Cloning Repository ---"
cd /workspace
apt-get updateroot
apt-get install -y --no-install-recommends \
    python3-venv git poppler-utils curl postgresql postgresql-contrib curl postgresql postgresql-contrib postgresql-16-pgvector
    
sudo service postgresql start
sudo -u postgres createdb rag_db
sudo -u postgres psql -d rag_db -c "CREATE EXTENSION IF NOT EXISTS vector;" 

echo "Cloning repository $REPO_URL into /workspace/setup"
git clone "$REPO_URL"

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
pip install spyder-kernels==3.0.7

ollama serve &
ollama pull mistral 
ollama pull bge-small 
# Start the Ollama server (usually needs to be run in the background or a separate terminal)

CONNECTION_FILE="/workspace/setup/remotekernel.json"

echo "Starting remote Python kernel and saving connection details to $CONNECTION_FILE"
python -m spyder_kernels.console --ip 0.0.0.0 -f "$CONNECTION_FILE" &


echo "Downloading companion onstart script from $ONSTART_SCRIPT_URL"
wget -O /Workspace/onstart.sh "$ONSTART_SCRIPT_URL"
chmod +x /workspace/onstart.sh
echo "Onstart script installed and made executable."

echo "--- PROVISIONING SCRIPT COMPLETE (ML Stack Ready) ---"
