"""
Computation Engines Package.

This package contains all pure Python computation modules for PE portfolio analysis.
These modules are independent of database logic and LLM integration.
"""

from .pe_metrics_engine import (
    calculate_xirr,
    calculate_tvpi,
    calculate_dpi,
    calculate_rvpi,
    calculate_moic,
    calculate_called_percent,
    calculate_distributed_percent,
    calculate_all_metrics,
    aggregate_metrics
)

from .cash_flow_engine import (
    CashFlow,
    CashFlowType,
    AggregationPeriod,
    aggregate_by_period,
    calculate_cumulative_cash_flows,
    separate_calls_and_distributions,
    calculate_net_cash_flow,
    filter_by_date_range,
    filter_by_fund,
    calculate_j_curve,
    calculate_ytd_metrics,
    generate_cash_flow_summary
)

from .projection_engine import (
    ProjectionModel,
    CashFlowShape,
    generate_s_curve,
    generate_j_curve,
    get_strategy_shape_params,
    project_cash_flows_takahashi,
    calculate_optimal_allocation,
    project_portfolio_cash_flows
)

from .visualization_engine import (
    prepare_j_curve_data,
    prepare_tvpi_evolution_data,
    prepare_allocation_chart_data,
    prepare_waterfall_chart_data,
    prepare_heatmap_data,
    format_currency,
    format_percentage,
    format_multiple,
    generate_chart_summary,
    export_chart_config
)

__all__ = [
    # PE Metrics
    "calculate_xirr",
    "calculate_tvpi",
    "calculate_dpi",
    "calculate_rvpi",
    "calculate_moic",
    "calculate_called_percent",
    "calculate_distributed_percent",
    "calculate_all_metrics",
    "aggregate_metrics",
    
    # Cash Flow
    "CashFlow",
    "CashFlowType",
    "AggregationPeriod",
    "aggregate_by_period",
    "calculate_cumulative_cash_flows",
    "separate_calls_and_distributions",
    "calculate_net_cash_flow",
    "filter_by_date_range",
    "filter_by_fund",
    "calculate_j_curve",
    "calculate_ytd_metrics",
    "generate_cash_flow_summary",
    
    # Projection
    "ProjectionModel",
    "CashFlowShape",
    "generate_s_curve",
    "generate_j_curve",
    "get_strategy_shape_params",
    "project_cash_flows_takahashi",
    "calculate_optimal_allocation",
    "project_portfolio_cash_flows",
    
    # Visualization
    "prepare_j_curve_data",
    "prepare_tvpi_evolution_data",
    "prepare_allocation_chart_data",
    "prepare_waterfall_chart_data",
    "prepare_heatmap_data",
    "format_currency",
    "format_percentage",
    "format_multiple",
    "generate_chart_summary",
    "export_chart_config"
]
