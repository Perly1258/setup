"""
Cash Flow Processing Engine.

This module provides flexible cash flow aggregation, filtering, and analysis
capabilities for Private Equity portfolios.
"""

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, date
from enum import Enum
import logging

logger = logging.getLogger(__name__)


# ==============================================================================
# ENUMS AND CONSTANTS
# ==============================================================================

class CashFlowType(Enum):
    """Cash flow transaction types."""
    CALL_INVESTMENT = "call_investment"
    CALL_FEES = "call_fees"
    DISTRIBUTION_PROFIT = "distribution_profit"
    DISTRIBUTION_RETURN_OF_CAPITAL = "distribution_return_of_capital"
    NAV_UPDATE = "nav_update"


class AggregationPeriod(Enum):
    """Time period aggregation options."""
    QUARTERLY = "quarterly"
    YEARLY = "yearly"
    MONTHLY = "monthly"
    ALL_TIME = "all_time"


# ==============================================================================
# CASH FLOW DATA STRUCTURES
# ==============================================================================

class CashFlow:
    """
    Represents a single cash flow transaction.
    """
    def __init__(
        self,
        transaction_id: int,
        fund_id: int,
        date: datetime,
        cf_type: str,
        amount: float,
        description: Optional[str] = None
    ):
        self.transaction_id = transaction_id
        self.fund_id = fund_id
        self.date = date
        self.cf_type = cf_type
        self.amount = amount
        self.description = description
    
    def is_call(self) -> bool:
        """Check if this is a capital call."""
        return self.amount < 0
    
    def is_distribution(self) -> bool:
        """Check if this is a distribution."""
        return self.amount > 0
    
    def __repr__(self) -> str:
        return f"CashFlow(fund={self.fund_id}, date={self.date}, type={self.cf_type}, amount={self.amount})"


# ==============================================================================
# CASH FLOW PROCESSING FUNCTIONS
# ==============================================================================

def aggregate_by_period(
    cash_flows: List[CashFlow],
    period: AggregationPeriod
) -> Dict[str, float]:
    """
    Aggregate cash flows by time period.
    
    Args:
        cash_flows: List of CashFlow objects
        period: Aggregation period (quarterly, yearly, monthly, all_time)
        
    Returns:
        Dictionary mapping period keys to total cash flow amounts
        
    Example:
        >>> cfs = [CashFlow(1, 1, date(2020, 3, 31), "call", -10000), ...]
        >>> yearly_totals = aggregate_by_period(cfs, AggregationPeriod.YEARLY)
        >>> print(yearly_totals)  # {'2020': -50000, '2021': 30000, ...}
    """
    aggregated: Dict[str, float] = {}
    
    for cf in cash_flows:
        if period == AggregationPeriod.YEARLY:
            key = str(cf.date.year)
        elif period == AggregationPeriod.QUARTERLY:
            quarter = (cf.date.month - 1) // 3 + 1
            key = f"{cf.date.year}-Q{quarter}"
        elif period == AggregationPeriod.MONTHLY:
            key = f"{cf.date.year}-{cf.date.month:02d}"
        else:  # ALL_TIME
            key = "all_time"
        
        aggregated[key] = aggregated.get(key, 0) + cf.amount
    
    logger.debug(f"Aggregated {len(cash_flows)} cash flows into {len(aggregated)} periods")
    return aggregated


def calculate_cumulative_cash_flows(
    cash_flows: List[CashFlow]
) -> List[Tuple[datetime, float]]:
    """
    Calculate cumulative cash flows over time.
    
    Args:
        cash_flows: List of CashFlow objects (must be sorted by date)
        
    Returns:
        List of (date, cumulative_amount) tuples
        
    Example:
        >>> cfs = [CashFlow(1, 1, date(2020, 1, 1), "call", -100), 
        ...        CashFlow(2, 1, date(2020, 6, 1), "dist", 20)]
        >>> cumulative = calculate_cumulative_cash_flows(cfs)
        >>> # [(date(2020, 1, 1), -100), (date(2020, 6, 1), -80)]
    """
    # Sort by date to ensure correct cumulative calculation
    sorted_cfs = sorted(cash_flows, key=lambda cf: cf.date)
    
    cumulative = 0
    cumulative_series = []
    
    for cf in sorted_cfs:
        cumulative += cf.amount
        cumulative_series.append((cf.date, cumulative))
    
    return cumulative_series


def separate_calls_and_distributions(
    cash_flows: List[CashFlow],
    include_fees: bool = True
) -> Tuple[List[CashFlow], List[CashFlow]]:
    """
    Separate cash flows into calls and distributions.
    
    Args:
        cash_flows: List of CashFlow objects
        include_fees: Whether to include management fees in calls
        
    Returns:
        Tuple of (calls, distributions) lists
    """
    calls = []
    distributions = []
    
    for cf in cash_flows:
        if cf.is_call():
            if include_fees or "fee" not in cf.cf_type.lower():
                calls.append(cf)
        elif cf.is_distribution():
            distributions.append(cf)
    
    logger.debug(f"Separated into {len(calls)} calls and {len(distributions)} distributions")
    return calls, distributions


def calculate_net_cash_flow(
    calls: List[CashFlow],
    distributions: List[CashFlow]
) -> float:
    """
    Calculate net cash flow (distributions - calls).
    
    Args:
        calls: List of capital call CashFlow objects
        distributions: List of distribution CashFlow objects
        
    Returns:
        Net cash flow amount (positive if distributions exceed calls)
    """
    total_calls = sum([abs(cf.amount) for cf in calls])
    total_distributions = sum([cf.amount for cf in distributions])
    
    return total_distributions - total_calls


def filter_by_date_range(
    cash_flows: List[CashFlow],
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> List[CashFlow]:
    """
    Filter cash flows by date range.
    
    Args:
        cash_flows: List of CashFlow objects
        start_date: Start date (inclusive), None for no lower bound
        end_date: End date (inclusive), None for no upper bound
        
    Returns:
        Filtered list of CashFlow objects
    """
    filtered = cash_flows
    
    if start_date:
        filtered = [cf for cf in filtered if cf.date >= start_date]
    
    if end_date:
        filtered = [cf for cf in filtered if cf.date <= end_date]
    
    logger.debug(f"Filtered to {len(filtered)} cash flows in date range")
    return filtered


def filter_by_fund(
    cash_flows: List[CashFlow],
    fund_ids: List[int]
) -> List[CashFlow]:
    """
    Filter cash flows by fund IDs.
    
    Args:
        cash_flows: List of CashFlow objects
        fund_ids: List of fund IDs to include
        
    Returns:
        Filtered list of CashFlow objects
    """
    filtered = [cf for cf in cash_flows if cf.fund_id in fund_ids]
    logger.debug(f"Filtered to {len(filtered)} cash flows for {len(fund_ids)} funds")
    return filtered


# ==============================================================================
# J-CURVE ANALYSIS
# ==============================================================================

def calculate_j_curve(
    cash_flows: List[CashFlow],
    period: AggregationPeriod = AggregationPeriod.YEARLY
) -> List[Dict[str, Any]]:
    """
    Calculate J-Curve data showing cumulative net cash flows over time.
    
    Args:
        cash_flows: List of CashFlow objects
        period: Time period for aggregation
        
    Returns:
        List of dictionaries with period, net_flow, and cumulative_flow
        
    Example:
        >>> j_curve = calculate_j_curve(cash_flows, AggregationPeriod.YEARLY)
        >>> # [{'period': '2020', 'net_flow': -100, 'cumulative': -100},
        >>> #  {'period': '2021', 'net_flow': 20, 'cumulative': -80}, ...]
    """
    # Aggregate by period
    aggregated = aggregate_by_period(cash_flows, period)
    
    # Sort by period
    sorted_periods = sorted(aggregated.keys())
    
    # Calculate cumulative values
    j_curve_data = []
    cumulative = 0
    
    for period_key in sorted_periods:
        net_flow = aggregated[period_key]
        cumulative += net_flow
        
        j_curve_data.append({
            "period": period_key,
            "net_flow": net_flow,
            "cumulative_flow": cumulative
        })
    
    logger.debug(f"Generated J-Curve with {len(j_curve_data)} data points")
    return j_curve_data


# ==============================================================================
# YEAR-TO-DATE (YTD) CALCULATIONS
# ==============================================================================

def calculate_ytd_metrics(
    cash_flows: List[CashFlow],
    reference_date: Optional[datetime] = None
) -> Dict[str, Any]:
    """
    Calculate year-to-date metrics.
    
    Args:
        cash_flows: List of CashFlow objects
        reference_date: Reference date for YTD calculation (defaults to today)
        
    Returns:
        Dictionary with YTD calls, distributions, and net flow
    """
    if reference_date is None:
        reference_date = datetime.now()
    
    # Filter to current year only
    year_start = datetime(reference_date.year, 1, 1)
    ytd_flows = filter_by_date_range(cash_flows, year_start, reference_date)
    
    # Separate and sum
    calls, distributions = separate_calls_and_distributions(ytd_flows)
    
    total_calls = sum([abs(cf.amount) for cf in calls])
    total_distributions = sum([cf.amount for cf in distributions])
    
    return {
        "ytd_calls": total_calls,
        "ytd_distributions": total_distributions,
        "ytd_net_flow": total_distributions - total_calls,
        "ytd_transaction_count": len(ytd_flows),
        "reference_year": reference_date.year
    }


# ==============================================================================
# CASH FLOW SUMMARY
# ==============================================================================

def generate_cash_flow_summary(
    cash_flows: List[CashFlow],
    include_fees: bool = True,
    period: AggregationPeriod = AggregationPeriod.YEARLY
) -> Dict[str, Any]:
    """
    Generate a comprehensive summary of cash flows.
    
    Args:
        cash_flows: List of CashFlow objects
        include_fees: Whether to include management fees in calculations
        period: Aggregation period for time-series data
        
    Returns:
        Dictionary containing comprehensive cash flow analysis
    """
    calls, distributions = separate_calls_and_distributions(cash_flows, include_fees)
    
    total_calls = sum([abs(cf.amount) for cf in calls])
    total_distributions = sum([cf.amount for cf in distributions])
    net_flow = total_distributions - total_calls
    
    # Time series data
    aggregated = aggregate_by_period(cash_flows, period)
    j_curve = calculate_j_curve(cash_flows, period)
    
    # YTD metrics
    ytd = calculate_ytd_metrics(cash_flows)
    
    summary = {
        "total_calls": total_calls,
        "total_distributions": total_distributions,
        "net_cash_flow": net_flow,
        "call_count": len(calls),
        "distribution_count": len(distributions),
        "total_transactions": len(cash_flows),
        "earliest_date": min([cf.date for cf in cash_flows]) if cash_flows else None,
        "latest_date": max([cf.date for cf in cash_flows]) if cash_flows else None,
        "aggregated_by_period": aggregated,
        "j_curve": j_curve,
        "ytd_metrics": ytd
    }
    
    logger.info(f"Generated cash flow summary with {len(cash_flows)} transactions")
    return summary
