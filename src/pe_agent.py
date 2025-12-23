import os
import sys
import logging
import json
import psycopg2
import ast
from typing import List, Dict, Any
import re

from langchain_ollama import OllamaLLM
from langchain.agents import AgentExecutor, create_react_agent
from langchain.prompts import PromptTemplate
from langchain.tools import tool

# --- CONFIGURATION ---
DB_CONFIG = {
    "dbname": "private_markets_db",
    "user": "postgres",
    "password": "postgres",
    "host": "localhost",
    "port": "5432"
}

LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-r1:32b")
LOG_LEVEL = "INFO"

logging.basicConfig(
    stream=sys.stdout, 
    level=LOG_LEVEL, 
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ==============================================================================
# DATABASE TOOLKIT
# ==============================================================================
class PEDatabaseToolkit:
    def __init__(self):
        try:
            self.conn = psycopg2.connect(**DB_CONFIG)
            logger.info("✅ Connected to Postgres")
        except Exception as e:
            logger.error(f"❌ Database Connection Failed: {e}")
            self.conn = None

    def run_sql_func(self, func_name: str, params: tuple) -> str:
        """Run PL/Python functions returning JSON"""
        if not self.conn:
            return "Database not connected."
        
        query = f"SELECT {func_name}({', '.join(['%s'] * len(params))})"
        
        with self.conn.cursor() as cur:
            try:
                logger.info(f"🔍 Executing SQL: {query} | Params: {params}")
                cur.execute(query, params)
                return cur.fetchone()[0]
            except Exception as e:
                self.conn.rollback()
                return json.dumps({"error": str(e)})

    def run_sql_query(self, sql: str, params: tuple = ()) -> str:
        """Run arbitrary SQL query returning JSON"""
        if not self.conn:
            return "Database not connected."
        
        with self.conn.cursor() as cur:
            try:
                logger.info(f"🔍 Executing SQL: {sql} | Params: {params}")
                cur.execute(sql, params)
                result = cur.fetchone()
                if result:
                    return json.dumps(result[0]) if isinstance(result[0], (dict, list)) else str(result[0])
                return "No results found."
            except Exception as e:
                self.conn.rollback()
                return json.dumps({"error": str(e)})

    def close(self):
        if self.conn:
            self.conn.close()

# ==============================================================================
# LANGCHAIN TOOLS
# ==============================================================================

db_tool = PEDatabaseToolkit()

@tool
def get_portfolio_overview(dummy_arg: str = "") -> str:
    """Get AGGREGATE metrics for the ENTIRE portfolio: Total TVPI, DPI, IRR, Paid-In, Distributed. Does NOT provide individual fund data."""
    return db_tool.run_sql_func("fn_get_pe_metrics_py", ('PORTFOLIO', None))

@tool
def get_strategy_metrics(strategy_name: str) -> str:
    """Get metrics for a PRIMARY STRATEGY (e.g., Venture Capital, Real Estate)."""
    return db_tool.run_sql_func("fn_get_pe_metrics_py", ('STRATEGY', strategy_name))

@tool
def get_sub_strategy_metrics(sub_strategy_name: str) -> str:
    """Get metrics for a SUB-STRATEGY (e.g., Growth Equity, Buyout)."""
    return db_tool.run_sql_func("fn_get_pe_metrics_py", ('SUB_STRATEGY', sub_strategy_name))

@tool
def get_fund_metrics(fund_name: str) -> str:
    """Get performance metrics for a specific FUND."""
    return db_tool.run_sql_func("fn_get_pe_metrics_py", ('FUND', fund_name))

@tool
def get_historical_j_curve(strategy_name: str) -> str:
    """Get J-Curve yearly cash flows for a strategy."""
    sql = """
        WITH yearly_data AS (
            SELECT 
                cf_year,
                cumulative_net_cash_flow,
                (cumulative_net_cash_flow - LAG(cumulative_net_cash_flow, 1, 0) OVER (ORDER BY cf_year)) as yearly_cash_flow
            FROM view_j_curve_cumulative
            WHERE primary_strategy = %s
        )
        SELECT json_agg(
            json_build_object(
                'year', cf_year,
                'cumulative_cash_flow', cumulative_net_cash_flow,
                'yearly_cash_flow', yearly_cash_flow
            )
        ) 
        FROM yearly_data
    """
    return db_tool.run_sql_query(sql, (strategy_name,))

@tool
def get_fund_ranking(metric: str = "Distributed") -> str:
    """
    Lists the top 5 funds based on a specific metric.
    Supported metrics: 'Distributed', 'Paid-In'.
    """
    # Map friendly names to DB columns
    # Paid-In is negative in DB, so we order by ASC to get the largest magnitude (most negative)
    if "Paid" in metric or "paid" in metric:
        sql = """
            SELECT json_agg(t) FROM (
                SELECT p.fund_name, SUM(cf.investment_paid_in_usd + cf.management_fees_usd) as total_paid_in
                FROM pe_historical_cash_flows cf
                JOIN pe_portfolio p ON cf.fund_id = p.fund_id
                GROUP BY p.fund_name
                ORDER BY total_paid_in ASC
                LIMIT 5
            ) t
        """
    else:
        # Default to Distributed (Positive values)
        sql = """
            SELECT json_agg(t) FROM (
                SELECT p.fund_name, SUM(cf.profit_distribution_usd + cf.return_of_cost_distribution_usd) as total_distributed
                FROM pe_historical_cash_flows cf
                JOIN pe_portfolio p ON cf.fund_id = p.fund_id
                GROUP BY p.fund_name
                ORDER BY total_distributed DESC
                LIMIT 5
            ) t
        """
    return db_tool.run_sql_query(sql)

@tool
def run_forecast_simulation(strategy_name: str, years: int = 5) -> str:
    """Run Takahashi-Alexander model forecast for future cash flows."""
    
    # Robust parsing for LLM inputs like "strategy_name='Venture Capital', years=5"
    if isinstance(strategy_name, str):
        # 1. Extract Strategy Name
        # Look for explicit assignment or just take the string if simple
        strat_match = re.search(r"strategy_name\s*=\s*['\"]([^'\"]+)['\"]", strategy_name)
        if strat_match:
            strategy_name_clean = strat_match.group(1)
        else:
            # Fallback: Remove potential tuple/quote artifacts
            strategy_name_clean = strategy_name.strip("()'\", ")
            # If it split into multiple args, take the first chunk
            if "," in strategy_name_clean:
                strategy_name_clean = strategy_name_clean.split(",")[0].strip("'\" ")
        
        # 2. Extract Years (if embedded in the first arg string)
        years_match = re.search(r"years\s*=\s*(\d+)", strategy_name)
        if years_match:
            years = int(years_match.group(1))
            
        strategy_name = strategy_name_clean
    
    # Ensure years is an integer
    years = int(years) if isinstance(years, str) else years
    
    return db_tool.run_sql_func("fn_run_takahashi_forecast", (strategy_name, years * 4))

@tool
def get_forecast_results(strategy_name: str) -> str:
    """Get forecast results after running simulation."""
    sql = """
        SELECT json_agg(
            json_build_object(
                'year', EXTRACT(YEAR FROM quarter_date),
                'forecast_type', forecast_type,
                'total_amount', SUM(amount_usd)
            )
        ) 
        FROM pe_forecast_output
        WHERE strategy = %s
        GROUP BY EXTRACT(YEAR FROM quarter_date), forecast_type
        ORDER BY EXTRACT(YEAR FROM quarter_date), forecast_type
    """
    return db_tool.run_sql_query(sql, (strategy_name,))

@tool
def check_modeling_assumptions(strategy_name: str) -> str:
    """Check J-Curve assumptions, Target IRR, and Model Rationale."""
    sql = """
        SELECT row_to_json(t) 
        FROM (
            SELECT 
                primary_strategy,
                target_return,
                j_curve_assumption,
                model_rationale
            FROM pe_modeling_rules 
            WHERE primary_strategy = %s
        ) t
    """
    return db_tool.run_sql_query(sql, (strategy_name,))

# ==============================================================================
# CUSTOM LLM WRAPPER
# ==============================================================================
class DeepSeekR1Ollama(OllamaLLM):
    def _call(self, prompt: str, stop: List[str] = None, **kwargs: Any) -> str:
        response = super()._call(prompt, stop, **kwargs)
        # Remove <think> tags to clean output and help ReAct parser
        cleaned_response = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL).strip()

        # If both Action and Final Answer are present, just keep the Action part.
        if "Action:" in cleaned_response and "Final Answer:" in cleaned_response:
            cleaned_response = cleaned_response.split("Final Answer:")[0].strip()

        # Heuristic: If the model gives a direct answer without an Action, wrap it
        if "Action:" not in cleaned_response and "Final Answer:" not in cleaned_response:
            return f"Final Answer: {cleaned_response}"
        return cleaned_response

# ==============================================================================
# AGENT SETUP
# ==============================================================================

def setup_agent():
    ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:21434")
    ollama_base_url = ollama_host if ollama_host.startswith("http") else f"http://{ollama_host}"

    tools = [
        get_portfolio_overview,
        get_strategy_metrics,
        get_sub_strategy_metrics,
        get_fund_metrics,
        get_fund_ranking,
        get_historical_j_curve,
        run_forecast_simulation,
        get_forecast_results,
        check_modeling_assumptions
    ]

    try:
        llm = DeepSeekR1Ollama(model=LLM_MODEL, temperature=0, base_url=ollama_base_url)
    except Exception as e:
        logger.error(f"Could not connect to Ollama at {ollama_base_url}: {e}")
        sys.exit(1)

    # Custom prompt to guide the LLM for more concise and relevant thoughts
    prompt_template = """Answer the following questions as concisely as possible. You have access to the following tools:

{tools}

Use the following format:

Question: the input question you must answer
Thought: You should always think about what to do. Focus on which SQL query or function will be run by the tool you select.
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: A concise, non-technical answer to the original question.

Begin!

Question: {input}
Thought:{agent_scratchpad}"""
    prompt = PromptTemplate.from_template(prompt_template)
    agent = create_react_agent(llm, tools, prompt) 
    
    return AgentExecutor(
        agent=agent, 
        tools=tools, 
        verbose=True, 
        handle_parsing_errors="Check your output and make sure it conforms to the format: Action: [tool] \n Action Input: [input]",
        max_iterations=15,
        max_execution_time=60
    )

# ==============================================================================
# MAIN
# ==============================================================================
if __name__ == "__main__":
    print("\n" + "="*60)
    print(f"🤖 Private Equity Agent | Model: {LLM_MODEL}")
    print("="*60 + "\n")

    agent_executor = setup_agent()

    questions = [
        "What is the TVPI and DPI of the entire portfolio?",
        "Which primary strategy has the highest Internal Rate of Return (IRR)?",
        "What is the total Paid-In capital for the 'Growth Equity' sub-strategy?",
        "Which specific fund has distributed the most capital to date?",
        "Show me the J-Curve for the 'Private Equity' strategy.",
        "What are the yearly net cash flows for the 'Venture Capital' strategy?",
        "What is the total remaining commitment (uncalled capital) for the 'Real Estate' strategy?",
        "Run a 5-year forecast for 'Venture Capital' and show me the results.",
        "Why is the J-Curve for Venture Capital so deep? Check the assumptions."
    ]

    for i, question in enumerate(questions, 1):
        print(f"\n🔹 Q{i}: {question}")
        print("-" * 70)
        try:
            response = agent_executor.invoke({"input": question})
            print(f"🟢 Answer: {response['output']}")
        except Exception as e:
            print(f"🔴 Error: {e}")
            logger.error(f"Error processing Q{i}: {e}")
        print("-" * 70)
            
    db_tool.close()