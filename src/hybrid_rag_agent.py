import os
import sys
import logging
from pathlib import Path

# --- LlamaIndex/PostgreSQL Imports ---
from sqlalchemy import create_engine
from llama_index.core import (
    SimpleDirectoryReader, 
    VectorStoreIndex, 
    StorageContext, 
    Settings,
    SQLDatabase, 
    load_index_from_storage,
    get_response_synthesizer
)
from llama_index.core.node_parser import SentenceSplitter 
from llama_index.llms.ollama import Ollama
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.vector_stores.postgres import PGVectorStore 
from llama_index.core.query_engine import RouterQueryEngine
from llama_index.core.tools import QueryEngineTool
from llama_index.core.selectors import LLMSingleSelector 
from llama_index.core.utilities.sql_wrapper import SQLTableRetriever

# Configure logging
logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logging.getLogger().addHandler(logging.StreamHandler(stream=sys.stdout))

# --- Configuration (Match your local environment and service names) ---
PDF_DIR = "documents" 
OLLAMA_MODEL = "mistral"     
EMBEDDING_MODEL = "nomic-embed-text" 
DB_VECTOR_TABLE = "rag_documents" 
# CRITICAL: Table list for SQL RAG (Must match your setup)
DB_TABLE_NAMES = ["pe_portfolio", "fund_cash_flows", "projected_cash_flows", "fund_model_assumptions"] 
PERSIST_DIR = "./storage" 

# --- PostgreSQL Configuration (Using hardcoded defaults for seamless initial setup) ---
# NOTE: Replace with os.environ.get if moving to production service deployment
DB_USER = "postgres"
DB_PASS = "postgres" 
DB_HOST = "localhost"
DB_PORT = "5432"
DB_NAME = "private_markets_db" 

CONNECTION_STRING = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434") 

# System prompt to guide the LLM's behavior (Crucial for routing and synthesis)
SYSTEM_PROMPT = (
    "You are a Hybrid Financial Analyst specialized in alternative assets. "
    "Your primary goal is to answer questions using two distinct sources: "
    "1. A Vector Store (for definitions, methodology, and documents). "
    "2. A SQL Database (for quantitative financial facts, projections, and numerical data). "
    "Always reference the source (the specific document or the table data) when possible. "
)

# --------------------------------------------------------------------------
# 1. SETUP: LLM, EMBEDDING, & CONNECTIONS
# --------------------------------------------------------------------------

def setup_llm_and_tools():
    """Initializes LLM, embedding model, and database engines."""
    
    # 1. Initialize LLM and Embedding Model (Running locally via Ollama)
    Settings.llm = Ollama(model=OLLAMA_MODEL, base_url=OLLAMA_HOST, system_prompt=SYSTEM_PROMPT, request_timeout=30.0)
    Settings.embed_model = OllamaEmbedding(model_name=EMBEDDING_MODEL, base_url=OLLAMA_HOST)
    
    # 2. Setup PostgreSQL Engine for Structured Data (SQL RAG)
    try:
        sql_engine = create_engine(CONNECTION_STRING)
        sql_database = SQLDatabase(sql_engine, include_tables=DB_TABLE_NAMES)
        logging.info("Successfully connected to PostgreSQL for Structured Data RAG.")
    except Exception as e:
        logging.error(f"Failed to connect to PostgreSQL. Ensure credentials, host, and DB name are correct: {e}")
        sys.exit(1)
        
    return sql_engine, sql_database

# --------------------------------------------------------------------------
# 2. INDEXING: VECTOR STORE (Unstructured PDF RAG)
# --------------------------------------------------------------------------

def get_vector_query_engine(sql_engine, sql_database):
    """Loads/creates the Vector Index from PDF documents."""
    
    # Use the SQL engine for storing vectors (PGVectorStore)
    vector_store = PGVectorStore(
        service_context=None,
        engine=sql_engine,
        embed_dim=Settings.embed_model.get_query_embedding("test").shape[0],
        table_name=DB_VECTOR_TABLE,
        schema_name="public",
    )
    
    try:
        # Attempt to load existing index from local storage cache
        storage_context = StorageContext.from_defaults(vector_store=vector_store, persist_dir=PERSIST_DIR)
        index = load_index_from_storage(storage_context)
        logging.info("Loaded existing Vector Index from disk.")
    
    except Exception:
        logging.info("Creating new Vector Index from documents...")
        
        # Load PDF documents
        documents = SimpleDirectoryReader(PDF_DIR).load_data()
        
        # Parse nodes and create index
        parser = SentenceSplitter(chunk_size=1024, chunk_overlap=20)
        nodes = parser.get_nodes_from_documents(documents)
        index = VectorStoreIndex(
            nodes,
            storage_context=StorageContext.from_defaults(vector_store=vector_store, persist_dir=PERSIST_DIR)
        )
        # Save the index metadata locally (for faster startup next time)
        index.storage_context.persist(persist_dir=PERSIST_DIR)
        logging.info("New Vector Index created and saved.")

    # Define the Query Engine for Unstructured Data
    vector_query_engine = index.as_query_engine(
        similarity_top_k=5, 
        response_synthesizer=get_response_synthesizer(streaming=True)
    )
    return vector_query_engine

# --------------------------------------------------------------------------
# 3. ROUTER: HYBRID RAG ENGINE
# --------------------------------------------------------------------------

def create_hybrid_router(sql_database, vector_query_engine):
    """Creates the router to choose between the SQL (structured) and Vector (unstructured) engines."""
    
    # 1. Define the Structured Data Tool (SQL RAG)
    # Using SQLTableRetriever to make sure the LLM only uses relevant table schemas
    sql_retriever = SQLTableRetriever(sql_database)
    
    sql_tool = QueryEngineTool.from_defaults(
        query_engine=sql_database.as_query_engine(
            synthesize_response=True,
            service_context=None
        ),
        name="sql_table_tool",
        description=(
            "Use this tool for questions about financial metrics, commitments, NAV, or forecasts. "
            "It queries PostgreSQL tables: PE_Portfolio, FUND_MODEL_ASSUMPTIONS, and PROJECTED_CASH_FLOWS. "
            "Example queries: 'What is the total commitment for Venture Capital?', 'Projected NAV for Fund X in Q4 2027'."
        )
    )
    
    # 2. Define the Unstructured Data Tool (PDF RAG)
    vector_tool = QueryEngineTool.from_defaults(
        query_engine=vector_query_engine,
        name="vector_document_tool",
        description=(
            "Use this tool for conceptual questions, definitions, rationale, methodology, "
            "or information contained within the external PDF documents (e.g., 'Explain the J-Curve', 'What is the goal of the Yale Model?')."
        )
    )
    
    # 3. Combine tools into the Router Query Engine
    router_query_engine = RouterQueryEngine(
        selector=LLMSingleSelector.from_defaults(),
        query_engine_tools=[sql_tool, vector_tool]
    )
    
    logging.info("Hybrid Router Query Engine is ready.")
    return router_query_engine

# --------------------------------------------------------------------------
# 4. MAIN CHAT LOOP
# --------------------------------------------------------------------------

if __name__ == "__main__":
    
    # 1. Setup connections
    sql_engine, sql_database = setup_llm_and_tools()
    
    # 2. Build the Vector Index
    # NOTE: This step only runs fully the first time to index documents
    vector_query_engine = get_vector_query_engine(sql_engine, sql_database)
    
    # 3. Create the Hybrid Router
    query_engine = create_hybrid_router(sql_database, vector_query_engine)

    print("\n" + "=" * 50)
    print("--- Hybrid RAG Financial Analyst Ready ---")
    print(f"PostgreSQL DB: {DB_NAME} | LLM: {OLLAMA_MODEL}")
    print("Ask a financial (SQL) or conceptual (PDF) question. Type 'exit' to quit.")
    print("=" * 50)

    while True:
        question = input("Your Question: ")
        if question.lower() in ["quit", "exit"]:
            print("Goodbye! Shutting down LLM connection.")
            break
        
        try:
            print("\nThinking...")
            # Execute the query through the router
            response = query_engine.query(question)
            
            # --- DEBUGGING OUTPUT (To show the routing decision and context used) ---
            print("\n" + "=" * 50)
            print(f"ROUTING DECISION: {response.metadata.get('selector_result', 'N/A')}")
            
            # Show retrieved context (either from SQL execution or VDB text chunks)
            if response.source_nodes:
                for i, node in enumerate(response.source_nodes):
                    # Check if the node is a standard VDB node or a SQL result node
                    if node.metadata.get('tool_name') == 'sql_table_tool':
                        print(f"--- Source {i+1}: SQL Result ---")
                        print(f"Query Run: {node.metadata.get('sql_query', 'N/A')}")
                        print(f"Result Data: {node.text[:400]}")
                    else:
                        print(f"--- Source {i+1}: PDF Chunk ---")
                        print(f"Source File: {node.metadata.get('file_name', 'N/A')}")
                        print(f"Text Snippet:\n{node.text[:400]}...")
                    print("-" * 15)
            else:
                  print("No specific context nodes returned (Synthesis was direct).")
            print("=" * 50)
            
            # --- MISTRAL ANSWER (Final Synthesis) ---
            print(f"💡 Mistral Answer: {str(response)}")
            print("-" * 50)
            
        except Exception as e:
            logging.error(f"An error occurred during query: {e}")
            break