"""
Data Layer Package.

This package handles all database interactions and data retrieval.
"""

from .db_adapter import (
    DatabaseConnection,
    get_fund_list,
    get_cash_flows,
    get_latest_nav,
    get_modeling_assumptions,
    calculate_fund_metrics,
    calculate_strategy_metrics,
    calculate_portfolio_metrics,
    cache_metrics
)

__all__ = [
    "DatabaseConnection",
    "get_fund_list",
    "get_cash_flows",
    "get_latest_nav",
    "get_modeling_assumptions",
    "calculate_fund_metrics",
    "calculate_strategy_metrics",
    "calculate_portfolio_metrics",
    "cache_metrics"
]
