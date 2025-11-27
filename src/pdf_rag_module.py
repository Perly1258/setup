import logging
from pathlib import Path
from sqlalchemy.engine import Engine

from llama_index.core import (
    SimpleDirectoryReader, 
    VectorStoreIndex, 
    StorageContext, 
    Settings,
    load_index_from_storage,
    get_response_synthesizer
)
from llama_index.core.node_parser import SentenceSplitter 
from llama_index.core.query_engine import BaseQueryEngine
from llama_index.vector_stores.postgres import PGVectorStore 

# Configure logging
logger = logging.getLogger(__name__)

# --- Configuration ---
REMOTE_PROJECT_ROOT = "/workspace/setup"
PDF_DIR = str(Path(REMOTE_PROJECT_ROOT) / "documents")
PERSIST_DIR = str(Path(REMOTE_PROJECT_ROOT) / "storage") # Local metadata cache
DB_VECTOR_TABLE = "rag_documents" 

def get_vector_query_engine(connection_string: str) -> BaseQueryEngine:
    """
    Loads or creates the Vector Index from PDF documents using PGVectorStore 
    and returns a query engine for unstructured data RAG.
    
    Args:
        connection_string: The PostgreSQL connection string.
    
    Returns:
        A LlamaIndex BaseQueryEngine for vector search.
    """
    
    logger.info("Setting up Vector Store for PDF RAG...")
    
    # PGVectorStore connects to PostgreSQL to store the vector embeddings
    vector_store = PGVectorStore(
        connection_string=connection_string, 
        # Embed dim must match the embed_model used in Settings (e.g., 768 for nomic)
        embed_dim=Settings.embed_model.get_query_embedding("test").shape[0], 
        table_name=DB_VECTOR_TABLE,
        schema_name="public",
    )
    
    try:
        # 1. Attempt to load existing index from local storage cache
        if Path(PERSIST_DIR).exists():
            storage_context = StorageContext.from_defaults(vector_store=vector_store, persist_dir=PERSIST_DIR)
            index = load_index_from_storage(storage_context)
            logger.info("Loaded existing Vector Index from local disk and PostgreSQL.")
        else:
            raise FileNotFoundError # Trigger creation logic if no local cache exists
    
    except Exception as e:
        logger.warning(f"Indexing required or error loading index: {e}. Starting re-indexing.")
        
        # 2. Indexing Logic (if load fails)
        
        # Load PDF documents from the documents folder
        documents = SimpleDirectoryReader(PDF_DIR).load_data()
        
        # Parse nodes (chunking the documents)
        parser = SentenceSplitter(chunk_size=1024, chunk_overlap=20)
        nodes = parser.get_nodes_from_documents(documents)
        
        # Create StorageContext pointing to the PGVectorStore
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        
        index = VectorStoreIndex(
            nodes,
            storage_context=storage_context,
            # Use the default LLM and embedding model from Settings
        )
        # Save the index metadata locally (for faster startup next time)
        index.storage_context.persist(persist_dir=PERSIST_DIR)
        logger.info("New Vector Index created and saved successfully.")

    # Define the Query Engine for Unstructured Data
    vector_query_engine = index.as_query_engine(
        similarity_top_k=5, 
        response_synthesizer=get_response_synthesizer(streaming=True)
    )
    return vector_query_engine

if __name__ == '__main__':
    # Example usage: This won't run correctly without a proper LlamaIndex Settings config (LLM/Embed)
    print("This module provides the Vector Query Engine and should be imported by hybrid_agent.py.")