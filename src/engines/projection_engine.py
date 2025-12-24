"""
Projection Engine for Future Cash Flow Forecasting.

This module implements the Takahashi/Alexander model for PE cash flow projections
and includes an allocation optimizer for maintaining constant strategy exposure.
"""

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from enum import Enum
import logging
import math

logger = logging.getLogger(__name__)


# ==============================================================================
# PROJECTION MODELS
# ==============================================================================

class ProjectionModel(Enum):
    """Available projection models."""
    TAKAHASHI_ALEXANDER = "takahashi_alexander"
    YALE_MODEL = "yale_model"
    LINEAR = "linear"


class CashFlowShape(Enum):
    """Cash flow distribution shapes."""
    S_CURVE = "s_curve"  # For capital calls
    J_CURVE = "j_curve"  # For distributions
    LINEAR = "linear"
    EXPONENTIAL = "exponential"


# ==============================================================================
# SHAPE GENERATION FUNCTIONS
# ==============================================================================

def generate_s_curve(
    num_periods: int,
    peak_period: int,
    steepness: float = 2.0
) -> List[float]:
    """
    Generate an S-curve shape for capital call distribution.
    
    Args:
        num_periods: Number of time periods
        peak_period: Period where the curve peaks
        steepness: Controls curve steepness (higher = steeper)
        
    Returns:
        List of normalized values (sum = 1.0)
    """
    values = []
    for i in range(num_periods):
        # Sigmoid function centered at peak_period
        x = (i - peak_period) / (num_periods / steepness)
        sigmoid = 1 / (1 + math.exp(-x))
        values.append(sigmoid)
    
    # Normalize to sum to 1.0
    total = sum(values)
    if total > 0:
        values = [v / total for v in values]
    
    return values


def generate_j_curve(
    num_periods: int,
    trough_period: int,
    recovery_steepness: float = 1.5
) -> List[float]:
    """
    Generate a J-curve shape for distribution patterns.
    
    Args:
        num_periods: Number of time periods
        trough_period: Period where the J-curve reaches its trough
        recovery_steepness: Controls recovery steepness
        
    Returns:
        List of normalized values (sum = 1.0)
    """
    values = []
    for i in range(num_periods):
        if i < trough_period:
            # Declining phase (low distributions)
            values.append(0.01)
        else:
            # Recovery phase (increasing distributions)
            x = (i - trough_period) / recovery_steepness
            exponential = math.exp(x / num_periods)
            values.append(exponential)
    
    # Normalize to sum to 1.0
    total = sum(values)
    if total > 0:
        values = [v / total for v in values]
    
    return values


def get_strategy_shape_params(strategy: str, num_periods: int) -> Dict[str, Any]:
    """
    Get shape parameters for different PE strategies.
    
    Args:
        strategy: Primary strategy name
        num_periods: Number of projection periods
        
    Returns:
        Dictionary with shape parameters for calls and distributions
    """
    # Default parameters by strategy
    params = {
        "Venture Capital": {
            "call_peak": int(num_periods * 0.3),  # Early investment
            "call_steepness": 2.5,
            "dist_trough": int(num_periods * 0.5),  # Late returns
            "dist_steepness": 1.2,
            "j_curve_depth": 0.15  # Deep J-curve
        },
        "Private Equity": {
            "call_peak": int(num_periods * 0.4),
            "call_steepness": 2.0,
            "dist_trough": int(num_periods * 0.4),
            "dist_steepness": 1.5,
            "j_curve_depth": 0.08
        },
        "Real Estate": {
            "call_peak": int(num_periods * 0.2),  # Fast deployment
            "call_steepness": 3.0,
            "dist_trough": int(num_periods * 0.1),  # Quick returns
            "dist_steepness": 2.0,
            "j_curve_depth": 0.02
        },
        "Infrastructure": {
            "call_peak": int(num_periods * 0.5),  # Slow deployment
            "call_steepness": 1.5,
            "dist_trough": int(num_periods * 0.2),  # Steady returns
            "dist_steepness": 3.0,
            "j_curve_depth": 0.01
        }
    }
    
    return params.get(strategy, params["Private Equity"])


# ==============================================================================
# TAKAHASHI/ALEXANDER MODEL IMPLEMENTATION
# ==============================================================================

def project_cash_flows_takahashi(
    unfunded_commitment: float,
    current_nav: float,
    expected_moic: float,
    target_irr: float,
    strategy: str,
    num_periods: int,
    management_fee_rate: float = 0.02,  # 2% annually
    vintage_year: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Project future cash flows using the Takahashi/Alexander model.
    
    This model accounts for:
    - Strategy-specific deployment and distribution patterns
    - J-curve effects (initial NAV depreciation)
    - Target IRR and MOIC constraints
    - Management fee structures
    
    Args:
        unfunded_commitment: Remaining unfunded commitment
        current_nav: Current Net Asset Value
        expected_moic: Expected Multiple on Invested Capital
        target_irr: Target Internal Rate of Return (as decimal)
        strategy: Primary strategy name
        num_periods: Number of quarters to project
        management_fee_rate: Annual management fee rate
        vintage_year: Fund vintage year (for fee calculation)
        
    Returns:
        List of projected cash flow dictionaries by period
    """
    # Get strategy-specific parameters
    shape_params = get_strategy_shape_params(strategy, num_periods)
    
    # Generate distribution shapes
    call_shape = generate_s_curve(
        num_periods,
        shape_params["call_peak"],
        shape_params["call_steepness"]
    )
    
    dist_shape = generate_j_curve(
        num_periods,
        shape_params["dist_trough"],
        shape_params["dist_steepness"]
    )
    
    # Calculate target distributions needed
    # Assume all unfunded commitment will be called
    total_investment = unfunded_commitment
    target_total_value = total_investment * expected_moic
    target_distributions = max(0, target_total_value - current_nav)
    
    # Initialize projection
    projections = []
    nav = current_nav
    remaining_commitment = unfunded_commitment
    remaining_distributions = target_distributions
    
    quarterly_fee_rate = management_fee_rate / 4
    current_year = datetime.now().year
    
    for period in range(num_periods):
        period_data = {
            "period": period + 1,
            "quarter_date": datetime.now() + timedelta(days=90 * (period + 1))
        }
        
        # --- CAPITAL CALLS ---
        call_investment = remaining_commitment * call_shape[period]
        
        # Management fees (2% of commitment for first 5 years, then 1%)
        years_since_vintage = (current_year + period // 4) - (vintage_year or current_year)
        if years_since_vintage <= 5:
            management_fees = (unfunded_commitment + current_nav) * quarterly_fee_rate
        else:
            management_fees = (unfunded_commitment + current_nav) * (quarterly_fee_rate / 2)
        
        period_data["call_investment"] = -call_investment
        period_data["management_fees"] = -management_fees
        
        remaining_commitment -= call_investment
        
        # --- DISTRIBUTIONS ---
        distribution = remaining_distributions * dist_shape[period]
        period_data["distribution"] = distribution
        
        remaining_distributions -= distribution
        
        # --- NAV EVOLUTION ---
        # Apply J-curve depreciation in early periods
        if period < shape_params["dist_trough"]:
            # Initial depreciation phase
            depreciation_rate = -shape_params["j_curve_depth"] / 4  # Quarterly
            nav_change = nav * depreciation_rate
        else:
            # Growth phase - derive from target IRR
            quarterly_growth = (1 + target_irr) ** 0.25 - 1
            nav_change = nav * quarterly_growth
        
        # Update NAV with investment, fees, distributions, and appreciation
        nav = nav + call_investment - management_fees - distribution + nav_change
        nav = max(0, nav)  # NAV floor at zero
        
        period_data["nav"] = nav
        period_data["nav_change"] = nav_change
        
        projections.append(period_data)
    
    logger.info(f"Generated {num_periods} period Takahashi projection for {strategy}")
    return projections


# ==============================================================================
# ALLOCATION OPTIMIZER
# ==============================================================================

def calculate_optimal_allocation(
    current_exposures: Dict[str, float],
    target_exposures: Dict[str, float],
    available_capital: float,
    projected_distributions: Dict[str, float],
    constraints: Optional[Dict[str, Any]] = None
) -> Dict[str, float]:
    """
    Calculate optimal new investments to maintain target strategy exposures.
    
    This optimizer helps answer: "How much should I invest in each strategy
    to maintain constant exposure levels given expected distributions?"
    
    Args:
        current_exposures: Current NAV by strategy
        target_exposures: Target allocation percentages by strategy
        available_capital: Available capital for new investments
        projected_distributions: Expected distributions by strategy (next 12 months)
        constraints: Optional constraints (min/max allocation, etc.)
        
    Returns:
        Dictionary of recommended allocations by strategy
        
    Example:
        >>> current = {"VC": 1000, "PE": 2000, "RE": 1000}
        >>> target = {"VC": 0.30, "PE": 0.50, "RE": 0.20}
        >>> available = 500
        >>> projected = {"VC": 100, "PE": 200, "RE": 150}
        >>> allocations = calculate_optimal_allocation(current, target, available, projected)
    """
    if constraints is None:
        constraints = {}
    
    # Calculate total portfolio value after projected distributions
    total_current = sum(current_exposures.values())
    total_distributions = sum(projected_distributions.values())
    projected_total = total_current - total_distributions + available_capital
    
    # Calculate target values by strategy
    target_values = {
        strategy: projected_total * pct
        for strategy, pct in target_exposures.items()
    }
    
    # Calculate gaps (what we need to invest to reach target)
    allocations = {}
    total_allocated = 0
    
    for strategy, target_value in target_values.items():
        current = current_exposures.get(strategy, 0)
        projected_dist = projected_distributions.get(strategy, 0)
        projected_value = current - projected_dist
        
        # Gap to target
        gap = target_value - projected_value
        
        # Apply constraints
        min_alloc = constraints.get(f"{strategy}_min", 0)
        max_alloc = constraints.get(f"{strategy}_max", available_capital)
        
        # Allocate to fill gap (within constraints)
        allocation = max(min_alloc, min(gap, max_alloc))
        allocation = max(0, allocation)  # No negative allocations
        
        allocations[strategy] = allocation
        total_allocated += allocation
    
    # Scale if we've over-allocated
    if total_allocated > available_capital:
        scale_factor = available_capital / total_allocated
        allocations = {k: v * scale_factor for k, v in allocations.items()}
    
    logger.info(f"Calculated optimal allocation across {len(allocations)} strategies")
    return allocations


# ==============================================================================
# PORTFOLIO PROJECTION
# ==============================================================================

def project_portfolio_cash_flows(
    funds_data: List[Dict[str, Any]],
    modeling_assumptions: Dict[str, Dict[str, Any]],
    num_periods: int = 20
) -> Dict[str, Any]:
    """
    Project cash flows for entire portfolio.
    
    Args:
        funds_data: List of fund dictionaries with current state
        modeling_assumptions: Strategy-level modeling parameters
        num_periods: Number of quarters to project
        
    Returns:
        Dictionary containing portfolio-level projections
    """
    portfolio_projections = {
        "total_calls": [0] * num_periods,
        "total_distributions": [0] * num_periods,
        "total_fees": [0] * num_periods,
        "total_nav": [0] * num_periods,
        "by_strategy": {},
        "by_fund": []
    }
    
    for fund in funds_data:
        strategy = fund.get("primary_strategy", "Private Equity")
        assumptions = modeling_assumptions.get(strategy, {})
        
        # Project cash flows for this fund
        fund_projection = project_cash_flows_takahashi(
            unfunded_commitment=fund.get("unfunded_commitment", 0),
            current_nav=fund.get("current_nav", 0),
            expected_moic=assumptions.get("expected_moic", 2.0),
            target_irr=assumptions.get("target_irr", 0.15),
            strategy=strategy,
            num_periods=num_periods,
            vintage_year=fund.get("vintage_year")
        )
        
        # Aggregate to portfolio level
        for i, period_data in enumerate(fund_projection):
            portfolio_projections["total_calls"][i] += abs(period_data.get("call_investment", 0))
            portfolio_projections["total_distributions"][i] += period_data.get("distribution", 0)
            portfolio_projections["total_fees"][i] += abs(period_data.get("management_fees", 0))
            portfolio_projections["total_nav"][i] += period_data.get("nav", 0)
        
        # Store by strategy
        if strategy not in portfolio_projections["by_strategy"]:
            portfolio_projections["by_strategy"][strategy] = {
                "calls": [0] * num_periods,
                "distributions": [0] * num_periods,
                "nav": [0] * num_periods
            }
        
        for i, period_data in enumerate(fund_projection):
            portfolio_projections["by_strategy"][strategy]["calls"][i] += abs(period_data.get("call_investment", 0))
            portfolio_projections["by_strategy"][strategy]["distributions"][i] += period_data.get("distribution", 0)
            portfolio_projections["by_strategy"][strategy]["nav"][i] += period_data.get("nav", 0)
        
        # Store fund-level projection
        portfolio_projections["by_fund"].append({
            "fund_id": fund.get("fund_id"),
            "fund_name": fund.get("fund_name"),
            "projection": fund_projection
        })
    
    logger.info(f"Projected portfolio cash flows for {len(funds_data)} funds over {num_periods} periods")
    return portfolio_projections
