"""
PE Metrics Computation Engine.

This module provides pure Python implementations of all Private Equity metrics
including IRR, TVPI, DPI, MoIC, Called %, and Distribution %.

All calculations are deterministic, testable, and independent of database logic.
"""

from typing import List, Tuple, Dict, Any, Optional
from datetime import datetime, date
import logging
from decimal import Decimal

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from config import IRR_MAX_ITERATIONS, IRR_TOLERANCE, IRR_INITIAL_GUESS

logger = logging.getLogger(__name__)


# ==============================================================================
# IRR CALCULATION (XIRR for irregular cash flows)
# ==============================================================================

def calculate_xirr(
    cash_flows: List[float],
    dates: List[datetime],
    initial_guess: float = IRR_INITIAL_GUESS,
    max_iterations: int = IRR_MAX_ITERATIONS,
    tolerance: float = IRR_TOLERANCE
) -> Optional[float]:
    """
    Calculate the Internal Rate of Return (IRR) for irregular cash flows using Newton-Raphson method.
    
    Args:
        cash_flows: List of cash flow amounts (negative for investments, positive for returns)
        dates: List of dates corresponding to each cash flow
        initial_guess: Initial guess for IRR (default: 0.1 or 10%)
        max_iterations: Maximum number of iterations for convergence
        tolerance: Convergence tolerance for NPV
        
    Returns:
        IRR as a decimal (e.g., 0.15 for 15%), or None if calculation fails
        
    Example:
        >>> cash_flows = [-100000, 10000, 20000, 30000, 50000]
        >>> dates = [date(2020, 1, 1), date(2021, 1, 1), date(2022, 1, 1), 
        ...          date(2023, 1, 1), date(2024, 1, 1)]
        >>> irr = calculate_xirr(cash_flows, dates)
        >>> print(f"IRR: {irr:.2%}")
    """
    if not cash_flows or len(cash_flows) < 2:
        logger.warning("Insufficient cash flows for IRR calculation")
        return None
        
    if len(cash_flows) != len(dates):
        logger.error("Cash flows and dates must have the same length")
        return None
    
    # Convert dates to years from start date
    start_date = dates[0]
    years = [(d - start_date).days / 365.25 for d in dates]
    
    rate = initial_guess
    
    for iteration in range(max_iterations):
        try:
            # Calculate NPV (Net Present Value)
            npv = sum([cf / (1 + rate) ** t for cf, t in zip(cash_flows, years)])
            
            # Calculate derivative of NPV
            dnpv = sum([-cf * t / (1 + rate) ** (t + 1) for cf, t in zip(cash_flows, years)])
            
            # Check for convergence
            if abs(npv) < tolerance:
                logger.debug(f"IRR converged in {iteration + 1} iterations: {rate:.6f}")
                return rate
            
            # Avoid division by zero
            if abs(dnpv) < tolerance:
                logger.warning("Derivative too small, IRR calculation may be unstable")
                return None
            
            # Newton-Raphson update
            rate = rate - npv / dnpv
            
            # Prevent extreme values
            if rate < -0.99 or rate > 10:
                logger.warning(f"IRR calculation diverging (rate={rate})")
                return None
                
        except (ZeroDivisionError, OverflowError) as e:
            logger.error(f"Error in IRR calculation: {e}")
            return None
    
    logger.warning(f"IRR did not converge after {max_iterations} iterations")
    return None


# ==============================================================================
# BASIC PE METRICS
# ==============================================================================

def calculate_tvpi(total_value: float, paid_in: float) -> Optional[float]:
    """
    Calculate Total Value to Paid-In (TVPI) multiple.
    
    TVPI = (Distributions + NAV) / Paid-In Capital
    
    Args:
        total_value: Sum of distributions and current NAV
        paid_in: Total capital paid in (contributions + fees)
        
    Returns:
        TVPI multiple, or None if paid_in is zero
        
    Example:
        >>> tvpi = calculate_tvpi(total_value=150000, paid_in=100000)
        >>> print(f"TVPI: {tvpi:.2f}x")
    """
    if paid_in <= 0:
        logger.warning("Paid-In capital must be positive for TVPI calculation")
        return None
    
    return total_value / paid_in


def calculate_dpi(distributions: float, paid_in: float) -> Optional[float]:
    """
    Calculate Distributions to Paid-In (DPI) multiple.
    
    DPI = Total Distributions / Paid-In Capital
    
    Args:
        distributions: Total distributions to investors
        paid_in: Total capital paid in (contributions + fees)
        
    Returns:
        DPI multiple, or None if paid_in is zero
    """
    if paid_in <= 0:
        logger.warning("Paid-In capital must be positive for DPI calculation")
        return None
    
    return distributions / paid_in


def calculate_rvpi(nav: float, paid_in: float) -> Optional[float]:
    """
    Calculate Residual Value to Paid-In (RVPI) multiple.
    
    RVPI = Current NAV / Paid-In Capital
    
    Args:
        nav: Current Net Asset Value
        paid_in: Total capital paid in (contributions + fees)
        
    Returns:
        RVPI multiple, or None if paid_in is zero
    """
    if paid_in <= 0:
        logger.warning("Paid-In capital must be positive for RVPI calculation")
        return None
    
    return nav / paid_in


def calculate_moic(total_value: float, invested_capital: float) -> Optional[float]:
    """
    Calculate Multiple on Invested Capital (MoIC).
    
    MoIC = Total Value / Invested Capital
    
    Note: Similar to TVPI but may exclude fees from denominator.
    
    Args:
        total_value: Sum of distributions and current NAV
        invested_capital: Total invested capital (may exclude fees)
        
    Returns:
        MoIC multiple, or None if invested_capital is zero
    """
    if invested_capital <= 0:
        logger.warning("Invested capital must be positive for MoIC calculation")
        return None
    
    return total_value / invested_capital


def calculate_called_percent(paid_in: float, commitment: float) -> Optional[float]:
    """
    Calculate the percentage of committed capital that has been called.
    
    Called % = (Paid-In Capital / Total Commitment) * 100
    
    Args:
        paid_in: Total capital paid in
        commitment: Total committed capital
        
    Returns:
        Percentage called (0-100), or None if commitment is zero
    """
    if commitment <= 0:
        logger.warning("Commitment must be positive for Called % calculation")
        return None
    
    return (paid_in / commitment) * 100


def calculate_distributed_percent(distributions: float, commitment: float) -> Optional[float]:
    """
    Calculate the percentage of committed capital that has been distributed.
    
    Distributed % = (Total Distributions / Total Commitment) * 100
    
    Args:
        distributions: Total distributions to investors
        commitment: Total committed capital
        
    Returns:
        Percentage distributed, or None if commitment is zero
    """
    if commitment <= 0:
        logger.warning("Commitment must be positive for Distributed % calculation")
        return None
    
    return (distributions / commitment) * 100


# ==============================================================================
# COMPREHENSIVE METRICS CALCULATION
# ==============================================================================

def calculate_all_metrics(
    cash_flows: List[float],
    dates: List[datetime],
    total_commitment: float,
    current_nav: float
) -> Dict[str, Any]:
    """
    Calculate all PE metrics for a given investment.
    
    Args:
        cash_flows: List of cash flows (negative for calls, positive for distributions)
        dates: Corresponding dates for each cash flow
        total_commitment: Total committed capital
        current_nav: Current Net Asset Value
        
    Returns:
        Dictionary containing all calculated metrics
        
    Example:
        >>> metrics = calculate_all_metrics(
        ...     cash_flows=[-100000, 10000, 20000, 30000],
        ...     dates=[date(2020, 1, 1), date(2021, 1, 1), date(2022, 1, 1), date(2023, 1, 1)],
        ...     total_commitment=150000,
        ...     current_nav=50000
        ... )
        >>> print(f"IRR: {metrics['irr']:.2%}, TVPI: {metrics['tvpi']:.2f}x")
    """
    # Separate calls and distributions
    paid_in = abs(sum([cf for cf in cash_flows if cf < 0]))
    distributions = sum([cf for cf in cash_flows if cf > 0])
    total_value = distributions + current_nav
    
    # Calculate all metrics
    metrics = {
        "paid_in": paid_in,
        "distributions": distributions,
        "current_nav": current_nav,
        "total_value": total_value,
        "total_commitment": total_commitment,
        "unfunded_commitment": total_commitment - paid_in,
        "irr": calculate_xirr(cash_flows + [current_nav], dates + [dates[-1]]) if cash_flows else None,
        "tvpi": calculate_tvpi(total_value, paid_in),
        "dpi": calculate_dpi(distributions, paid_in),
        "rvpi": calculate_rvpi(current_nav, paid_in),
        "moic": calculate_moic(total_value, paid_in),
        "called_percent": calculate_called_percent(paid_in, total_commitment),
        "distributed_percent": calculate_distributed_percent(distributions, total_commitment)
    }
    
    logger.debug(f"Calculated metrics: {metrics}")
    return metrics


# ==============================================================================
# AGGREGATE METRICS (for hierarchy levels)
# ==============================================================================

def aggregate_metrics(fund_metrics_list: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Aggregate metrics across multiple funds for portfolio/strategy level calculations.
    
    Args:
        fund_metrics_list: List of metric dictionaries from individual funds
        
    Returns:
        Aggregated metrics dictionary
        
    Note:
        - IRR is recalculated from combined cash flows
        - Multiples are weighted averages based on paid-in capital
    """
    if not fund_metrics_list:
        logger.warning("No fund metrics provided for aggregation")
        return {}
    
    # Sum up basic values
    total_paid_in = sum([m.get("paid_in", 0) for m in fund_metrics_list])
    total_distributions = sum([m.get("distributions", 0) for m in fund_metrics_list])
    total_nav = sum([m.get("current_nav", 0) for m in fund_metrics_list])
    total_commitment = sum([m.get("total_commitment", 0) for m in fund_metrics_list])
    total_value = total_distributions + total_nav
    
    # Calculate aggregated metrics
    aggregated = {
        "paid_in": total_paid_in,
        "distributions": total_distributions,
        "current_nav": total_nav,
        "total_value": total_value,
        "total_commitment": total_commitment,
        "unfunded_commitment": total_commitment - total_paid_in,
        "tvpi": calculate_tvpi(total_value, total_paid_in),
        "dpi": calculate_dpi(total_distributions, total_paid_in),
        "rvpi": calculate_rvpi(total_nav, total_paid_in),
        "moic": calculate_moic(total_value, total_paid_in),
        "called_percent": calculate_called_percent(total_paid_in, total_commitment),
        "distributed_percent": calculate_distributed_percent(total_distributions, total_commitment),
        "fund_count": len(fund_metrics_list)
    }
    
    # Note: IRR aggregation requires combined cash flows from all funds
    # This should be calculated at the database query level or by passing combined cash flows
    
    logger.debug(f"Aggregated metrics for {len(fund_metrics_list)} funds")
    return aggregated
