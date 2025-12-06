#!/bin/bash
# start_rag_webui.sh

# --- RAG WEB SERVER STARTUP ---
echo "--- RAG WEB SERVER STARTUP ---"
echo "Starting the RAG API server. Ollama is active on 21434."
echo "ENSURE POSTGRESQL (on 5432) IS RUNNING FIRST!"
echo "-----------------------------------"

# 1. Set environment variables to connect to local services
# These match the defaults in your pdf_rag_module.py
export POSTGRES_USER="postgres"
export POSTGRES_PASSWORD="postgres"
export DB_HOST="localhost"
export DB_PORT="5432"

# Ollama Configuration
# CRITICAL FIX: The native 'ollama' library must be set using only the host:port format 
# when read from OLLAMA_HOST environment variable, or it throws the "Port out of range" error.
# We set it to the plain host:port here.
export OLLAMA_HOST="localhost:21434"

# 2. Create required directories (if they don't exist)
mkdir -p documents
mkdir -p storage_pdf

# 3. Start the FastAPI application (api_server.py) using uvicorn
echo "Starting FastAPI server on http://localhost:9000.."
# FIX: Changed 'api_server:app' to 'src.api_server:app' assuming api_server.py 
# is located in a 'src' subdirectory for correct module loading.
uvicorn src.api_server:app --host 0.0.0.0 --port 9000
