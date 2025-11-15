po#!/bin/bash
# Exit immediately if a command exits with a non-zero status.
set -e

# --- Environment Variables ---
VENV_PATH="/workspace/mistral_env"
MODEL_BASE_DIR="/workspace/models"
REPO_URL="https://github.com/Perly1258/setup.git" # Repository to clone
ONSTART_SCRIPT_URL="[YOUR_RAW_URL_TO_ONSTART.SH]" # URL for the companion startup script

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
EMB_REPO="BAAI/bge-small-en-v1.5"

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

# --- 4. FINALIZATION AND ONSTART SETUP ---
echo "--- 4. Finalizing Setup and Installing Onstart Script ---"
echo "Registering venv kernel for Jupyter/Spyder."
python3 -m ipykernel install --user --name="mistral_venv" --display-name="Python (Mistral venv)"

deactivate

# CRITICAL: Download and install the companion startup script to /root/
echo "Downloading companion onstart script from $ONSTART_SCRIPT_URL"
wget -O /root/onstart.sh "$ONSTART_SCRIPT_URL"
chmod +x /root/onstart.sh
echo "Onstart script installed and made executable."

echo "--- PROVISIONING SCRIPT COMPLETE (ML Stack Ready) ---"
