#!/bin/bash
# Exit immediately if a command exits with a non-zero status.
set -e

# --- Environment Variables ---
PG_DATA_PATH="/workspace/postgres_data"
PG_USER="vast_user"
PG_DB="vast_project_db"
PG_PASSWORD="vast_user" # <<< CRITICAL: CHANGE THIS PASSWORD

# URL for the initial data script (assuming you host init_data.sql next to this script)
SQL_INIT_URL="[YOUR_RAW_URL_TO_INIT_DATA.SQL]"
LOCAL_SQL_FILE="/tmp/init_data.sql"

# Determine the PostgreSQL binary directory for the current system
PG_VERSION_DIR=$(/usr/lib/postgresql/$(dpkg-query -W -f='${Version}' postgresql | cut -d. -f1)/bin)

echo "--- 1. System Update and Core Dependency Installation ---"
cd /workspace
apt-get update
# Install build tools needed for pgvector compilation and PDF processing
apt-get install -y \
    python3-venv git postgresql postgresql-contrib \
    postgresql-server-dev-all \
    build-essential make cmake poppler-utils \
    libpq-dev # Required for psycopg2

# --- 2. POSTGRESQL SETUP (Initialization, Start, and pgvector install) ---

mkdir -p "$PG_DATA_PATH"

if [ ! -f "$PG_DATA_PATH/PG_VERSION" ]; then
    echo "Initializing new PostgreSQL cluster."
    
    # Initialization and temporary start
    $PG_VERSION_DIR/initdb -D "$PG_DATA_PATH" --locale C --encoding UTF8

    # Set password environment variable for non-interactive commands
    export PGPASSWORD=$PG_PASSWORD

    echo "Starting PostgreSQL temporarily for pgvector setup..."
    $PG_VERSION_DIR/pg_ctl -D "$PG_DATA_PATH" -o "-k /tmp" -l /tmp/postgres.log start

    # --- Install pgvector from source (Most reliable method in a Docker container) ---
    echo "Installing and compiling pgvector extension..."
    git clone --depth 1 https://github.com/pgvector/pgvector.git /tmp/pgvector
    cd /tmp/pgvector
    make clean
    make && make install

    # --- Create User, Database, and Enable pgvector ---
    echo "Creating user ($PG_USER), database ($PG_DB), and enabling extension..."

    # Create the user and set password non-interactively
    $PG_VERSION_DIR/createuser --createdb --login --pwprompt $PG_USER <<EOF
$PG_PASSWORD
$PG_PASSWORD
EOF

    # Create the database owned by the new user
    $PG_VERSION_DIR/createdb -O $PG_USER $PG_DB
    
    # Enable the pgvector extension in the new database
    $PG_VERSION_DIR/psql -d $PG_DB -U $PG_USER -c "CREATE EXTENSION vector;"

    # --- NEW: Initialize Database Schema and Data ---
    echo "Downloading and executing database schema and sample data..."
    
    # NOTE: You must replace the placeholder below with the actual raw URL of init_data.sql
    wget -O $LOCAL_SQL_FILE "[YOUR_RAW_URL_TO_INIT_DATA.SQL]"
    
    # Execute the SQL script
    $PG_VERSION_DIR/psql -d $PG_DB -U $PG_USER -f $LOCAL_SQL_FILE
    
    echo "Stopping PostgreSQL service. Will be restarted by /root/onstart.sh."
    $PG_VERSION_DIR/pg_ctl -D "$PG_DATA_PATH" stop
    
    # Unset password environment variable
    unset PGPASSWORD
else
    echo "PostgreSQL cluster already initialized. Skipping setup and compilation."
fi

# --- 3. PYTHON VENV AND PACKAGE INSTALLATION ---

VENV_PATH="/workspace/mistral_env"
mkdir -p "$VENV_PATH"

if [ ! -f "$VENV_PATH/bin/activate" ]; then
    echo "Creating Python Virtual Environment: $VENV_PATH"
    python3 -m venv $VENV_PATH
fi

source $VENV_PATH/bin/activate

echo "Installing core Python packages (LLM, RAG, and PostgreSQL client tools)..."

pip install torch torchvision torchio --index-url https://download.pytorch.org/whl/cu121
pip install transformers accelerate ipykernel spyder-kernels psycopg2-binary
pip install langchain langchain-ollama pypdf pydantic sentence-transformers

# --- 4. MISTRAL MODEL PULL (Download to persistent storage) ---

MODEL_DIR="/workspace/mistral-7b"
MODEL_REPO="mistralai/Mistral-7B-Instruct-v0.2"

echo "Attempting to download Mistral model $MODEL_REPO to $MODEL_DIR..."

python3 -c "
from huggingface_hub import snapshot_download
import os

repo_id = os.environ.get('MODEL_REPO', '$MODEL_REPO')
model_dir = os.environ.get('MODEL_DIR', '$MODEL_DIR')

if not os.path.exists(model_dir) or not os.listdir(model_dir):
    print(f'Downloading model {repo_id}...')
    snapshot_download(repo_id=repo_id, local_dir=model_dir, local_dir_use_symlinks=False)
else:
    print('Mistral model already found. Skipping download.')
"

# --- 5. SPYDER KERNEL SETUP AND CLEANUP ---

echo "Registering venv kernel for Jupyter/Spyder."
python3 -m ipykernel install --user --name="mistral_venv" --display-name="Python (Mistral venv)"

deactivate
echo "--- PROVISIONING SCRIPT COMPLETE (Full Stack Ready) ---"
