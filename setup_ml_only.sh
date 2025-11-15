po#!/bin/bash
# Exit immediately if a command exits with a non-zero status.
set -e

# --- Environment Variables ---
VENV_PATH="/workspace/rag_env"
MODEL_BASE_DIR="/workspace/models"
REPO_URL="https://github.com/Perly1258/setup.git" # Repository to clone
ONSTART_SCRIPT_URL="https://raw.githubusercontent.com/Perly1258/setup/refs/heads/main/onstart.sh" # URL for the companion startup script

# --- 1. System Dependency Installation ---
echo "--- 1. Installing System Dependencies & Cloning Repository ---"
cd /workspace
apt-get update
# Install basic tools and necessary dependencies
apt-get install -y --no-install-recommends \
    python3-venv git poppler-utils 

# --- CRITICAL ADDITION: Clone the GitHub repository into /workspace ---
echo "Cloning repository $REPO_URL into /workspace/setup"
git clone "$REPO_URL"

# --- 2. PYTHON VENV AND PACKAGE INSTALLATION ---
echo "--- 2. Setting up Python Virtual Environment and RAG Tools ---"
mkdir -p "$VENV_PATH"
mkdir -p "$MODEL_BASE_DIR"

if [ ! -f "$VENV_PATH/bin/activate" ]; then
    echo "Creating Python Virtual Environment: $VENV_PATH"
    python3 -m venv "$VENV_PATH"
fi

source "$VENV_PATH/bin/activate"

echo "Installing core Python packages..."

# Install PyTorch and related CUDA dependencies
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
# Install LLM, RAG, and necessary utility libraries
pip install transformers accelerate ipykernel spyder-kernels psycopg2-binary sentence-transformers
pip install langchain langchain-ollama pypdf pydantic huggingface-hub

# --- 3. MODEL PULLS (Download to persistent storage) ---
echo "--- 3. Downloading LLM and Embedding Models ---"


# --- A. Large Language Model (Mistral) ---
LLM_DIR="$MODEL_BASE_DIR/Mistral-7B-Instruct-v0.2"
LLM_REPO="mistralai/Mistral-7B-Instruct-v0.2"

# --- B. Embedding Model (BGE Small) ---
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
apt-get install -y --no-install-recommends \
    python3-venv git poppler-utils curl postgresql postgresql-contrib
sudo -u postgres psql -d rag_db -c "CREATE EXTENSION IF NOT EXISTS vector;"
ONNECTION_FILE="/workspace/setup/connection_file.json"

echo "Starting remote Python kernel and saving connection details to $CONNECTION_FILE"

# Start the kernel, listening on ALL IPs (0.0.0.0) so your local machine can connect
# The -f flag specifies the path for the JSON connection file.
python -m spyder_kernels.console --ip 0.0.0.0 -f "$CONNECTION_FILE"
CONNECTION_FILE="/workspace/setup/remotekernel.json"
python -m spyder_kernels.console --ip 0.0.0.0 -f "$CONNECTION_FILE"
deactivate

# CRITICAL: Download and install the companion startup script to /root/
echo "Downloading companion onstart script from $ONSTART_SCRIPT_URL"
wget -O /root/onstart.sh "$ONSTART_SCRIPT_URL"
chmod +x /root/onstart.sh
echo "Onstart script installed and made executable."

echo "--- PROVISIONING SCRIPT COMPLETE (ML Stack Ready) ---"
