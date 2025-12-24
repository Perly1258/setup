#!/bin/bash
set -e

VENV_PATH="/workspace/rag_env"
MODEL_BASE_DIR="/workspace/models"
REPO_URL="https://github.com/Perly1258/setup.git"
ONSTART_SCRIPT_URL="https://raw.githubusercontent.com/Perly1258/setup/refs/heads/main/onstart.sh"

echo "--- 1. Installing System Dependencies & Cloning Repository ---"
cd /workspace

apt-get update

# Install prerequisites and setup PostgreSQL repository
apt-get install -y curl ca-certificates gnupg lsb-release
install -d /usr/share/postgresql-common/pgdg
curl -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc --fail https://www.postgresql.org/media/keys/ACCC4CF8.asc
sh -c 'echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list'
apt-get update

echo "Cloning repository $REPO_URL into /workspace/setup"
# To force an overwrite, the directory must be removed first as 'git clone --force' does not overwrite existing directories.
if [ -d "/workspace/setup" ]; then
    echo "Removing existing /workspace/setup directory for a fresh clone."
    rm -rf "/workspace/setup"
fi
git clone "$REPO_URL"
git config --global user.email "alexander_foster@yahoo.com"
git config --global user.name "Perly1258"


# Remove any previous PostgreSQL versions
apt-get remove --purge -y postgresql* || true

# Install PostgreSQL 16 with pgvector extension
# Note: postgresql-plpython3-16 is NO LONGER installed because the new architecture
# uses pure Python computation engines (src/engines/*.py) instead of database-resident
# PL/Python functions. Financial calculations (IRR, TVPI, projections) are now handled
# by pe_metrics_engine.py, cash_flow_engine.py, and projection_engine.py.
apt-get install -y --no-install-recommends \
    python3-venv git poppler-utils curl postgresql-16 postgresql-contrib postgresql-16-pgvector


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

# Setup database schema (data-only layer, no computation logic)
sudo -u postgres PGPASSWORD='postgres' psql -U postgres -d private_markets_db -f /workspace/setup/db/setup/private_market_setup.sql
sudo -u postgres PGPASSWORD='postgres' psql -U postgres -d private_markets_db -f /workspace/setup/db/setup/rag_annotations.sql

# MIGRATION NOTE: The following files are NO LONGER executed:
# - pe_logic_python.sql (replaced by src/engines/pe_metrics_engine.py)
# - pe_forecast_logic.sql (replaced by src/engines/projection_engine.py)
#
# The new architecture uses a "computation-first hybrid" approach where:
# - Database = Data-only layer (no PL/Python functions)
# - Computation = Pure Python engines (testable, debuggable, maintainable)
# - LLM Agent = Query understanding and response formatting only
#
# Old PL/Python functions like fn_get_pe_metrics_py() and fn_run_takahashi_forecast()
# have been replaced by equivalent pure Python functions in the engines/ directory.





echo "--- 2. Setting up Python Virtual Environment and RAG Tools ---"
mkdir -p "$VENV_PATH"
mkdir -p "$MODEL_BASE_DIR"

if [ ! -f "$VENV_PATH/bin/activate" ]; then
    echo "Creating Python Virtual Environment: $VENV_PATH"
    python3 -m venv "$VENV_PATH"
fi

source "$VENV_PATH/bin/activate"
pip install --upgrade pip

echo "Installing core Python packages..."
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
pip install transformers accelerate ipykernel psycopg2-binary sentence-transformers
pip install pypdf pydantic huggingface-hub
pip install spyder-kernels numpy matplotlib numpy_financial

# Install Open WebUI first to handle its strict pinning
pip install open-webui

# Install LlamaIndex and LangChain extensions separately to avoid resolution deadlocks
pip install llama-index-core llama-index-llms-ollama llama-index-embeddings-ollama \
            llama-index-vector-stores-postgres sqlalchemy psycopg2-binary \
            llama-index-readers-file pymupdf tabulate llama-index \
            langchain-ollama langchainhub

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

# ==============================================================================
# SETUP COMPLETE - New Architecture Ready
# ==============================================================================
echo ""
echo "════════════════════════════════════════════════════════════════════════"
echo "✅ Setup Complete! The PE Portfolio Analysis System is ready."
echo "════════════════════════════════════════════════════════════════════════"
echo ""
echo "📊 ARCHITECTURE:"
echo "   • Database: Data-only layer (no PL/Python computation)"
echo "   • Engines: Pure Python computation (src/engines/)"
echo "   • Agent: LLM-powered query interface (src/pe_agent_refactored.py)"
echo ""
echo "🚀 QUICK START:"
echo "   1. Activate environment: source /workspace/rag_env/bin/activate"
echo "   2. Run agent: python /workspace/setup/src/pe_agent_refactored.py"
echo "   3. Ask questions like:"
echo "      - 'What is the portfolio-level TVPI?'"
echo "      - 'Show me the top 5 funds by IRR'"
echo "      - 'Run a 5-year projection for Venture Capital'"
echo ""
echo "📖 DOCUMENTATION:"
echo "   • Architecture: /workspace/setup/README_NEW.md"
echo "   • Implementation: /workspace/setup/IMPLEMENTATION_SUMMARY.md"
echo "   • Tests: /workspace/setup/tests/"
echo ""
echo "🔧 KEY COMPONENTS:"
echo "   • PE Metrics Engine: src/engines/pe_metrics_engine.py"
echo "   • Cash Flow Engine: src/engines/cash_flow_engine.py"
echo "   • Projection Engine: src/engines/projection_engine.py"
echo "   • Agent Layer: src/pe_agent_refactored.py"
echo ""
echo "════════════════════════════════════════════════════════════════════════"
echo ""
