import pandas as pd
import numpy_financial as npf
import matplotlib.pyplot as plt
import re
import os
import sys
import logging
from sqlalchemy import create_engine, text

# --- COMPATIBILITY IMPORTS (Safe for OpenWebUI) ---
from langchain_community.llms import Ollama 
from langchain_community.utilities import SQLDatabase
import traceback # Added for detailed error logging

# FIX: Robust imports for Tool and Agents
# Try standard locations first, then fallbacks
try:
    from langchain.agents import Tool, AgentExecutor, create_react_agent
except ImportError:
    try:
        # Newer LangChain structure
        from langchain_core.tools import Tool
        from langchain.agents import AgentExecutor, create_react_agent
    except ImportError:
        # Fallback for older/mixed environments
        from langchain.tools import Tool
        from langchain.agents import AgentExecutor, create_react_agent

from langchain import hub

# --- JUPYTER SUPPORT ---
try:
    from IPython.display import display, Image
    IN_JUPYTER = True
except ImportError:
    IN_JUPYTER = False

# --- 0. LOGGING CONFIGURATION ---
LOG_LEVEL = os.environ.get("PE_AGENT_LOG_LEVEL", "INFO").upper()
logging.basicConfig(stream=sys.stdout, level=LOG_LEVEL, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- 1. CONFIGURATION ---
DB_USER = "postgres"
DB_PASS = "postgres" 
DB_HOST = "127.0.0.1"
DB_PORT = "5432"
DB_NAME = "private_markets_db"

# DEEPSEEK CONFIG
LLM_MODEL = "deepseek-r1:70b"
LLM_BASE_URL = "http://localhost:21434"

# Connect to Database
try:
    connection_str = f"postgresql+psycopg2://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    engine = create_engine(connection_str)
    db = SQLDatabase(engine)
    logger.info(f"✅ Database Connected (User: {DB_USER})")
except Exception as e:
    logger.error(f"❌ Database Error: {e}", exc_info=True) # Log full traceback
    sys.exit(1)

# --- 2. INITIALIZE LEGACY LLM ---
llm = Ollama(
    model=LLM_MODEL,
    base_url=LLM_BASE_URL,
    temperature=0.0,
    num_ctx=8192
)

# --- 3. ROBUST HELPER FUNCTIONS ---

def clean_llm_output(text: str) -> str:
    """
    Cleans DeepSeek-R1 output to prevent SQL Syntax Errors.
    Removes <think> tags and markdown code blocks.
    """
    if "</think>" in text:
        text = text.split("</think>")[-1]
    
    code_match = re.search(r"```sql\n(.*?)\n```", text, re.DOTALL)
    if code_match:
        return code_match.group(1).strip()
    
    code_match_generic = re.search(r"```\n(.*?)\n```", text, re.DOTALL)
    if code_match_generic:
        return code_match_generic.group(1).strip()
        
    text = text.replace("```sql", "").replace("```", "").strip()
    return text

# --- 4. TOOLS ---

def robust_sql_query(query_input: str):
def get_portfolio_metrics(strategy_filter: str = ""):
    """
    Generates and executes SQL safely with strict logic for duplicates.
    Calculates TVPI and DPI for a given strategy or the entire portfolio.
    Use for questions about TVPI or DPI.
    Input: A strategy name (e.g., 'Growth Equity') or empty for the whole portfolio.
    """
    prompt = f"""
    You are a PostgreSQL expert. Given the user question, write a valid SQL query.
    
    ### DATABASE SCHEMA (STRICTLY FOLLOW THESE TABLE NAMES):
    1. Table: pe_portfolio (alias: p)
       - Columns: fund_id (PK), fund_name, vintage_year, 
                  primary_strategy (e.g., 'Private Equity', 'Venture Capital'), 
                  sub_strategy (e.g., 'Leveraged Buyout (LBO)', 'Growth Equity'), 
                  total_commitment_usd
    2. Table: pe_historical_cash_flows (alias: cf)
       - Columns: transaction_id, fund_id (FK), transaction_date, transaction_type, 
                  investment_paid_in_usd (negative), management_fees_usd (negative),
                  return_of_cost_distribution_usd (positive), profit_distribution_usd (positive),
                  net_asset_value_usd (NAV)

    ### CALCULATION RULES:
    1. Paid In = investment_paid_in_usd + management_fees_usd (Negative)
    2. Distributions = profit_distribution_usd + return_of_cost_distribution_usd (Positive)
    3. TVPI = (SUM(Distributions) + SUM(Latest_NAV)) / ABS(SUM(Paid_In))
    4. **MANAGEMENT FEES:** To find "Total Management Fees", SUM(management_fees_usd). The result will be negative; display as ABS().
    5. **LATEST NAV LOGIC (CRITICAL):**
       - Duplicate rows exist for the same date. Do NOT use a simple MAX(date).
       - Use this CTE pattern to pick the single latest row per fund:
         WITH ordered_navs AS (
             SELECT fund_id, net_asset_value_usd,
             ROW_NUMBER() OVER (PARTITION BY fund_id ORDER BY transaction_date DESC, transaction_id DESC) as rn
             FROM pe_historical_cash_flows
         )
         SELECT SUM(net_asset_value_usd) FROM ordered_navs WHERE rn = 1
    6. **UN CALLED CAPITAL (REMAINING COMMITMENT):**
       - This is `total_commitment_usd` from the portfolio table minus the total capital called.
       - Formula: `p.total_commitment_usd - ABS(SUM(cf.investment_paid_in_usd))`
    7. **RANKING & SELECTION:**
       - For questions like "Which fund..." or "What is the top...", you must return the `fund_name`.
       - Use `ORDER BY` with `DESC` for "highest" or "most", and `ASC` for "lowest" or "least".
       - Always include `LIMIT 1` unless the user asks for more than one result.
       - Example: To find the fund with the most distributions, `SELECT p.fund_name FROM pe_portfolio p JOIN ... GROUP BY p.fund_name ORDER BY SUM(cf.profit_distribution_usd + cf.return_of_cost_distribution_usd) DESC LIMIT 1`.

    ### OUTPUT FORMAT (VERY STRICT):
    - **Return ONLY the raw SQL code and nothing else.**
    - NO explanations, NO markdown (like ```sql), NO conversational text, NO <think> tags.
    - Your entire response must be only the SQL query.
    
    Question: {query_input}
    """
    
    raw_response = llm.invoke(prompt)
    clean_sql = clean_llm_output(raw_response)
    
    logger.debug(f"SQL Query:\n{clean_sql}")
    
    try:
        return db.run(clean_sql)
        # Use '%' as a wildcard for the function if the filter is not empty
        filter_param = f"%{strategy_filter}%" if strategy_filter else None
        
        with engine.connect() as conn:
            # Use sqlalchemy.text to safely pass parameters to the database function
            result = conn.execute(text("SELECT tvpi, dpi FROM calculate_portfolio_metrics(:filter)"), {"filter": filter_param}).fetchone()
        
        if result and result.tvpi is not None:
            return f"Metrics for '{strategy_filter or 'Entire Portfolio'}': TVPI = {result.tvpi:.2f}x, DPI = {result.dpi:.2f}x"
        else:
            return f"Could not calculate metrics for '{strategy_filter or 'Entire Portfolio'}'. No data found."
    except Exception as e:
        logger.error(f"SQL Execution Failed: {e}", exc_info=True) # Log full traceback
        return f"SQL Execution Failed: {e}" # Still return the error message for the agent to process
        logger.error(f"Error calling calculate_portfolio_metrics: {e}", exc_info=True)
        return "Failed to retrieve portfolio metrics from the database."

def calculate_irr_jcurve(filter_context: str = ""):
    """
    Calculates IRR and J-Curve.
    Input: A string describing the strategy/fund filter (e.g. "Buyout", "Fund V")
    """
    # --- SANITIZE INPUT ---
    # Remove quotes and standard SQL syntax to prevent double-quoting errors
    search_term = filter_context.strip().strip('"').strip("'")
    if search_term.lower().startswith("where "):
        search_term = search_term[6:]
    if search_term.lower().startswith("p."):
        search_term = search_term[2:]
    
    # Remove any internal quotes that might break SQL strings (e.g., 'Venture' -> Venture)
    search_term = search_term.replace("'", "").replace('"', "")
    
    # --- SMART FILTER LOGIC ---
    # Use ILIKE with wildcards for broad matching.
    where_clause = f"WHERE p.primary_strategy ILIKE '%%{search_term}%%' OR p.sub_strategy ILIKE '%%{search_term}%%'"
    
    logger.debug(f"Filter: {where_clause}")

    sql = f"""
    SELECT 
        cf.transaction_date,
        (cf.investment_paid_in_usd + cf.management_fees_usd) as paid_in,
        (cf.return_of_cost_distribution_usd + cf.profit_distribution_usd) as distributions,
        cf.net_asset_value_usd,
        cf.fund_id
    FROM pe_historical_cash_flows cf
    JOIN pe_portfolio p ON cf.fund_id = p.fund_id
    {where_clause}
    ORDER BY cf.transaction_date
    """
    
    try:
        with engine.connect() as conn:
            df = pd.read_sql(text(sql), conn)
            
        if df.empty: return f"No data found matching '{search_term}'."

        # Net Cash Flow
        df['net_cf'] = df['paid_in'] + df['distributions']
        
        # Latest NAV Logic (Pandas Fallback for Accuracy)
        latest_nav = df.sort_values(['fund_id', 'transaction_date']).groupby('fund_id').tail(1)['net_asset_value_usd'].sum()
        
        # IRR Calculation
        timeline = df.groupby('transaction_date')['net_cf'].sum().sort_index()
        flows = timeline.tolist()
        if flows: flows[-1] += latest_nav
        
        try:
            irr = npf.irr(flows)
        except:
            irr = 0.0

        # J-Curve Plot
        cumulative_cf = timeline.cumsum()
        plt.figure(figsize=(10, 6))
        cumulative_cf.plot(title=f"J-Curve Analysis: {search_term}", color='navy', linewidth=2)
        plt.axhline(0, color='red', linestyle='--')
        plt.grid(True, alpha=0.3)
        plt.ylabel("Cumulative Net Cash Flow ($)")
        
        filename = "j_curve_result.png"
        plt.savefig(filename)
        plt.close()

        if IN_JUPYTER:
            try:
                display(Image(filename=filename))
                print(f"Graph displayed above. Saved to: {filename}")
            except Exception:
                pass
                logger.info(f"Graph displayed above. Saved to: {filename}")
            except Exception as e:
                logger.warning(f"Could not display image in Jupyter: {e}")

        return f"IRR: {irr:.2%} (Periodic). J-Curve saved to {filename}."
        
    except Exception as e:
        return f"Calculation Error: {e}"
        logger.error(f"IRR/J-Curve Calculation Error: {e}")
        return f"Calculation Error: {e}" # Still return the error message for the agent to process

def calculate_annual_cash_flows(filter_context: str = ""):
    """
    Aggregates Annual Net Cash Flows and Cumulative Cash Flows.
    Input: A keyword like "Private Equity" or "Buyout".
    """
    search_term = filter_context.strip().strip('"')
    search_term = search_term.replace("'", "").replace('"', "")
    
    where_clause = f"WHERE p.primary_strategy ILIKE '%%{search_term}%%' OR p.sub_strategy ILIKE '%%{search_term}%%'"
    
    sql = f"""
    SELECT 
        EXTRACT(YEAR FROM cf.transaction_date) as year,
        SUM(cf.investment_paid_in_usd + cf.management_fees_usd) as paid_in,
        SUM(cf.return_of_cost_distribution_usd + cf.profit_distribution_usd) as distributions
    FROM pe_historical_cash_flows cf
    JOIN pe_portfolio p ON cf.fund_id = p.fund_id
    {where_clause}
    GROUP BY 1
    ORDER BY 1
    """
    
    try:
        with engine.connect() as conn:
            df = pd.read_sql(text(sql), conn)
            
        if df.empty: return f"No data found matching '{search_term}'."
        
        df['net_cash_flow'] = df['paid_in'] + df['distributions']
        df['cumulative_net_cf'] = df['net_cash_flow'].cumsum()
        
        df['year'] = df['year'].astype(int)
        pd.options.display.float_format = '{:,.0f}'.format
        
        return f"Annual Cash Flows for {search_term}:\n" + df.to_string(index=False)
        
    except Exception as e:
        logger.error(f"Error calculating annual cash flows: {e}", exc_info=True) # Log full traceback
        return f"Error: {e}" # Still return the error message for the agent to process

# --- 5. AGENT SETUP ---

def setup_agent():
    tools = [
        Tool(
            name="SQL_Query_Tool",
            func=robust_sql_query, # Updated description
            description="Use for TVPI, MOIC, DPI, Distributions, Ranking, Uncalled Capital. Input: Full user question." 
            name="Portfolio_Metrics_Tool",
            func=get_portfolio_metrics,
            description="Use for any questions about TVPI or DPI for the whole portfolio or a specific strategy. Input: a strategy name like 'Growth Equity' or empty for the entire portfolio."
        ),
        Tool(
            name="IRR_JCurve_Tool",
            func=calculate_irr_jcurve,
            description="Use for IRR/J-Curve. Input: A simple keyword like 'Buyout', 'Venture', or 'Fund V'.",
        ),
        Tool(
            name="Annual_Cash_Flow_Tool",
            func=calculate_annual_cash_flows,
            description="Use for Yearly/Annual cash flows. Input: A simple keyword like 'LBO' or 'Private Equity'."
        )
    ]
    
    prompt = hub.pull("hwchase17/react")
    agent = create_react_agent(llm, tools, prompt)
    return AgentExecutor(agent=agent, tools=tools, verbose=True, handle_parsing_errors=True)

# --- 6. BATCH EXECUTION ---
if __name__ == "__main__": 
    agent = setup_agent()
    logger.info("\n" + "="*50)
    logger.info("🤖 Private Equity Agent Ready")
    logger.info("   - Connected to DeepSeek-R1 (Port 21434)")
    logger.info("   - Connected to Postgres (Port 5432)")
    logger.info("   - Executing Batch Test Plan...")
    logger.info("="*50 + "\n")
    
    test_questions = [
        "What is the TVPI and DPI of the entire portfolio?",
        "Which primary strategy has the highest Internal Rate of Return (IRR)?",
        "What is the total Paid-In capital for the 'Growth Equity' sub-strategy?",
        "Which specific fund has distributed the most capital to date?",
        "Show me the J-Curve for the 'Private Equity' strategy.",
        "What are the yearly net cash flows for the 'Venture Capital' strategy?",
        "What is the total remaining commitment (uncalled capital) for the 'Real Estate' strategy?",
        "What is the TVPI for 'Infrastructure' funds with a vintage year of 2018 or later?",
        "What is the total amount of management fees paid across the entire portfolio?",
        "Calculate the IRR for Buyout funds."
    ]
    
    for i, q in enumerate(test_questions, 1):
        logger.info(f"\n🔹 Question {i}: {q}")
        try:
            result = agent.invoke({"input": q})
            logger.info(f"Agent Answer: {result['output']}")
            
        except Exception as e:
            logger.error(f"❌ Query failed for question '{q}': {e}\n", exc_info=True) # Log full traceback
