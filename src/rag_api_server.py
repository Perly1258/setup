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
logger = logging.getLogger(__name__)

# Database Config
DB_USER = os.environ.get("POSTGRES_USER", "postgres").strip()
DB_PASS = os.environ.get("POSTGRES_PASSWORD", "postgres").strip()
DB_HOST = os.environ.get("DB_HOST", "localhost").strip()
DB_PORT = os.environ.get("DB_PORT", "5432").strip()
DB_NAME = "rag_db"

# Ollama Config
OLLAMA_URL = os.environ.get("OLLAMA_HOST", "http://localhost:21434").strip()
if not OLLAMA_URL.startswith("http"):
    OLLAMA_URL = f"http://{OLLAMA_URL}"

PROJECT_ROOT = "/workspace/setup"
PDF_DIR = str(Path(PROJECT_ROOT) / "documents")
PERSIST_DIR = str(Path(PROJECT_ROOT) / "storage_pdf")

def setup_environment_and_engine():
    """
    Exported function for API Server to initialize the PDF engine.
    Returns a QueryEngine.
    """
    logger.info(f"--- Setting up PDF RAG Engine ---")
    logger.info(f"Targeting Ollama: {OLLAMA_URL}")

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
        # Quick test
        Settings.embed_model.get_query_embedding("test")
        logger.info("✅ Ollama Connected!")
    except Exception as e:
        logger.error(f"❌ Ollama Connection Failed: {e}")
        raise e

    # 4. CONNECT TO DATABASE
    logger.info("Connecting to Database...")
    vector_store = PGVectorStore.from_params(
        database=DB_NAME,
        host=DB_HOST,
        password=DB_PASS,
        port=DB_PORT,
        user=DB_USER,
        table_name="rag_documents",
        embed_dim=768
    )

    # 5. INDEXING LOGIC
    if os.path.exists(PERSIST_DIR):
        logger.info("Loading existing index...")
        storage_context = StorageContext.from_defaults(
            vector_store=vector_store, persist_dir=PERSIST_DIR
        )
        index = load_index_from_storage(storage_context)
    else:
        logger.info("Creating new index from documents...")
        if not os.path.exists(PDF_DIR):
             raise FileNotFoundError(f"PDF Directory not found: {PDF_DIR}")
             
        documents = SimpleDirectoryReader(PDF_DIR).load_data()
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        index = VectorStoreIndex.from_documents(
            documents, storage_context=storage_context
        )
        index.storage_context.persist(persist_dir=PERSIST_DIR)

    return index.as_query_engine(streaming=True)

# Main loop for standalone testing
if __name__ == "__main__":
    try:
        engine = setup_environment_and_engine()
        print("\n✅ System Ready. Type 'exit' to quit.\n")
        while True:
            q = input("Q: ")
            if q.lower() in ["exit", "quit"]: break
            print(f"A: {engine.query(q)}")
    except Exception as e:
        logger.error(f"Runtime Error: {e}")