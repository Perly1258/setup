import os
import sys
import logging
import json
import psycopg2
from typing import Optional, List, Dict, Any

# --- LANGCHAIN IMPORTS ---
from langchain_community.llms import Ollama
from langchain.agents import AgentExecutor, create_react_agent
from langchain.tools import tool
from langchain import hub

# --- CONFIGURATION ---
DB_CONFIG = {
    "dbname": "private_markets_db",
    "user": "postgres",
    "password": "postgres",  # Update if needed
    "host": "localhost",
    "port": "5432"
}

LLM_MODEL = "deepseek-r1" # Or 'llama3', depending on what you have installed
LOG_LEVEL = "INFO"

# --- LOGGING SETUP ---
logging.basicConfig(
    stream=sys.stdout, 
    level=LOG_LEVEL, 
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ==============================================================================
# CLASS: DATABASE TOOLKIT
# This replaces all the manual Pandas logic from the old script.
# It calls the PL/Python functions we built in the SQL files.
# ==============================================================================
class PEDatabaseToolkit:
    def __init__(self):
        try:
            self.conn = psycopg2.connect(**DB_CONFIG)
            logger.info("✅ Connected to Postgres (SQL Logic Layer)")
        except Exception as e:
            logger.error(f"❌ Database Connection Failed: {e}")
            self.conn = None

    def _run_sql_func(self, func_name: str, params: tuple) -> str:
        """Helper to run the PL/Python functions returning JSON"""
        if not self.conn: return "Database not connected."
        
        # We wrap the function call in a SELECT statement
        query = f"SELECT {func_name}({', '.join(['%s'] * len(params))})"
        
        with self.conn.cursor() as cur:
            try:
                cur.execute(query, params)
                # The result is already a JSON string from the DB function
                result = cur.fetchone()[0]
                return result # It's a string representation of JSON
            except Exception as e:
                self.conn.rollback()
                return json.dumps({"error": str(e)})

    def close(self):
        if self.conn:
            self.conn.close()

# ==============================================================================
# LANGCHAIN TOOLS
# These are the instructions the DeepSeek Agent uses to interact with the DB.
# ==============================================================================

db_tool = PEDatabaseToolkit()

@tool
def get_portfolio_overview(dummy_arg: str = "") -> str:
    """
    Useful for answering questions about the ENTIRE portfolio.
    Returns Total TVPI, DPI, IRR, Paid-In, and Distributed for all funds combined.
    Input should be an empty string.
    """
    # Calls: fn_get_pe_metrics_py('PORTFOLIO', NULL)
    return db_tool._run_sql_func("fn_get_pe_metrics_py", ('PORTFOLIO', None))

@tool
def get_strategy_metrics(strategy_name: str) -> str:
    """
    Useful for questions about a specific PRIMARY STRATEGY (e.g., 'Venture Capital', 'Real Estate', 'Private Equity').
    Returns IRR, TVPI, Uncalled Capital, and Net/Gross performance.
    """
    # Calls: fn_get_pe_metrics_py('STRATEGY', 'Venture Capital')
    return db_tool._run_sql_func("fn_get_pe_metrics_py", ('STRATEGY', strategy_name))

@tool
def get_sub_strategy_metrics(sub_strategy_name: str) -> str:
    """
    Useful for questions about a SUB-STRATEGY (e.g., 'Growth Equity', 'Buyout', 'Distressed Debt').
    """
    # Calls: fn_get_pe_metrics_py('SUB_STRATEGY', 'Growth Equity')
    return db_tool._run_sql_func("fn_get_pe_metrics_py", ('SUB_STRATEGY', sub_strategy_name))

@tool
def get_fund_metrics(fund_name: str) -> str:
    """
    Useful for questions about a specific FUND (e.g., 'Pinnacle Tech Fund VI').
    Returns performance metrics for that single fund.
    """
    # Calls: fn_get_pe_metrics_py('FUND', 'Fund Name')
    return db_tool._run_sql_func("fn_get_pe_metrics_py", ('FUND', fund_name))

@tool
def get_historical_j_curve(strategy_name: str) -> str:
    """
    Useful for showing the 'J-Curve' or yearly cash flows (Net Cash Flow) for a strategy.
    Returns a list of years and cumulative cash flows.
    """
    # We query the VIEW directly for this simple data
    sql = """
        SELECT json_agg(t) FROM (
            SELECT cf_year, net_cash_flow, cumulative_net_cash_flow 
            FROM view_j_curve_cumulative 
            WHERE primary_strategy = %s 
            ORDER BY cf_year
        ) t
    """
    if not db_tool.conn: return "DB Error"
    with db_tool.conn.cursor() as cur:
        cur.execute(sql, (strategy_name,))
        res = cur.fetchone()[0]
        return json.dumps(res) if res else "No J-Curve data found."

@tool
def run_forecast_simulation(strategy_name: str, years: int = 5) -> str:
    """
    Useful for projecting/forecasting FUTURE cash flows.
    Runs the Takahashi-Alexander model simulation in the database.
    Input: Strategy Name (string) and Years (int, default 5).
    """
    quarters = years * 4
    # Calls: fn_run_takahashi_forecast('Strategy', quarters)
    return db_tool._run_sql_func("fn_run_takahashi_forecast", (strategy_name, quarters))

@tool
def get_forecast_results(strategy_name: str) -> str:
    """
    Useful for retrieving the results of a forecast AFTER running 'run_forecast_simulation'.
    Returns the projected Capital Calls, Distributions, and NAV by year.
    """
    sql = """
        SELECT json_agg(t) FROM (
            SELECT 
                EXTRACT(YEAR FROM quarter_date) as yr,
                forecast_type,
                SUM(amount_usd) as total_amount
            FROM pe_forecast_output
            WHERE strategy = %s
            GROUP BY 1, 2
            ORDER BY 1, 2
        ) t
    """
    if not db_tool.conn: return "DB Error"
    with db_tool.conn.cursor() as cur:
        cur.execute(sql, (strategy_name,))
        res = cur.fetchone()[0]
        return json.dumps(res) if res else "No forecast results found. Run simulation first."

@tool
def check_modeling_assumptions(strategy_name: str) -> str:
    """
    Useful for checking WHY a forecast looks the way it does.
    Returns the J-Curve assumptions, Target IRR, and Model Rationale.
    """
    sql = """
        SELECT row_to_json(t) FROM (
            SELECT * FROM pe_modeling_rules WHERE primary_strategy = %s
        ) t
    """
    with db_tool.conn.cursor() as cur:
        cur.execute(sql, (strategy_name,))
        res = cur.fetchone()
        return json.dumps(res[0]) if res else "No assumptions found."

# ==============================================================================
# AGENT SETUP
# ==============================================================================

def setup_agent():
    # 1. Define the Toolkit
    tools = [
        get_portfolio_overview,
        get_strategy_metrics,
        get_sub_strategy_metrics,
        get_fund_metrics,
        get_historical_j_curve,
        run_forecast_simulation,
        get_forecast_results,
        check_modeling_assumptions
    ]

    # 2. Initialize the LLM (DeepSeek via Ollama)
    try:
        llm = Ollama(model=LLM_MODEL, temperature=0)
    except Exception as e:
        logger.error("Could not connect to Ollama. Is it running?")
        sys.exit(1)

    # 3. Pull the Prompt Template (ReAct style)
    # We use a standard prompt but enforce the tool usage
    prompt = hub.pull("hwchase17/react")

    # 4. Create the Agent
    agent = create_react_agent(llm, tools, prompt)
    
    # 5. Create Executor (The runtime)
    # handle_parsing_errors=True is crucial for DeepSeek/Llama models as they sometimes chatter
    agent_executor = AgentExecutor(
        agent=agent, 
        tools=tools, 
        verbose=True, 
        handle_parsing_errors=True,
        max_iterations=10
    )
    
    return agent_executor

# ==============================================================================
# MAIN EXECUTION LOOP
# ==============================================================================
if __name__ == "__main__":
    
    print("\n" + "="*60)
    print(f"🤖 Private Equity Agent (SQL-Powered) | Model: {LLM_MODEL}")
    print("   Logic: Moved entirely to PostgreSQL (PL/Python functions)")
    print("="*60 + "\n")

    agent_executor = setup_agent()

    # The exact questions from your original request
    test_questions = [
        "What is the TVPI and DPI of the entire portfolio?",
        "Which primary strategy has the highest Internal Rate of Return (IRR)?",
        "What is the total Paid-In capital for the 'Growth Equity' sub-strategy?",
        "Which specific fund has distributed the most capital to date?", # Might require a custom query or iterating, let's see how Agent handles it
        "Show me the J-Curve for the 'Private Equity' strategy.",
        "What are the yearly net cash flows for the 'Venture Capital' strategy?",
        "What is the total remaining commitment (uncalled capital) for the 'Real Estate' strategy?",
        # New Forecast Questions
        "Run a 5-year forecast for 'Venture Capital' and show me the results.",
        "Why is the J-Curve for Venture Capital so deep? Check the assumptions."
    ]

    for i, question in enumerate(test_questions, 1):
        print(f"\n🔹 Q{i}: {question}")
        try:
            response = agent_executor.invoke({"input": question})
            print(f"🟢 Answer: {response['output']}")
        except Exception as e:
            print(f"🔴 Error: {e}")
            
    # Cleanup
    db_tool.close()