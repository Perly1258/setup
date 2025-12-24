"""
Refactored PE Portfolio Agent.

This agent uses pure Python computation engines for all calculations
and only relies on the LLM for natural language understanding and response formatting.

Architecture:
- User Query → LLM Agent (routing) → Computation Engines (calculations) → Database (caching)
"""

import os
import sys
import logging
import json
from typing import List, Dict, Any
import re

from langchain_ollama import OllamaLLM
from langchain.agents import AgentExecutor, create_react_agent
from langchain.prompts import PromptTemplate
from langchain.tools import tool

# Import our computation engines and data layer
from config import LLM_MODEL, OLLAMA_HOST, LLM_TEMPERATURE, LLM_MAX_ITERATIONS, LLM_MAX_EXECUTION_TIME, LOG_LEVEL
from data.db_adapter import (
    DatabaseConnection,
    get_fund_list,
    get_cash_flows,
    calculate_fund_metrics,
    calculate_strategy_metrics,
    calculate_portfolio_metrics,
    get_modeling_assumptions
)
from engines.cash_flow_engine import (
    calculate_j_curve,
    AggregationPeriod,
    generate_cash_flow_summary,
    calculate_ytd_metrics
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

# Global database connection
_db_connection = None

def get_db():
    """Get or create database connection."""
    global _db_connection
    if _db_connection is None:
        _db_connection = DatabaseConnection()
    return _db_connection


# ==============================================================================
# LANGCHAIN TOOLS (Using Computation Engines)
# ==============================================================================

@tool
def get_portfolio_overview(dummy_arg: str = "") -> str:
    """
    Get AGGREGATE metrics for the ENTIRE portfolio: Total TVPI, DPI, IRR, Paid-In, Distributed.
    Does NOT provide individual fund data.
    """
    try:
        db = get_db()
        metrics = calculate_portfolio_metrics(db)
        
        if not metrics:
            return json.dumps({"error": "No portfolio data available"})
        
        # Format for LLM consumption
        response = {
            "hierarchy_level": "PORTFOLIO",
            "total_commitment": metrics.get('total_commitment', 0),
            "paid_in": metrics.get('paid_in', 0),
            "distributions": metrics.get('distributions', 0),
            "current_nav": metrics.get('current_nav', 0),
            "total_value": metrics.get('total_value', 0),
            "unfunded_commitment": metrics.get('unfunded_commitment', 0),
            "tvpi": metrics.get('tvpi'),
            "dpi": metrics.get('dpi'),
            "rvpi": metrics.get('rvpi'),
            "called_percent": metrics.get('called_percent'),
            "distributed_percent": metrics.get('distributed_percent'),
            "fund_count": metrics.get('fund_count', 0)
        }
        
        logger.info(f"Portfolio metrics calculated: TVPI={response['tvpi']:.2f}x")
        return json.dumps(response)
        
    except Exception as e:
        logger.error(f"Error calculating portfolio metrics: {e}")
        return json.dumps({"error": str(e)})


@tool
def get_strategy_metrics(strategy_name: str) -> str:
    """
    Get metrics for a PRIMARY STRATEGY (e.g., Venture Capital, Real Estate, Private Equity, Infrastructure).
    Includes aggregated TVPI, DPI, IRR, and all PE metrics for the strategy.
    """
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
            "rvpi": metrics.get('rvpi'),
            "called_percent": metrics.get('called_percent'),
            "fund_count": metrics.get('fund_count', 0)
        }
        
        logger.info(f"Strategy metrics for {strategy_name}: TVPI={response['tvpi']:.2f}x")
        return json.dumps(response)
        
    except Exception as e:
        logger.error(f"Error calculating strategy metrics: {e}")
        return json.dumps({"error": str(e)})


@tool
def get_sub_strategy_metrics(sub_strategy_name: str) -> str:
    """
    Get metrics for a SUB-STRATEGY (e.g., Growth Equity, Buyout).
    You need to specify which primary strategy this sub-strategy belongs to.
    """
    try:
        db = get_db()
        
        # For sub-strategies, we need to determine the primary strategy
        # This is a simplified version - in production, we'd extract this from the query
        # For now, we'll search all strategies
        
        funds = get_fund_list(db, sub_strategy=sub_strategy_name)
        if not funds:
            return json.dumps({"error": f"No funds found for sub-strategy: {sub_strategy_name}"})
        
        # Get the primary strategy from the first fund
        primary_strategy = funds[0]['primary_strategy']
        
        metrics = calculate_strategy_metrics(db, strategy=primary_strategy, sub_strategy=sub_strategy_name)
        
        if not metrics:
            return json.dumps({"error": f"Could not calculate metrics for sub-strategy: {sub_strategy_name}"})
        
        response = {
            "hierarchy_level": "SUB_STRATEGY",
            "primary_strategy": primary_strategy,
            "sub_strategy": sub_strategy_name,
            "total_commitment": metrics.get('total_commitment', 0),
            "paid_in": metrics.get('paid_in', 0),
            "distributions": metrics.get('distributions', 0),
            "current_nav": metrics.get('current_nav', 0),
            "tvpi": metrics.get('tvpi'),
            "dpi": metrics.get('dpi'),
            "fund_count": metrics.get('fund_count', 0)
        }
        
        return json.dumps(response)
        
    except Exception as e:
        logger.error(f"Error calculating sub-strategy metrics: {e}")
        return json.dumps({"error": str(e)})


@tool
def get_fund_metrics(fund_name: str) -> str:
    """
    Get performance metrics for a specific FUND by name.
    Returns TVPI, DPI, IRR, NAV, and all detailed metrics.
    """
    try:
        db = get_db()
        
        # Find fund by name
        funds = get_fund_list(db, is_active=None)  # Include all funds
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
            "fund_id": metrics.get('fund_id'),
            "fund_name": metrics.get('fund_name'),
            "vintage_year": metrics.get('vintage_year'),
            "primary_strategy": metrics.get('primary_strategy'),
            "total_commitment": metrics.get('total_commitment', 0),
            "paid_in": metrics.get('paid_in', 0),
            "distributions": metrics.get('distributions', 0),
            "current_nav": metrics.get('current_nav', 0),
            "total_value": metrics.get('total_value', 0),
            "unfunded_commitment": metrics.get('unfunded_commitment', 0),
            "tvpi": metrics.get('tvpi'),
            "dpi": metrics.get('dpi'),
            "rvpi": metrics.get('rvpi'),
            "irr": metrics.get('irr'),
            "called_percent": metrics.get('called_percent')
        }
        
        irr_value = response.get('irr')
        irr_str = f"{irr_value:.2%}" if irr_value is not None else "N/A"
        logger.info(f"Fund metrics for {fund_name}: TVPI={response['tvpi']:.2f}x, IRR={irr_str}")
        return json.dumps(response)
        
    except Exception as e:
        logger.error(f"Error calculating fund metrics: {e}")
        return json.dumps({"error": str(e)})


@tool
def get_historical_j_curve(strategy_name: str) -> str:
    """
    Get J-Curve data (yearly cumulative cash flows) for a strategy.
    Shows the investment curve over time - typically negative initially, then positive.
    """
    try:
        db = get_db()
        
        # Get cash flows for the strategy
        cash_flows = get_cash_flows(db, strategy=strategy_name)
        
        if not cash_flows:
            return json.dumps({"error": f"No cash flow data for strategy: {strategy_name}"})
        
        # Calculate J-Curve
        j_curve_data = calculate_j_curve(cash_flows, AggregationPeriod.YEARLY)
        
        # Prepare visualization data
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
        
        logger.info(f"Generated J-Curve for {strategy_name} with {len(j_curve_data)} periods")
        return json.dumps(response)
        
    except Exception as e:
        logger.error(f"Error calculating J-Curve: {e}")
        return json.dumps({"error": str(e)})


@tool
def get_fund_ranking(metric: str = "distributions") -> str:
    """
    Lists the top 5 funds based on a specific metric.
    Supported metrics: 'distributions', 'paid_in', 'tvpi', 'nav'.
    """
    try:
        db = get_db()
        
        # Get all active funds
        funds = get_fund_list(db, is_active=True)
        
        if not funds:
            return json.dumps({"error": "No active funds found"})
        
        # Calculate metrics for each fund
        fund_metrics = []
        for fund in funds:
            metrics = calculate_fund_metrics(db, fund['fund_id'])
            if metrics:
                fund_metrics.append(metrics)
        
        # Sort by requested metric
        metric_lower = metric.lower()
        if metric_lower in ['distributed', 'distributions']:
            sorted_funds = sorted(fund_metrics, key=lambda x: x.get('distributions', 0), reverse=True)
        elif metric_lower in ['paid', 'paid_in', 'calls']:
            sorted_funds = sorted(fund_metrics, key=lambda x: x.get('paid_in', 0), reverse=True)
        elif metric_lower == 'tvpi':
            sorted_funds = sorted(fund_metrics, key=lambda x: x.get('tvpi', 0) or 0, reverse=True)
        elif metric_lower == 'nav':
            sorted_funds = sorted(fund_metrics, key=lambda x: x.get('current_nav', 0), reverse=True)
        else:
            sorted_funds = sorted(fund_metrics, key=lambda x: x.get('distributions', 0), reverse=True)
        
        # Get top 5
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
        
        logger.info(f"Generated top 5 funds by {metric}")
        return json.dumps({"metric": metric, "top_funds": results})
        
    except Exception as e:
        logger.error(f"Error ranking funds: {e}")
        return json.dumps({"error": str(e)})


@tool
def run_forecast_simulation(strategy_name: str, years: int = 5) -> str:
    """
    Run Takahashi-Alexander model forecast for future cash flows.
    Projects capital calls, distributions, and NAV evolution for the next N years.
    """
    try:
        # Parse parameters if they come as a single string
        if isinstance(strategy_name, str) and ',' in strategy_name:
            parts = strategy_name.split(',')
            strategy_name = parts[0].strip().strip("'\"")
            if len(parts) > 1:
                years_str = parts[1].strip()
                if '=' in years_str:
                    years = int(years_str.split('=')[1].strip())
                else:
                    years = int(years_str)
        
        years = int(years)
        num_periods = years * 4  # Quarterly projections
        
        db = get_db()
        
        # Get modeling assumptions for the strategy
        assumptions = get_modeling_assumptions(db, strategy_name)
        if not assumptions:
            return json.dumps({"error": f"No modeling assumptions found for strategy: {strategy_name}"})
        
        # Get funds in the strategy
        funds = get_fund_list(db, strategy=strategy_name, is_active=True)
        if not funds:
            return json.dumps({"error": f"No active funds found for strategy: {strategy_name}"})
        
        # Prepare fund data for projection
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
        
        # Run portfolio projection
        modeling_assumptions = {strategy_name: assumptions}
        projections = project_portfolio_cash_flows(funds_data, modeling_assumptions, num_periods)
        
        # Summarize results
        summary = {
            "strategy": strategy_name,
            "projection_years": years,
            "total_projected_calls": sum(projections['total_calls']),
            "total_projected_distributions": sum(projections['total_distributions']),
            "projected_nav_end": projections['total_nav'][-1] if projections['total_nav'] else 0,
            "quarterly_data": {
                "calls": projections['total_calls'][:8],  # First 2 years
                "distributions": projections['total_distributions'][:8],
                "nav": projections['total_nav'][:8]
            }
        }
        
        logger.info(f"Generated {years}-year forecast for {strategy_name}")
        return json.dumps(summary)
        
    except Exception as e:
        logger.error(f"Error running forecast: {e}")
        return json.dumps({"error": str(e)})


@tool
def check_modeling_assumptions(strategy_name: str) -> str:
    """
    Check J-Curve assumptions, Target IRR, MOIC expectations, and Model Rationale for a strategy.
    """
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
            "j_curve_depreciation_rate": assumptions.get('nav_initial_qtr_depreciation'),
            "j_curve_depreciation_quarters": assumptions.get('nav_initial_depreciation_qtrs'),
            "j_curve_model": assumptions.get('j_curve_model_description'),
            "modeling_rationale": assumptions.get('modeling_rationale')
        }
        
        logger.info(f"Retrieved modeling assumptions for {strategy_name}")
        return json.dumps(response)
        
    except Exception as e:
        logger.error(f"Error retrieving assumptions: {e}")
        return json.dumps({"error": str(e)})


# ==============================================================================
# CUSTOM LLM WRAPPER (Clean DeepSeek output)
# ==============================================================================

class DeepSeekR1Ollama(OllamaLLM):
    """Custom wrapper to clean DeepSeek R1 output."""
    
    def _call(self, prompt: str, stop: List[str] = None, **kwargs: Any) -> str:
        response = super()._call(prompt, stop, **kwargs)
        
        # Remove <think> tags
        cleaned_response = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL).strip()
        
        # If both Action and Final Answer present, keep only Action
        if "Action:" in cleaned_response and "Final Answer:" in cleaned_response:
            cleaned_response = cleaned_response.split("Final Answer:")[0].strip()
        
        # Wrap direct answers without Action/Final Answer
        if "Action:" not in cleaned_response and "Final Answer:" not in cleaned_response:
            return f"Final Answer: {cleaned_response}"
        
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
        max_iterations=LLM_MAX_ITERATIONS,
        max_execution_time=LLM_MAX_EXECUTION_TIME
    )


# ==============================================================================
# MAIN
# ==============================================================================

if __name__ == "__main__":
    print("\n" + "="*60)
    print(f"🤖 PE Portfolio Agent (Computation-First) | Model: {LLM_MODEL}")
    print("="*60 + "\n")
    
    agent_executor = setup_agent()
    
    questions = [
        "What is the TVPI and DPI of the entire portfolio?",
        "Which primary strategy has the highest Internal Rate of Return (IRR)?",
        "What is the total Paid-In capital for the 'Private Equity' strategy?",
        "Which specific fund has distributed the most capital to date?",
        "Show me the J-Curve for the 'Venture Capital' strategy.",
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
    
    # Close database connection
    db = get_db()
    db.close()
