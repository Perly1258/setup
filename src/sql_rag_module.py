import logging
import sys
import os
from sqlalchemy import create_engine
from llama_index.core import SQLDatabase
from llama_index.core.query_engine import BaseQueryEngine
from llama_index.core.tools import QueryEngineTool

# Configure logging
logger = logging.getLogger(__name__)

# --- Configuration ---
# CRITICAL: Table list for SQL RAG (MUST match the final DDL)
DB_TABLE_NAMES = [
    "pe_portfolio", 
    "pe_historical_cash_flows", 
    "pe_forecast_cash_flows", 
    "pe_modeling_rules",
    "schema_annotations" 
] 

# --- PostgreSQL Configuration (Using Environment Variables for Vast.ai/Container Portability) ---
DB_USER = os.environ.get("POSTGRES_USER", "postgres")
DB_PASS = os.environ.get("POSTGRES_PASSWORD", "postgres") 
DB_HOST = os.environ.get("DB_HOST", "127.0.0.1") 
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_NAME = os.environ.get("DB_NAME", "private_markets_db") 

CONNECTION_STRING = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

def get_sql_query_engine() -> tuple[BaseQueryEngine, QueryEngineTool]:
    """
    Initializes PostgreSQL connection, creates SQLDatabase object, and returns 
    the SQL Query Engine and its corresponding QueryEngineTool.
    """
    
    logger.info(f"Connecting to PostgreSQL at {DB_HOST}:{DB_PORT} as {DB_USER}...")
    
    try:
        sql_engine = create_engine(CONNECTION_STRING)
        # FIX APPLIED: Removed the problematic 'table_names_to_use' argument
        # We only pass 'include_tables' which handles which tables are loaded.
        sql_database = SQLDatabase(
            sql_engine, 
            include_tables=DB_TABLE_NAMES,
        )
        logger.info("Successfully connected to PostgreSQL for Structured Data RAG.")
    except Exception as e:
        logger.error(f"Failed to connect to PostgreSQL. Ensure DB service is running and credentials are correct. Connection String: {CONNECTION_STRING}. Error: {e}")
        # Note: sys.exit(1) is correctly placed here to stop execution if the DB connection fails
        sys.exit(1)
        
    # Define the Query Engine for Structured Data
    sql_query_engine = sql_database.as_query_engine(
        synthesize_response=True,
    )
    
    # Define the Structured Data Tool
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
    print("This module provides the SQL Query Engine and Tool.")