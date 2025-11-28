import os
import sys
import logging
from pathlib import Path
from sqlalchemy import create_engine
import psycopg2 
from llama_index.core import (
    SimpleDirectoryReader, 
    VectorStoreIndex, 
    StorageContext, 
    Settings,
    load_index_from_storage,
    get_response_synthesizer
)
from llama_index.core.node_parser import SentenceSplitter 
from llama_index.llms.ollama import Ollama
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.vector_stores.postgres import PGVectorStore 

# Configure logging
logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)

# --- CONFIGURATION (Common Setup) ---
OLLAMA_MODEL = "mistral"     
EMBEDDING_MODEL = "nomic-embed-text" 
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434") 

# PostgreSQL Connection Details (for Vector Store)
DB_USER = os.environ.get("POSTGRES_USER", "postgres")
DB_PASS = os.environ.get("POSTGRES_PASSWORD", "postgres") 
DB_HOST = os.environ.get("DB_HOST", "127.0.0.1") 
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_NAME = os.environ.get("DB_NAME", "private_markets_db") 

# Database Driver Prefix
DB_URL_PREFIX = "postgresql" 


# PDF RAG Specific Configuration
REMOTE_PROJECT_ROOT = "/workspace/setup"
PDF_DIR = str(Path(REMOTE_PROJECT_ROOT) / "documents")
PERSIST_DIR = str(Path(REMOTE_PROJECT_ROOT) / "storage_pdf") 
DB_VECTOR_TABLE = "rag_documents" 

SYSTEM_PROMPT = (
    "You are a Conceptual Financial Analyst. Your sole purpose is to retrieve and synthesize "
    "information from the provided documents (PDF Vector Store). Do NOT attempt to generate SQL "
    "or look for quantitative data. Focus on definitions, methodology, rationale, and conceptual analysis."
)
# --------------------------------------------------------------------------
# 1. SETUP: LLM, EMBEDDING, & VECTOR INDEXING
# --------------------------------------------------------------------------

def setup_environment_and_engine():
    """Initializes LLM and loads/creates the Vector Index."""
    
    logger.info("Starting environment setup...")
    
    # 1. Resolve Connection String and debug inputs
    CONNECTION_STRING = f"{DB_URL_PREFIX}://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    
    # CRITICAL DEBUGGING LOGS (MUST BE FIRST)
    logger.info(f"DB_USER: '{DB_USER}'")
    logger.info(f"DB_PASS (Presence Check): {'PASS_SET' if DB_PASS else 'PASS_EMPTY'}")
    logger.info(f"DB_HOST: '{DB_HOST}'")
    logger.info(f"DB_PORT: '{DB_PORT}'")
    logger.info(f"DB_NAME: '{DB_NAME}'")
    # Log the sanitized connection string for inspection
    logger.info(f"Resolved DB Connection String (Sanitized): {DB_URL_PREFIX}://{DB_USER}:*****@{DB_HOST}:{DB_PORT}/{DB_NAME}")


    logger.info(f"Initializing LLM ({OLLAMA_MODEL}) and Embedding Model ({EMBEDDING_MODEL})...")
    
    try:
        # Set global LlamaIndex settings
        Settings.llm = Ollama(model=OLLAMA_MODEL, base_url=OLLAMA_HOST, system_prompt=SYSTEM_PROMPT, request_timeout=120.0)
        Settings.embed_model = OllamaEmbedding(model_name=EMBEDDING_MODEL, base_url=OLLAMA_HOST)
    except Exception as e:
        logger.error(f"Failed to initialize Ollama services. Error: {e}")
        sys.exit(1)

    logger.info("Setting up Vector Store for PDF RAG...")
    
    # Calculate embedding dimension
    try:
        embedding_vector = Settings.embed_model.get_query_embedding("test")
        embed_dim = len(embedding_vector)
        logger.info(f"Detected embedding dimension: {embed_dim}")
    except Exception as e:
        logger.error(f"Failed to retrieve embedding dimension: {e}")
        sys.exit(1)

    # Validate SQLAlchemy connection string before passing it
    try:
        # Create a temporary engine just to test the connection string validity
        temp_engine = create_engine(CONNECTION_STRING)
        temp_engine.dispose()
        logger.info("SQLAlchemy URL resolved successfully.")
    except Exception as e:
        # If this fails, the URL format is definitely the issue
        logger.error(f"Could not resolve SQLAlchemy URL. Check DB_USER, DB_PASS, DB_HOST, DB_PORT, or DB_NAME for malformed values.")
        logger.error(f"SQLAlchemy URL Error: {e}")
        sys.exit(1)


    # PGVectorStore connects to PostgreSQL
    vector_store = PGVectorStore(
        connection_string=CONNECTION_STRING, 
        embed_dim=embed_dim, 
        table_name=DB_VECTOR_TABLE,
        schema_name="public",
    )
    
    try:
        # Try loading from local cache first
        if Path(PERSIST_DIR).exists():
            storage_context = StorageContext.from_defaults(vector_store=vector_store, persist_dir=PERSIST_DIR)
            index = load_index_from_storage(storage_context)
            logger.info("Loaded existing Vector Index.")
        else:
            raise FileNotFoundError 
    
    except Exception as e:
        logger.warning(f"Indexing required or error loading index: {e}. Starting re-indexing.")
        
        # Indexing Logic
        documents = SimpleDirectoryReader(PDF_DIR).load_data()
        parser = SentenceSplitter(chunk_size=1024, chunk_overlap=20)
        nodes = parser.get_nodes_from_documents(documents)
        
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        index = VectorStoreIndex(nodes, storage_context=storage_context)
        
        Path(PERSIST_DIR).mkdir(parents=True, exist_ok=True)
        index.storage_context.persist(persist_dir=PERSIST_DIR)
        logger.info("New Vector Index created and saved successfully.")

    # Define the Query Engine
    query_engine = index.as_query_engine(
        similarity_top_k=5, 
        response_synthesizer=get_response_synthesizer(streaming=True)
    )
    return query_engine

# --------------------------------------------------------------------------
# 2. MAIN CHAT LOOP
# --------------------------------------------------------------------------

if __name__ == "__main__":
    
    try:
        # NOTE: Restart Spyder/IPython kernel before running this after saving!
        query_engine = setup_environment_and_engine()

        print("\n" + "=" * 50)
        print("--- Standalone PDF RAG Agent Ready ---")
        print("Focus: Conceptual, Definitions, and Methodology (Documents)")
        print(f"LLM: {OLLAMA_MODEL}")
        print("=" * 50)

        while True:
            question = input("Conceptual Question: ")
            if question.lower() in ["quit", "exit"]:
                print("Goodbye! Shutting down LLM connection.")
                break
            
            print("\nThinking...")
            response = query_engine.query(question)
            
            print("\n" + "=" * 50)
            if response.source_nodes:
                print("RETRIEVED CONTEXT (VERIFICATION):")
                for i, node in enumerate(response.source_nodes):
                    print(f"--- Source (PDF Chunk) ---")
                    print(f"Source File: {node.metadata.get('file_name', 'N/A')}")
                    print(f"Text Snippet:\n{node.text[:400]}...")
                    print("-" * 15)
            
            print(f"💡 LLM Answer: {str(response)}")
            print("-" * 50)
            
    except Exception as e:
        logger.error(f"An error occurred during execution: {e}")