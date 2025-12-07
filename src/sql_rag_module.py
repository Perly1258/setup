import logging
import sys
import os
import nest_asyncio
from sqlalchemy import create_engine
from llama_index.core import SQLDatabase, Settings
from llama_index.core.query_engine import BaseQueryEngine, NLSQLTableQueryEngine
from llama_index.core.tools import QueryEngineTool
from llama_index.llms.ollama import Ollama
from llama_index.embeddings.ollama import OllamaEmbedding

# 1. SETUP ENVIRONMENT (Vast.ai Fixes)
# Fix for Jupyter/Interactive loops
nest_asyncio.apply()
# Force localhost traffic to bypass proxies (Critical for Vast.ai)
os.environ["no_proxy"] = "localhost,127.0.0.1,0.0.0.0"

# Configure logging
logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Configuration ---

# CRITICAL: Table list for SQL RAG
DB_TABLE_NAMES = [
    "pe_portfolio", 
    "pe_historical_cash_flows", 
    "pe_forecast_cash_flows", 
    "pe_modeling_rules",
    "schema_annotations" 
] 

# --- Database Config (Reads from env or uses defaults) ---
# We strip() to avoid the "Could not parse URL" error from hidden newlines
DB_USER = os.environ.get("POSTGRES_USER", "postgres").strip()
DB_PASS = os.environ.get("POSTGRES_PASSWORD", "postgres").strip()
DB_HOST = os.environ.get("DB_HOST", "localhost").strip()
DB_PORT = os.environ.get("DB_PORT", "5432").strip()
DB_NAME = os.environ.get("DB_NAME", "private_markets_db").strip()

# --- Ollama Config (Auto-detects Vast.ai port) ---
# Automatically picks up 'http://0.0.0.0:21434' from your env if on Vast
OLLAMA_URL = os.environ.get("OLLAMA_HOST", "http://localhost:21434").strip()

def init_llm():
    """
    Initializes the global Settings with the correct Ollama instance.
    """
    try:
        logger.info(f"Connecting to Ollama at {OLLAMA_URL}...")
        Settings.llm = Ollama(
            model="mistral", 
            base_url=OLLAMA_URL, 
            request_timeout=120.0
        )
        Settings.embed_model = OllamaEmbedding(
            model_name="nomic-embed-text", 
            base_url=OLLAMA_URL
        )
        # Quick connectivity test
        Settings.embed_model.get_query_embedding("test")
        logger.info("✅ Ollama Connection Successful!")
    except Exception as e:
        logger.error(f"❌ Ollama Connection Failed: {e}")
        sys.exit(1)

def get_sql_query_engine() -> tuple[BaseQueryEngine, QueryEngineTool]:
    """
    Initializes PostgreSQL connection, creates SQLDatabase object, and returns 
    the SQL Query Engine and its corresponding QueryEngineTool.
    """
    # Ensure LLM is ready before creating the engine
    init_llm()
    
    # Construct Safe Connection String (Standard psycopg2 for SQL tasks)
    connection_string = f"postgresql+psycopg2://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    
    logger.info(f"Connecting to PostgreSQL at {DB_HOST}:{DB_PORT}...")
    
    try:
        sql_engine = create_engine(connection_string)
        
        # Initialize SQLDatabase with specific tables
        sql_database = SQLDatabase(
            sql_engine, 
            include_tables=DB_TABLE_NAMES,
        )
        logger.info("✅ Connected to PostgreSQL for Structured Data RAG.")
    except Exception as e:
        logger.error(f"FATAL: Database connection failed. Error: {e}")
        sys.exit(1)
        
    # Define the Query Engine (NLSQLTableQueryEngine is best for text-to-sql)
    sql_query_engine = NLSQLTableQueryEngine(
        sql_database=sql_database,
        synthesize_response=True, # Allows the LLM to write a sentence answer, not just raw rows
    )
    
    # Define the Tool (for use in larger agents)
    sql_tool = QueryEngineTool.from_defaults(
        query_engine=sql_query_engine,
        name="sql_table_tool",
        description=(
            "Use this tool for questions about financial metrics, commitments, NAV, cash flow amounts, "
            "vintage years, or projection rules. It queries the PostgreSQL tables directly."
        )
    )
    
    return sql_query_engine, sql_tool

# --- Standalone Execution Loop ---
if __name__ == '__main__':
    print("\n" + "="*50)
    print("--- Standalone SQL RAG Agent Ready ---")
    print(f"Targeting DB: {DB_NAME}")
    print(f"Targeting Ollama: {OLLAMA_URL}")
    print("="*50)

    try:
        # Initialize the engine
        query_engine, _ = get_sql_query_engine()
        
        print("\n✅ System Ready. Type 'exit' to quit.\n")
        
        while True:
            question = input("SQL Question: ")
            if question.lower() in ["quit", "exit"]:
                print("Goodbye!")
                break
            
            print("Generating SQL...")
            try:
                response = query_engine.query(question)
                print(f"\n📊 Answer: {response}")
                
                # Optional: Show the SQL it generated
                if hasattr(response, 'metadata') and response.metadata:
                    print(f"   (SQL Used: {response.metadata.get('sql_query', 'N/A')})")
                print("-" * 50)
                
            except Exception as e:
                print(f"❌ Query Failed: {e}")

    except Exception as e:
        logger.error(f"Runtime Error: {e}")