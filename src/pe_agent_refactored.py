"""
Refactored PE Portfolio Agent.

This agent uses pure Python computation engines for all calculations
and only relies on the LLM for natural language understanding and response formatting.

Architecture:
- User Query → LLM Agent (routing) → Computation Engines (calculations) → Database (Metrics Storage)
"""

import os
import sys
import logging
import json
import re
import time
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

import psycopg2
from psycopg2.extras import RealDictCursor

from langchain_community.llms import Ollama
from langchain.agents import AgentExecutor, create_react_agent
from langchain_core.prompts import PromptTemplate
from langchain_core.tools import tool

# Import our computation engines
from config import (
    LLM_MODEL, OLLAMA_HOST, LLM_TEMPERATURE, LLM_MAX_ITERATIONS, LLM_MAX_EXECUTION_TIME, 
    LOG_LEVEL, DB_CONFIG, ENABLE_CACHING, CACHE_TTL_SECONDS, CACHE_SIMILARITY_THRESHOLD, 
    CACHE_DB_PATH, CACHE_EMBEDDING_MODEL, CACHE_MAX_ENTRIES
)

from engines.cash_flow_engine import (
    calculate_j_curve,
    AggregationPeriod,
    generate_cash_flow_summary,
    calculate_ytd_metrics,
    CashFlow
)
from engines.projection_engine import (
    project_cash_flows_takahashi,
    project_portfolio_cash_flows,
    calculate_optimal_allocation
)
from engines.visualization_engine import (
    prepare_j_curve_data,
    prepare_tvpi_evolution_data,
    generate_chart_summary
)
from engines.pe_metrics_engine import calculate_all_metrics, aggregate_metrics

# Configure logging
logging.basicConfig(
    stream=sys.stdout,
    level=LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ==============================================================================
# DATABASE CONNECTION (Singleton)
# ==============================================================================

class DatabaseConnection:
    """Manages database connection lifecycle."""
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize database connection.
        
        Args:
            config: Database configuration dict (defaults to DB_CONFIG from config.py)
        """
        self.config = config or DB_CONFIG
        self.conn = None
        self._connect()
        self._ensure_metrics_table()
    
    def _connect(self):
        """Establish database connection."""
        try:
            self.conn = psycopg2.connect(**self.config)
            logger.info("✅ Connected to PostgreSQL database")
        except Exception as e:
            logger.error(f"❌ Database connection failed: {e}")
            self.conn = None
            
    def _ensure_metrics_table(self):
        """Ensure the table for storing calculated metrics exists."""
        query = """
        CREATE TABLE IF NOT EXISTS pe_computed_metrics (
            metric_id SERIAL PRIMARY KEY,
            calculation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            hierarchy_level VARCHAR(20) NOT NULL, -- 'PORTFOLIO', 'STRATEGY', 'SUB_STRATEGY', 'FUND'
            entity_id VARCHAR(100), -- Fund ID (as string) or Strategy Name
            paid_in NUMERIC,
            distributions NUMERIC,
            total_value NUMERIC,
            current_nav NUMERIC,
            tvpi NUMERIC,
            dpi NUMERIC,
            rvpi NUMERIC,
            irr NUMERIC,
            metrics_json JSONB -- Catch-all for extra data
        );
        CREATE INDEX IF NOT EXISTS idx_metrics_lookup ON pe_computed_metrics(hierarchy_level, entity_id);
        CREATE INDEX IF NOT EXISTS idx_metrics_date ON pe_computed_metrics(calculation_date);
        """
        self.execute_query(query, fetch="none")
    
    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")
    
    def execute_query(
        self,
        query: str,
        params: Tuple = None,
        fetch: str = "all"
    ) -> Any:
        """
        Execute a SQL query.
        
        Args:
            query: SQL query string
            params: Query parameters
            fetch: 'all', 'one', or 'none'
            
        Returns:
            Query results based on fetch parameter
        """
        if not self.conn:
            logger.error("No database connection available")
            return None
        
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                # logger.debug(f"Executing query: {query[:100]}...")
                cur.execute(query, params or ())
                
                if fetch == "all":
                    return cur.fetchall()
                elif fetch == "one":
                    return cur.fetchone()
                else:  # none
                    self.conn.commit()
                    return None
        except Exception as e:
            logger.error(f"Query execution error: {e}")
            self.conn.rollback()
            return None

# Global database connection
_db_connection = None

def get_db():
    """Get or create database connection."""
    global _db_connection
    if _db_connection is None:
        _db_connection = DatabaseConnection()
    return _db_connection


# ==============================================================================
# DATA SAVING / CACHING FUNCTIONS
# ==============================================================================

def save_computed_metrics(db: DatabaseConnection, metrics: Dict[str, Any]):
    """Save calculated metrics to the database for future retrieval."""
    if not metrics:
        return

    query = """
        INSERT INTO pe_computed_metrics 
        (hierarchy_level, entity_id, paid_in, distributions, total_value, current_nav, tvpi, dpi, rvpi, irr, metrics_json)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    
    # Extract specific fields
    hierarchy = metrics.get('hierarchy_level', 'UNKNOWN')
    
    # Determine entity_id based on hierarchy
    if hierarchy == 'FUND':
        entity_id = str(metrics.get('fund_id', ''))
    elif hierarchy == 'STRATEGY':
        entity_id = metrics.get('primary_strategy', '')
    elif hierarchy == 'SUB_STRATEGY':
        entity_id = metrics.get('sub_strategy', '')
    else:
        entity_id = 'PORTFOLIO'
        
    params = (
        hierarchy,
        entity_id,
        metrics.get('paid_in'),
        metrics.get('distributions'),
        metrics.get('total_value'),
        metrics.get('current_nav'),
        metrics.get('tvpi'),
        metrics.get('dpi'),
        metrics.get('rvpi'),
        metrics.get('irr'),
        json.dumps(metrics, default=str) # store full payload as JSON
    )
    
    db.execute_query(query, params, fetch="none")
    logger.info(f"💾 Saved computed metrics for {hierarchy}: {entity_id}")


# ==============================================================================
# DATA RETRIEVAL HELPER FUNCTIONS
# ==============================================================================

def get_fund_list(
    db: DatabaseConnection,
    strategy: Optional[str] = None,
    sub_strategy: Optional[str] = None,
    is_active: bool = True
) -> List[Dict[str, Any]]:
    """Get list of funds with optional filtering."""
    query = """
        SELECT 
            fund_id,
            fund_name,
            vintage_year,
            primary_strategy,
            sub_strategy,
            total_commitment_usd as total_commitment,
            is_active
        FROM pe_portfolio
        WHERE 1=1
    """
    params = []
    
    if is_active is not None: 
        if is_active is True:
             query += " AND is_active = %s"
             params.append(True)
        
    if strategy:
        query += " AND primary_strategy = %s"
        params.append(strategy)
    
    if sub_strategy:
        query += " AND sub_strategy = %s"
        params.append(sub_strategy)
    
    query += " ORDER BY fund_name"
    
    results = db.execute_query(query, tuple(params))
    return [dict(row) for row in results] if results else []


def get_cash_flows(
    db: DatabaseConnection,
    fund_id: Optional[int] = None,
    strategy: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> List[CashFlow]:
    """Get cash flows from database."""
    query = """
        SELECT 
            cf.transaction_id,
            cf.fund_id,
            cf.transaction_date,
            cf.transaction_type,
            cf.investment_paid_in_usd,
            cf.management_fees_usd,
            cf.return_of_cost_distribution_usd,
            cf.profit_distribution_usd,
            cf.net_asset_value_usd
        FROM pe_historical_cash_flows cf
        LEFT JOIN pe_portfolio p ON cf.fund_id = p.fund_id
        WHERE 1=1
    """
    params = []
    
    if fund_id:
        query += " AND cf.fund_id = %s"
        params.append(fund_id)
    
    if strategy:
        query += " AND p.primary_strategy = %s"
        params.append(strategy)
    
    if start_date:
        query += " AND cf.transaction_date >= %s"
        params.append(start_date)
    
    if end_date:
        query += " AND cf.transaction_date <= %s"
        params.append(end_date)
    
    query += " ORDER BY cf.transaction_date"
    
    results = db.execute_query(query, tuple(params))
    
    if not results:
        return []
    
    cash_flows = []
    for row in results:
        # Investment
        if row['investment_paid_in_usd']:
            amount = row['investment_paid_in_usd']
            if amount > 0: amount = -amount
            cash_flows.append(CashFlow(
                transaction_id=row['transaction_id'],
                fund_id=row['fund_id'],
                date=row['transaction_date'],
                cf_type='call_investment',
                amount=amount
            ))
        
        # Fees
        if row['management_fees_usd']:
            amount = row['management_fees_usd']
            if amount > 0: amount = -amount
            cash_flows.append(CashFlow(
                transaction_id=row['transaction_id'],
                fund_id=row['fund_id'],
                date=row['transaction_date'],
                cf_type='call_fees',
                amount=amount
            ))
        
        # Return of capital
        if row['return_of_cost_distribution_usd']:
            cash_flows.append(CashFlow(
                transaction_id=row['transaction_id'],
                fund_id=row['fund_id'],
                date=row['transaction_date'],
                cf_type='distribution_return_of_capital',
                amount=row['return_of_cost_distribution_usd']
            ))
        
        # Profit
        if row['profit_distribution_usd']:
            cash_flows.append(CashFlow(
                transaction_id=row['transaction_id'],
                fund_id=row['fund_id'],
                date=row['transaction_date'],
                cf_type='distribution_profit',
                amount=row['profit_distribution_usd']
            ))
    
    return cash_flows


def get_latest_nav(db: DatabaseConnection, fund_id: int) -> Optional[float]:
    """Get the latest NAV for a fund."""
    query = """
        SELECT net_asset_value_usd
        FROM pe_historical_cash_flows
        WHERE fund_id = %s
        AND net_asset_value_usd IS NOT NULL
        ORDER BY transaction_date DESC
        LIMIT 1
    """
    result = db.execute_query(query, (fund_id,), fetch="one")
    return float(result['net_asset_value_usd']) if result else None


def get_modeling_assumptions(db: DatabaseConnection, strategy: str) -> Optional[Dict[str, Any]]:
    """Get modeling assumptions for a strategy."""
    query = """
        SELECT 
            primary_strategy,
            expected_moic_gross_multiple as expected_moic,
            target_irr_net_percentage as target_irr,
            investment_period_years,
            fund_life_years,
            nav_initial_qtr_depreciation,
            nav_initial_depreciation_qtrs,
            j_curve_model_description,
            modeling_rationale
        FROM pe_modeling_rules
        WHERE primary_strategy = %s
    """
    result = db.execute_query(query, (strategy,), fetch="one")
    return dict(result) if result else None


# ==============================================================================
# METRIC CALCULATION HELPERS
# ==============================================================================

def calculate_fund_metrics(db: DatabaseConnection, fund_id: int) -> Optional[Dict[str, Any]]:
    """Calculate all metrics for a specific fund and save to DB."""
    # Get fund info
    fund_query = "SELECT fund_name, vintage_year, primary_strategy, total_commitment_usd FROM pe_portfolio WHERE fund_id = %s"
    fund_info = db.execute_query(fund_query, (fund_id,), fetch="one")
    if not fund_info:
        logger.warning(f"Fund {fund_id} not found")
        return None
    
    cash_flows = get_cash_flows(db, fund_id=fund_id)
    current_nav = get_latest_nav(db, fund_id) or 0
    
    cf_amounts = [cf.amount for cf in cash_flows]
    cf_dates = [cf.date for cf in cash_flows]
    
    metrics = calculate_all_metrics(
        cash_flows=cf_amounts,
        dates=cf_dates,
        total_commitment=float(fund_info['total_commitment_usd']),
        current_nav=current_nav
    )
    
    metrics.update({
        "hierarchy_level": "FUND",
        "fund_id": fund_id,
        "fund_name": fund_info['fund_name'],
        "vintage_year": fund_info['vintage_year'],
        "primary_strategy": fund_info['primary_strategy']
    })
    
    # Save computed metrics to DB
    save_computed_metrics(db, metrics)
    
    return metrics


def calculate_strategy_metrics(
    db: DatabaseConnection,
    strategy: str,
    sub_strategy: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Calculate aggregated metrics for a strategy and save to DB."""
    funds = get_fund_list(db, strategy=strategy, sub_strategy=sub_strategy)
    
    if not funds:
        logger.warning(f"No funds found for strategy: {strategy}")
        return None
    
    fund_metrics = []
    for fund in funds:
        metrics = calculate_fund_metrics(db, fund['fund_id'])
        if metrics:
            fund_metrics.append(metrics)
    
    aggregated = aggregate_metrics(fund_metrics)
    aggregated.update({
        "hierarchy_level": "SUB_STRATEGY" if sub_strategy else "STRATEGY",
        "primary_strategy": strategy,
        "sub_strategy": sub_strategy
    })
    
    # Save computed metrics to DB
    save_computed_metrics(db, aggregated)
    
    return aggregated


def calculate_portfolio_metrics(db: DatabaseConnection) -> Optional[Dict[str, Any]]:
    """Calculate metrics for entire portfolio and save to DB."""
    funds = get_fund_list(db, is_active=True)
    
    if not funds:
        logger.warning("No active funds found in portfolio")
        return None
    
    fund_metrics = []
    for fund in funds:
        metrics = calculate_fund_metrics(db, fund['fund_id'])
        if metrics:
            fund_metrics.append(metrics)
    
    aggregated = aggregate_metrics(fund_metrics)
    aggregated.update({
        "hierarchy_level": "PORTFOLIO"
    })
    
    # Save computed metrics to DB
    save_computed_metrics(db, aggregated)
    
    return aggregated


# ==============================================================================
# LANGCHAIN TOOLS (Using Computation Engines)
# ==============================================================================

@tool
def get_portfolio_overview() -> str:
    """Get AGGREGATE metrics for the ENTIRE portfolio: Total TVPI, DPI, IRR, Paid-In, Distributed."""
    try:
        db = get_db()
        metrics = calculate_portfolio_metrics(db)
        if not metrics:
            return json.dumps({"error": "No portfolio data available"})
        
        response = {
            "hierarchy_level": "PORTFOLIO",
            "total_commitment": metrics.get('total_commitment', 0),
            "paid_in": metrics.get('paid_in', 0),
            "distributions": metrics.get('distributions', 0),
            "current_nav": metrics.get('current_nav', 0),
            "total_value": metrics.get('total_value', 0),
            "tvpi": metrics.get('tvpi'),
            "dpi": metrics.get('dpi'),
            "rvpi": metrics.get('rvpi'),
            "fund_count": metrics.get('fund_count', 0)
        }
        logger.info(f"Portfolio metrics calculated: TVPI={response['tvpi']:.2f}x")
        return json.dumps(response)
    except Exception as e:
        logger.error(f"Error: {e}")
        return json.dumps({"error": str(e)})

@tool
def get_strategy_metrics(strategy_name: str) -> str:
    """Get metrics for a PRIMARY STRATEGY (e.g., Venture Capital, Real Estate)."""
    try:
        db = get_db()
        metrics = calculate_strategy_metrics(db, strategy=strategy_name)
        if not metrics:
            return json.dumps({"error": f"No data found for strategy: {strategy_name}"})
        
        response = {
            "hierarchy_level": "STRATEGY",
            "primary_strategy": strategy_name,
            "total_commitment": metrics.get('total_commitment', 0),
            "paid_in": metrics.get('paid_in', 0),
            "distributions": metrics.get('distributions', 0),
            "current_nav": metrics.get('current_nav', 0),
            "total_value": metrics.get('total_value', 0),
            "tvpi": metrics.get('tvpi'),
            "dpi": metrics.get('dpi'),
            "fund_count": metrics.get('fund_count', 0)
        }
        logger.info(f"Strategy metrics for {strategy_name}: TVPI={response['tvpi']:.2f}x")
        return json.dumps(response)
    except Exception as e:
        logger.error(f"Error: {e}")
        return json.dumps({"error": str(e)})

@tool
def get_sub_strategy_metrics(sub_strategy_name: str) -> str:
    """Get metrics for a SUB-STRATEGY."""
    try:
        db = get_db()
        funds = get_fund_list(db, sub_strategy=sub_strategy_name)
        if not funds:
            return json.dumps({"error": f"No funds found for sub-strategy: {sub_strategy_name}"})
        
        primary_strategy = funds[0]['primary_strategy']
        metrics = calculate_strategy_metrics(db, strategy=primary_strategy, sub_strategy=sub_strategy_name)
        
        if not metrics:
            return json.dumps({"error": f"Could not calculate metrics for: {sub_strategy_name}"})
        
        response = {
            "hierarchy_level": "SUB_STRATEGY",
            "primary_strategy": primary_strategy,
            "sub_strategy": sub_strategy_name,
            "tvpi": metrics.get('tvpi'),
            "dpi": metrics.get('dpi'),
            "fund_count": metrics.get('fund_count', 0)
        }
        return json.dumps(response)
    except Exception as e:
        logger.error(f"Error: {e}")
        return json.dumps({"error": str(e)})

@tool
def get_fund_metrics(fund_name: str) -> str:
    """Get performance metrics for a specific FUND by name."""
    try:
        db = get_db()
        funds = get_fund_list(db, is_active=None)
        matching_fund = None
        for fund in funds:
            if fund_name.lower() in fund['fund_name'].lower():
                matching_fund = fund
                break
        
        if not matching_fund:
            return json.dumps({"error": f"Fund not found: {fund_name}"})
        
        metrics = calculate_fund_metrics(db, matching_fund['fund_id'])
        if not metrics:
            return json.dumps({"error": f"Could not calculate metrics for fund: {fund_name}"})
        
        response = {
            "hierarchy_level": "FUND",
            "fund_name": metrics.get('fund_name'),
            "vintage_year": metrics.get('vintage_year'),
            "primary_strategy": metrics.get('primary_strategy'),
            "tvpi": metrics.get('tvpi'),
            "dpi": metrics.get('dpi'),
            "irr": metrics.get('irr')
        }
        irr_str = f"{response['irr']:.2%}" if response['irr'] is not None else "N/A"
        logger.info(f"Fund metrics for {fund_name}: TVPI={response['tvpi']:.2f}x, IRR={irr_str}")
        return json.dumps(response)
    except Exception as e:
        logger.error(f"Error: {e}")
        return json.dumps({"error": str(e)})

@tool
def get_historical_j_curve(strategy_name: str) -> str:
    """Get J-Curve data for a strategy."""
    try:
        db = get_db()
        cash_flows = get_cash_flows(db, strategy=strategy_name)
        if not cash_flows:
            return json.dumps({"error": f"No cash flow data for strategy: {strategy_name}"})
        
        j_curve_data = calculate_j_curve(cash_flows, AggregationPeriod.YEARLY)
        periods = [item['period'] for item in j_curve_data]
        cumulative_flows = [item['cumulative_flow'] for item in j_curve_data]
        discrete_flows = [item['net_flow'] for item in j_curve_data]
        
        chart_data = prepare_j_curve_data(periods, cumulative_flows, discrete_flows)
        summary = generate_chart_summary(chart_data)
        
        response = {
            "strategy": strategy_name,
            "j_curve": j_curve_data,
            "chart_summary": summary
        }
        return json.dumps(response)
    except Exception as e:
        logger.error(f"Error: {e}")
        return json.dumps({"error": str(e)})

@tool
def get_fund_ranking(metric: str = "distributions") -> str:
    """Lists the top 5 funds based on a specific metric."""
    try:
        db = get_db()
        funds = get_fund_list(db, is_active=True)
        if not funds:
            return json.dumps({"error": "No active funds found"})
        
        fund_metrics = []
        for fund in funds:
            metrics = calculate_fund_metrics(db, fund['fund_id'])
            if metrics:
                fund_metrics.append(metrics)
        
        metric_lower = metric.lower()
        if metric_lower in ['distributed', 'distributions']:
            key_func = lambda x: x.get('distributions', 0)
        elif metric_lower in ['paid', 'paid_in', 'calls']:
            key_func = lambda x: x.get('paid_in', 0)
        elif metric_lower == 'tvpi':
            key_func = lambda x: x.get('tvpi', 0) or 0
        elif metric_lower == 'nav':
            key_func = lambda x: x.get('current_nav', 0)
        else:
            key_func = lambda x: x.get('distributions', 0)
            
        sorted_funds = sorted(fund_metrics, key=key_func, reverse=True)
        top_5 = sorted_funds[:5]
        
        results = []
        for i, fund in enumerate(top_5, 1):
            results.append({
                "rank": i,
                "fund_name": fund.get('fund_name'),
                "strategy": fund.get('primary_strategy'),
                "metric_value": fund.get(metric_lower.replace(' ', '_'), 0),
                "tvpi": fund.get('tvpi'),
                "dpi": fund.get('dpi')
            })
        return json.dumps({"metric": metric, "top_funds": results})
    except Exception as e:
        logger.error(f"Error: {e}")
        return json.dumps({"error": str(e)})

@tool
def run_forecast_simulation(strategy_name: str, years: int = 5) -> str:
    """Run Takahashi-Alexander model forecast for future cash flows."""
    try:
        if isinstance(strategy_name, str) and ',' in strategy_name:
            parts = strategy_name.split(',')
            strategy_name = parts[0].strip().strip("'"")
            if len(parts) > 1:
                years_str = parts[1].strip()
                years = int(years_str.split('=')[1].strip()) if '=' in years_str else int(years_str)
        
        years = int(years)
        num_periods = years * 4
        db = get_db()
        
        assumptions = get_modeling_assumptions(db, strategy_name)
        if not assumptions:
            return json.dumps({"error": f"No modeling assumptions found for strategy: {strategy_name}"})
        
        funds = get_fund_list(db, strategy=strategy_name, is_active=True)
        if not funds:
            return json.dumps({"error": f"No active funds found for strategy: {strategy_name}"})
        
        funds_data = []
        for fund in funds:
            metrics = calculate_fund_metrics(db, fund['fund_id'])
            if metrics:
                funds_data.append({
                    "fund_id": fund['fund_id'],
                    "fund_name": fund['fund_name'],
                    "primary_strategy": fund['primary_strategy'],
                    "vintage_year": fund['vintage_year'],
                    "unfunded_commitment": metrics.get('unfunded_commitment', 0),
                    "current_nav": metrics.get('current_nav', 0)
                })
        
        modeling_assumptions = {strategy_name: assumptions}
        projections = project_portfolio_cash_flows(funds_data, modeling_assumptions, num_periods)
        
        summary = {
            "strategy": strategy_name,
            "projection_years": years,
            "total_projected_calls": sum(projections['total_calls']),
            "total_projected_distributions": sum(projections['total_distributions']),
            "projected_nav_end": projections['total_nav'][-1] if projections['total_nav'] else 0
        }
        return json.dumps(summary)
    except Exception as e:
        logger.error(f"Error running forecast: {e}")
        return json.dumps({"error": str(e)})

@tool
def check_modeling_assumptions(strategy_name: str) -> str:
    """Check J-Curve assumptions, Target IRR, MOIC expectations."""
    try:
        db = get_db()
        assumptions = get_modeling_assumptions(db, strategy_name)
        if not assumptions:
            return json.dumps({"error": f"No modeling assumptions found for: {strategy_name}"})
        
        response = {
            "primary_strategy": assumptions.get('primary_strategy'),
            "expected_moic": assumptions.get('expected_moic'),
            "target_irr": assumptions.get('target_irr'),
            "investment_period_years": assumptions.get('investment_period_years'),
            "fund_life_years": assumptions.get('fund_life_years'),
            "modeling_rationale": assumptions.get('modeling_rationale')
        }
        return json.dumps(response)
    except Exception as e:
        logger.error(f"Error retrieving assumptions: {e}")
        return json.dumps({"error": str(e)})


# ==============================================================================
# CUSTOM LLM WRAPPER
# ==============================================================================

class DeepSeekR1Ollama(Ollama):
    """Custom wrapper to clean DeepSeek R1 output and enforce ReAct format."""
    
    def _call(self, prompt: str, stop: List[str] = None, **kwargs: Any) -> str:
        response = super()._call(prompt, stop, **kwargs)
        cleaned_response = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL).strip()
        
        if "Action:" not in cleaned_response and "Final Answer:" not in cleaned_response:
            if "portfolio" in cleaned_response.lower() and ("tvpi" in cleaned_response.lower() or "dpi" in cleaned_response.lower()):
                return "Thought: I need to get portfolio-level metrics.\nAction: get_portfolio_overview\nAction Input: "
            else:
                return f"Thought: I have the information needed.\nFinal Answer: {cleaned_response}"
        
        if "Action:" in cleaned_response and "Final Answer:" in cleaned_response:
            action_part = cleaned_response.split("Final Answer:")[0].strip()
            return action_part
        
        return cleaned_response


# ==============================================================================
# AGENT SETUP
# ==============================================================================

def setup_agent():
    """Set up the PE agent with computation-based tools."""
    
    ollama_base_url = OLLAMA_HOST if OLLAMA_HOST.startswith("http") else f"http://{OLLAMA_HOST}"
    
    tools = [
        get_portfolio_overview,
        get_strategy_metrics,
        get_sub_strategy_metrics,
        get_fund_metrics,
        get_fund_ranking,
        get_historical_j_curve,
        run_forecast_simulation,
        check_modeling_assumptions
    ]
    
    try:
        llm = DeepSeekR1Ollama(
            model=LLM_MODEL,
            temperature=LLM_TEMPERATURE,
            base_url=ollama_base_url
        )
    except Exception as e:
        logger.error(f"Could not connect to Ollama at {ollama_base_url}: {e}")
        sys.exit(1)
    
    prompt_template = """Answer the following questions as concisely as possible. You have access to the following tools:

{tools}

Use the following format:

Question: the input question you must answer
Thought: You should always think about what to do
Action: one of [{tool_names}] (no parentheses)
Action Input: JSON for the tool args, e.g. {{'strategy_name': 'Private Equity'}}
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: A concise, non-technical answer to the original question.

Begin!

Question: {input}
Thought:{agent_scratchpad}"""
    
    prompt = PromptTemplate.from_template(prompt_template)
    agent = create_react_agent(llm, tools, prompt)
    
    executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        handle_parsing_errors="Check your output and make sure it conforms to the format: Action: [tool] \n Action Input: [input]",
        max_iterations=LLM_MAX_ITERATIONS,
        max_execution_time=LLM_MAX_EXECUTION_TIME
    )
    
    return executor


# ==============================================================================
# MAIN
# ==============================================================================

if __name__ == "__main__":
    user_question = sys.argv[1] if len(sys.argv) > 1 else None

    print("\n" + "="*60)
    print(f"🤖 PE Portfolio Agent (Computation-First) | Model: {LLM_MODEL}")
    print("="*60 + "\n")
    
    agent_executor = setup_agent()
    
    default_questions = [
        "What is the TVPI and DPI of the entire portfolio?",
        "Which primary strategy has the highest Internal Rate of Return (IRR)?",
        "What is the total Paid-In capital for the 'Private Equity' strategy?",
        "Which specific fund has distributed the most capital to date?",
        "Show me the J-Curve for the 'Venture Capital' strategy.",
        "Run a 5-year forecast for 'Venture Capital' and show me the results.",
        "Why is the J-Curve for Venture Capital so deep? Check the assumptions."
    ]

    questions = [user_question] if user_question else default_questions
    
    for i, question in enumerate(questions, 1):
        print(f"\n└ Q{i}: {question}")
        print("-" * 70)
        try:
            response = agent_executor.invoke({"input": question})
            print(f"│ Answer: {response['output']}")
        except Exception as e:
            print(f" └ Error: {e}")
            logger.error(f"Error processing Q{i}: {e}")
        print("-" * 70)
    
    # Close database connection
    db = get_db()
    db.close()
