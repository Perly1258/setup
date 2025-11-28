import os
import sys
import logging
import nest_asyncio
from pathlib import Path

from llama_index.core import (
    SimpleDirectoryReader,
    VectorStoreIndex,
    StorageContext,
    Settings,
    load_index_from_storage,
)
from llama_index.llms.ollama import Ollama
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.vector_stores.postgres import PGVectorStore

# 1. SETUP ENVIRONMENT
nest_asyncio.apply()
os.environ["no_proxy"] = "localhost,127.0.0.1,0.0.0.0"

# 2. CONFIGURATION
logging.basicConfig(stream=sys.stdout, level=logging.INFO)

# Database Config
DB_USER = os.environ.get("POSTGRES_USER", "postgres").strip()
DB_PASS = os.environ.get("POSTGRES_PASSWORD", "postgres").strip()
DB_HOST = os.environ.get("DB_HOST", "localhost").strip()
DB_PORT = os.environ.get("DB_PORT", "5432").strip()
DB_NAME = "rag_db"

# Ollama Config (Auto-detects Vast.ai port)
OLLAMA_URL = os.environ.get("OLLAMA_HOST", "http://localhost:11434").strip()

PROJECT_ROOT = "/workspace/setup"
PDF_DIR = f"{PROJECT_ROOT}/documents"
PERSIST_DIR = f"{PROJECT_ROOT}/storage_pdf"

def main():
    print(f"--- Starting PDF RAG (Auto-Update) ---")
    print(f"Targeting Ollama: {OLLAMA_URL}")

    # 3. CONNECT TO OLLAMA
    try:
        Settings.llm = Ollama(
            model="mistral", 
            base_url=OLLAMA_URL,
            request_timeout=120.0
        )
        Settings.embed_model = OllamaEmbedding(
            model_name="nomic-embed-text", 
            base_url=OLLAMA_URL
        )
        Settings.embed_model.get_query_embedding("test")
        print("✅ Ollama Connected!")
    except Exception as e:
        print(f"❌ Ollama Connection Failed: {e}")
        return

    # 4. CONNECT TO DATABASE
    print("Connecting to Database...")
    vector_store = PGVectorStore.from_params(
        database=DB_NAME,
        host=DB_HOST,
        password=DB_PASS,
        port=DB_PORT,
        user=DB_USER,
        table_name="rag_documents",
        embed_dim=768
    )

    # 5. INTELLIGENT INDEXING
    print(f"Scanning '{PDF_DIR}' for documents...")
    if not os.path.exists(PDF_DIR):
        print(f"❌ Error: Directory not found: {PDF_DIR}")
        return

    # Always load files from the directory first
    current_documents = SimpleDirectoryReader(PDF_DIR).load_data()
    print(f"Found {len(current_documents)} document chunks in folder.")

    if os.path.exists(PERSIST_DIR):
        print("Loading existing index metadata...")
        storage_context = StorageContext.from_defaults(
            vector_store=vector_store, persist_dir=PERSIST_DIR
        )
        index = load_index_from_storage(storage_context)

        # --- THE FIX: Refresh the index with new files ---
        print("Checking for new or updated files...")
        # 'refresh_ref_docs' checks if docs in 'current_documents' are already in the index
        refreshed_docs = index.refresh_ref_docs(current_documents)
        
        # Calculate how many were actually new/updated (returns a list of booleans)
        files_updated_count = sum(refreshed_docs)
        if files_updated_count > 0:
            print(f"🔄 Detected changes. Added/Updated {files_updated_count} chunks.")
            # Save the updated mapping to disk
            index.storage_context.persist(persist_dir=PERSIST_DIR)
        else:
            print("✅ Index is up to date. No new files.")
            
    else:
        print("No local index found. Creating new index from scratch...")
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        index = VectorStoreIndex.from_documents(
            current_documents, storage_context=storage_context
        )
        index.storage_context.persist(persist_dir=PERSIST_DIR)
        print("✅ New index created and saved.")

    # 6. CHAT LOOP
    query_engine = index.as_query_engine(streaming=True)
    print("\n✅ System Ready. Type 'exit' to quit.\n")

    while True:
        question = input("Q: ")
        if question.lower() in ["exit", "quit"]:
            break
        print("Thinking...")
        response = query_engine.query(question)
        print(f"A: {response}\n")

if __name__ == "__main__":
    main()