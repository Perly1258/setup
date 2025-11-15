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
    python3-venv git poppler-utils 
apt-get install -y --no-install-recommends \
      curl postgresql postgresql-contrib
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
pip install transformers accelerate ipykernel spyder-kernels psycopg2-binary sentence-transformers
pip install langchain langchain-ollama pypdf pydantic huggingface-hub

echo "--- 3. Downloading LLM and Embedding Models ---"


LLM_DIR="$MODEL_BASE_DIR/Mistral-7B-Instruct-v0.2"
LLM_REPO="mistralai/Mistral-7B-Instruct-v0.2"

EMB_DIR="$MODEL_BASE_DIR/bge-small-en-v1.5"
EMB_REPO="BAAI/c-v1.5"

python3 -c "
from huggingface_hub import snapshot_download
import os

def download_model(repo_id, local_dir):
    if not os.path.exists(local_dir) or not os.listdir(local_dir):
        print(f'Downloading model {repo_id} to {local_dir}...')
        snapshot_download(repo_id=repo_id, local_dir=local_dir, local_dir_use_symlinks=False)
    else:
        print(f'Model {repo_id} already found. Skipping download.')

download_model('$LLM_REPO', '$LLM_DIR')
download_model('$EMB_REPO', '$EMB_DIR')
"
ollama pull mistral
ollama pull bge-small

CONNECTION_FILE="/workspace/setup/connection_file.json"

"
echo "Starting remote Python kernel and saving connection details to $CONNECTION_FILE"
python -m spyder_kernels.console --ip 0.0.0.0 -f "$CONNECTION_FILE" &


echo "Downloading companion onstart script from $ONSTART_SCRIPT_URL"
wget -O /Workspace/onstart.sh "$ONSTART_SCRIPT_URL"
chmod +x /workspace/onstart.sh
echo "Onstart script installed and made executable."

echo "--- PROVISIONING SCRIPT COMPLETE (ML Stack Ready) ---"
