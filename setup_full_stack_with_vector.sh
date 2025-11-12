#!/bin/bash
# Exit immediately if a command exits with a non-zero status.
# Enable extreme debugging to trace execution: set -euxo pipefail
set -e

# --- Environment Variables (Referenced from Vast.ai Launch Settings) ---
PG_DATA_PATH="/workspace/postgres_data"
PG_USER="vast_user"
PG_DB="vast_project_db"

# NOTE: The PG_PASSWORD MUST be passed as an environment variable when launching
# the Vast.ai instance (e.g., PG_PASSWORD=MySecurePwd123)
if [ -z "$PG_PASSWORD" ]; then
    echo "ERROR: PG_PASSWORD environment variable is not set. Exiting."
    exit 1
fi

# URL for the initial data script (CHANGE THIS to your actual Raw URL)
SQL_INIT_URL="https://raw.githubusercontent.com/Perly1258/setup/main/init_data.sql"
LOCAL_SQL_FILE="/tmp/init_data.sql"

# --- 1. System Update and Core Dependency Installation ---
echo "--- 1. Installing System Dependencies and Build Tools ---"
cd /workspace
apt-get update
# Install build tools needed for pgvector compilation and PDF processing
apt-get install -y \
    python3-venv git postgresql postgresql-contrib \
    postgresql-server-dev-all \
    build-essential make cmake poppler-utils \
    libpq-dev # Required for psycopg2

# --- 2. POSTGRESQL SETUP (Initialization, Start, and pgvector install) ---
echo "--- 2. Setting up PostgreSQL and pgvector ---"
mkdir -p "$PG_DATA_PATH"

if [ ! -f "$PG_DATA_PATH/PG_VERSION" ]; then
    echo "Initializing new PostgreSQL cluster."
    
    # Initialization using the standard /usr/bin/initdb (FIXED PATH)
    /usr/bin/initdb -D "$PG_DATA_PATH" --locale C --encoding UTF8

    # Set password environment variable for non-interactive commands
    export PGPASSWORD=$PG_PASSWORD

    echo "Starting PostgreSQL temporarily for setup..."
    # Use standard pg_ctl with the persistent data directory
    /usr/bin/pg_ctl -D "$PG_DATA_PATH" -o "-k /tmp" -l /tmp/postgres.log start

    # --- Install pgvector from source (Most reliable method) ---
    echo "Installing and compiling pgvector extension..."
    git clone --depth 1 https://github.com/pgvector/pgvector.git /tmp/pgvector
    cd /tmp/pgvector
    make clean
    make && make install

    # --- Create User, Database, and Enable pgvector ---
    echo "Creating user ($PG_USER), database ($PG_DB), and enabling extension..."

    # Create the user and set password non-interactively
    /usr/bin/createuser --createdb --login --pwprompt $PG_USER <<EOF
$PG_PASSWORD
$PG_PASSWORD
EOF

    # Create the database owned by the new user
    /usr/bin/createdb -O $PG_USER $PG_DB
    
    # Enable the pgvector extension in the new database
    /usr/bin/psql -d $PG_DB -
