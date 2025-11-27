import logging
import sys
from sqlalchemy import create_engine
from llama_index.core import SQLDatabase
from llama_index.core.query_engine import BaseQueryEngine
from llama_index.core.tools import QueryEngineTool

# Configure logging
logger = logging.getLogger(__name__)

# --- Configuration ---
# CRITICAL: Table list for SQL RAG (MUST match the final DDL from private_market_setup.sql)
DB_TABLE_NAMES = [
    "pe_portfolio", 
    "pe_historical_cash_flows", 
    "pe_forecast_cash_flows", 
    "pe_modeling_rules",
    "schema_annotations" # Include this for contextual information retrieval (Advanced RAG)
] 

# --- PostgreSQL Configuration (Using hardcoded defaults for seamless initial setup) ---
DB_USER = "postgres"
DB_PASS = "postgres" 
DB_HOST = "127.0.0.1" 
DB_PORT = "5432"
DB_NAME = "private_markets_db" 

CONNECTION_STRING = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

def get_sql_query_engine() -> tuple[BaseQueryEngine, QueryEngineTool]:
    """
    Initializes PostgreSQL connection, creates SQLDatabase object, and returns 
    the SQL Query Engine and its corresponding QueryEngineTool.
    
    Returns:
        A tuple containing (SQL Query Engine, SQL Query Engine Tool).
    """
    
    logger.info(f"Connecting to PostgreSQL at {DB_HOST}:{DB_PORT}...")
    
    # 1. Setup PostgreSQL Engine for Structured Data (SQL RAG)
    try:
        sql_engine = create_engine(CONNECTION_STRING)
        # SQLDatabase initializes the database connection and exposes schemas
        sql_database = SQLDatabase(
            sql_engine, 
            include_tables=DB_TABLE_NAMES,
            # Optionally set tables to be used (metadata names from DDL)
            table_names_to_use=DB_TABLE_NAMES
        )
        logger.info("Successfully connected to PostgreSQL for Structured Data RAG.")
    except Exception as e:
        logger.error(f"Failed to connect to PostgreSQL. Ensure DB service is running and credentials are correct. Error: {e}")
        sys.exit(1)
        
    # 2. Define the Query Engine for Structured Data
    sql_query_engine = sql_database.as_query_engine(
        synthesize_response=True,
        # Optional: Add system prompt specific to SQL generation if needed
    )
    
    # 3. Define the Structured Data Tool
    sql_tool = QueryEngineTool.from_defaults(
        query_engine=sql_query_engine,
        name="sql_table_tool",
        description=(
            "Use this tool for questions about financial metrics, commitments, NAV, cash flow amounts, "
            "vintage years, or projection rules. It queries the PostgreSQL tables: "
            "pe_portfolio, pe_modeling_rules, pe_historical_cash_flows, and pe_forecast_cash_flows. "
            "IMPORTANT: Amounts are in US dollars (not millions). "
            "Example queries: 'What is the total commitment for Venture Capital?', 'What is the largest profit distribution?'"
        )
    )
    
    return sql_query_engine, sql_tool

if __name__ == '__main__':
    # Example usage: This won't run correctly without a proper LlamaIndex Settings config (LLM/Embed)
    print("This module provides the SQL Query Engine and Tool and should be imported by hybrid_agent.py.")