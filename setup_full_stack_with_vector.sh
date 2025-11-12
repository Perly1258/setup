#!/bin/bash
# Exit immediately if a command exits with a non-zero status.
# Use 'set -euxo pipefail' (uncommented) for detailed debugging output if issues persist.
set -e

# --- User-Defined Environment Variables (Set in Vast.ai Console) ---
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

# --- 1. System Update and Core Dependency Installation ---
echo "--- 1. Installing System Dependencies and Build Tools ---"
cd /workspace
apt-get update
apt-get install -y --no-install-recommends python3-venv git postgresql postgresql-contrib postgresql-server-dev-all build-essential make cmake poppler-utils libpq-dev 

# --- 2. POSTGRESQL SETUP (Initialization, Start, and pgvector install) ---
echo "--- 2. Setting up PostgreSQL and pgvector ---"
mkdir -p "$PG_DATA_PATH"

if [ ! -f "$PG_DATA_PATH/PG_VERSION" ]; then
    echo "Initializing new PostgreSQL cluster in $PG_DATA_PATH."
    
    # Get the installed PostgreSQL major version (e.g., '16')
    PG_FULL_VERSION=$(dpkg-query -W -f='${Version}' postgresql)
    PG_VERSION=$(echo "$PG_FULL_VERSION" | sed 's/\([0-9]*\).*/\1/')
    PG_BIN_DIR="/usr/lib/postgresql/$PG_VERSION/bin"
    
    # 1. Temporarily stop the default cluster that APT might have auto-started
    /usr/sbin/pg_dropcluster --stop "$PG_VERSION" main || true

    # CRITICAL FIX: Change directory ownership to postgres user (Fixes "Operation not permitted")
    echo "Fixing permissions on persistent data directory..."
    chown -R postgres:postgres "$PG_DATA_PATH"
    
    # 2. Initialize the cluster using the persistent data path (FIXED PATH and OWNER)
    echo "Running initdb using $PG_BIN_DIR/initdb"
    sudo -u postgres "$PG_BIN_DIR/initdb" -D "$PG_DATA_PATH" \
        --locale C --encoding UTF8

    export PGPASSWORD="$PG_PASSWORD"

    echo "Starting PostgreSQL temporarily for setup..."
    /usr/bin/pg_ctl -D "$PG_DATA_PATH" -o "-k /tmp" -l /tmp/postgres.log start

    # --- Install pgvector from source ---
    echo "Installing and compiling pgvector extension..."
    git clone --depth 1 https://github.com/pgvector/pgvector.git /tmp/pgvector
    cd /tmp/pgvector
    make clean
    make && make install

    # --- Create User, Database, and Enable pgvector ---
    echo "Creating user ($PG_USER), database ($PG_DB), and enabling extension..."

    # Use version-specific binaries for precision
    sudo -u postgres "$PG_BIN_DIR/createuser" --createdb --login --pwprompt "$PG_USER" <<EOF
$PG_PASSWORD
$PG_PASSWORD
EOF
    sudo -u postgres "$PG_BIN_DIR/createdb" -O "$PG_USER" "$PG_DB"
    
    # Enable the pgvector extension 
    /usr/bin/psql -d "$PG_DB" -U "$PG_USER" -c "CREATE EXTENSION vector;"

    # --- Initialize Database Schema and Data ---
    echo "Downloading and executing database schema and sample data from: $SQL_INIT_URL"
    
    wget -O "$LOCAL_SQL_FILE" "$SQL_INIT_URL"
    
    /usr/bin/psql -d "$PG_DB" -U "$PG_USER" -f "$LOCAL_SQL_FILE"
    
    echo "Stopping PostgreSQL service. Will be restarted by /root/onstart.sh."
    /usr/bin/pg_ctl -D "$PG_DATA_PATH" stop
    
    unset PGPASSWORD
else
    echo "PostgreSQL cluster already initialized. Skipping setup and compilation."
fi

# --- 3. PYTHON VENV AND PACKAGE INSTALLATION ---
echo "--- 3. Setting up Python Virtual Environment and RAG Tools ---"
VENV_PATH="/workspace/mistral_env"
mkdir -p "$VENV_PATH"

if [ ! -f "$VENV_PATH/bin/activate" ]; then
    echo "Creating Python Virtual Environment: $VENV_PATH"
    python3 -m venv "$VENV_PATH"
fi

source "$VENV_PATH/bin/activate"

echo "Installing core Python packages (LLM, RAG, and PostgreSQL client tools)..."

pip install torch torchvision torchaudio --index-url
