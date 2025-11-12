#!/bin/bash
# Exit immediately if a command exits with a non-zero status.
set -euxo pipefail # Use this line for debugging, otherwise use 'set -e'

# --- User-Defined Environment Variables ---
PG_DATA_PATH="/workspace/postgres_data"
PG_USER="vast_user"
PG_DB="vast_project_db"

# CRITICAL: PG_PASSWORD must be set in the Vast.ai Environment Variables.
if [ -z "$PG_PASSWORD" ]; then
    echo "ERROR: PG_PASSWORD environment variable is not set. Exiting."
    exit 1
fi

# URL for the initial data script (Update this with your actual public raw URL)
SQL_INIT_URL="[YOUR_RAW_URL_TO_INIT_DATA.SQL]"
LOCAL_SQL_FILE="/tmp/init_data.sql"

# --- 1. Dependencies and Path Setup ---
echo "--- 1. Installing Dependencies and Determining Paths ---"
cd /workspace
apt-get update
apt-get install -y --no-install-recommends python3-venv git postgresql postgresql-contrib postgresql-server-dev-all build-essential make cmake poppler-utils libpq-dev 

# FIX: Dynamically find the correct PostgreSQL binary path (e.g., /usr/lib/postgresql/16/bin)
PG_FULL_VERSION=$(dpkg-query -W -f='${Version}' postgresql)
PG_VERSION=$(echo "$PG_FULL_VERSION" | sed 's/\([0-9]*\).*/\1/')
PG_BIN_DIR="/usr/lib/postgresql/$PG_VERSION/bin"

# --- 2. POSTGRESQL SETUP (Initialization, Start, and pgvector install) ---
echo "--- 2. Setting up PostgreSQL and pgvector ---"
mkdir -p "$PG_DATA_PATH"

if [ ! -f "$PG_DATA_PATH/PG_VERSION" ]; then
    echo "Initializing new PostgreSQL cluster in $PG_DATA_PATH."
    
    /usr/sbin/pg_dropcluster --stop "$PG_VERSION" main || true # Stop default cluster
    
    # Initialization using the FIXED version-specific path
    sudo -u postgres "$PG_BIN_DIR/initdb" -D "$PG_DATA_PATH" --locale C --encoding UTF8

    export PGPASSWORD="$PG_PASSWORD"

    echo "Starting PostgreSQL temporarily for setup..."
    /usr/bin/pg_ctl -D "$PG_DATA_PATH" -o "-k /tmp" -l /tmp/postgres.log start

    # --- Install pgvector from source ---
    git clone --depth 1 https://github.com/pgvector/pgvector.git /tmp/pgvector
    cd /tmp/pgvector
    make clean && make && make install

    # --- Create User, Database, and Enable pgvector (using $PG_BIN_DIR for precision) ---
    sudo -u postgres "$PG_BIN_DIR/createuser" --createdb --login --pwprompt "$PG_USER" <<EOF
$PG_PASSWORD
$PG_PASSWORD
EOF
    sudo -u postgres "$PG_BIN_DIR/createdb" -O "$PG_USER" "$PG_DB"
    /usr/bin/psql -d "$PG_DB" -U "$PG_USER" -c "CREATE EXTENSION vector;"

    # --- Initialize Database Schema and Data ---
    wget -O "$LOCAL_SQL_FILE" "$SQL_INIT_URL" # Download SQL data
    /usr/bin/psql -d "$PG_DB" -U "$PG_USER" -f "$LOCAL_SQL_FILE" # Execute SQL

    echo "Stopping PostgreSQL service. Will be restarted by /root/onstart.sh."
    /usr/bin/pg_ctl -D "$PG_DATA_PATH" stop
    unset PGPASSWORD
else
    echo "PostgreSQL cluster already initialized. Skipping setup and compilation."
fi

# --- 3. PYTHON VENV and RAG Tools ---
echo "--- 3. Setting up Python Virtual Environment and RAG Tools ---"
VENV_PATH="/workspace/mistral_env"
mkdir -p "$VENV_PATH"
[ ! -f "$VENV_PATH/bin/activate" ] && python3 -m venv "$VENV_PATH"
source "$VENV_PATH/bin/activate"

pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
pip install transformers accelerate ipykernel spyder-kernels psycopg2-binary sentence-transformers
pip install langchain langchain-ollama pypdf pydantic

# --- 4. MISTRAL MODEL PULL ---
echo "--- 4. Downloading Mistral Model ---"
MODEL_DIR="/workspace/mistral-7b"
MODEL_REPO="mistralai/Mistral-7B-Instruct-v0.2"
# Python block to handle model download...

# --- 5. FINALIZATION ---
echo "--- 5. Finalizing Setup ---"
python3 -m ipykernel install --user --name="mistral_venv" --display-name="Python (Mistral venv)"
deactivate
echo "--- PROVISIONING SCRIPT COMPLETE (Full Stack Ready) ---"
```eof

***

### 🔑 Critical Reminder

Please ensure you replace the placeholder:

`SQL_INIT_URL="[YOUR_RAW_URL_TO_INIT_DATA.SQL]"`

And set the **`PG_PASSWORD`** environment variable in the Vast.ai console when launching the instance.
