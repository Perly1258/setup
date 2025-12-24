"""
Visualization Engine for PE Portfolio Analysis.

This module generates charts and visualizations for:
- J-Curve analysis
- TVPI evolution over time
- Allocation recommendations
- Cash flow waterfall charts
"""

from typing import List, Dict, Any, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


# ==============================================================================
# CHART DATA PREPARATION
# ==============================================================================

def prepare_j_curve_data(
    periods: List[str],
    cumulative_flows: List[float],
    discrete_flows: Optional[List[float]] = None
) -> Dict[str, Any]:
    """
    Prepare data for J-Curve visualization.
    
    Args:
        periods: List of period labels (e.g., ['2020', '2021', '2022'])
        cumulative_flows: Cumulative net cash flows
        discrete_flows: Optional discrete cash flows per period
        
    Returns:
        Dictionary with chart data and metadata
        
    Example:
        >>> data = prepare_j_curve_data(
        ...     periods=['2020', '2021', '2022', '2023'],
        ...     cumulative_flows=[-100, -80, -50, 20],
        ...     discrete_flows=[-100, 20, 30, 70]
        ... )
    """
    chart_data = {
        "chart_type": "j_curve",
        "x_axis": {
            "label": "Period",
            "values": periods
        },
        "y_axis": {
            "label": "Cash Flow (Cumulative)",
            "unit": "currency"
        },
        "series": [
            {
                "name": "Cumulative Net Cash Flow",
                "type": "line",
                "data": cumulative_flows,
                "color": "#1f77b4"
            }
        ],
        "annotations": []
    }
    
    # Add discrete flows if provided
    if discrete_flows:
        chart_data["series"].append({
            "name": "Period Net Cash Flow",
            "type": "bar",
            "data": discrete_flows,
            "color": "#ff7f0e"
        })
    
    # Find trough (lowest point) for annotation
    if cumulative_flows:
        min_value = min(cumulative_flows)
        min_index = cumulative_flows.index(min_value)
        chart_data["annotations"].append({
            "type": "point",
            "x": periods[min_index],
            "y": min_value,
            "label": f"Trough: {min_value:,.0f}"
        })
    
    logger.debug(f"Prepared J-Curve data with {len(periods)} periods")
    return chart_data


def prepare_tvpi_evolution_data(
    periods: List[str],
    tvpi_values: List[float],
    dpi_values: Optional[List[float]] = None,
    rvpi_values: Optional[List[float]] = None
) -> Dict[str, Any]:
    """
    Prepare data for TVPI evolution chart.
    
    Args:
        periods: List of period labels
        tvpi_values: TVPI values over time
        dpi_values: Optional DPI values over time
        rvpi_values: Optional RVPI values over time
        
    Returns:
        Dictionary with chart data and metadata
    """
    chart_data = {
        "chart_type": "tvpi_evolution",
        "x_axis": {
            "label": "Period",
            "values": periods
        },
        "y_axis": {
            "label": "Multiple",
            "unit": "multiple"
        },
        "series": [
            {
                "name": "TVPI",
                "type": "line",
                "data": tvpi_values,
                "color": "#2ca02c",
                "line_width": 3
            }
        ],
        "annotations": []
    }
    
    # Add DPI if provided
    if dpi_values:
        chart_data["series"].append({
            "name": "DPI",
            "type": "line",
            "data": dpi_values,
            "color": "#d62728",
            "line_style": "dashed"
        })
    
    # Add RVPI if provided
    if rvpi_values:
        chart_data["series"].append({
            "name": "RVPI",
            "type": "line",
            "data": rvpi_values,
            "color": "#9467bd",
            "line_style": "dotted"
        })
    
    # Add reference line at 1.0x
    chart_data["annotations"].append({
        "type": "horizontal_line",
        "y": 1.0,
        "label": "Break-even (1.0x)",
        "color": "#7f7f7f",
        "line_style": "dashed"
    })
    
    # Add latest value annotation
    if tvpi_values:
        latest_tvpi = tvpi_values[-1]
        chart_data["annotations"].append({
            "type": "point",
            "x": periods[-1],
            "y": latest_tvpi,
            "label": f"Current: {latest_tvpi:.2f}x"
        })
    
    logger.debug(f"Prepared TVPI evolution data with {len(periods)} periods")
    return chart_data


def prepare_allocation_chart_data(
    strategies: List[str],
    current_allocations: List[float],
    target_allocations: List[float],
    recommended_investments: Optional[List[float]] = None
) -> Dict[str, Any]:
    """
    Prepare data for allocation comparison chart.
    
    Args:
        strategies: List of strategy names
        current_allocations: Current allocation percentages
        target_allocations: Target allocation percentages
        recommended_investments: Optional recommended new investment amounts
        
    Returns:
        Dictionary with chart data and metadata
    """
    chart_data = {
        "chart_type": "allocation_comparison",
        "x_axis": {
            "label": "Strategy",
            "values": strategies
        },
        "y_axis": {
            "label": "Allocation %",
            "unit": "percentage"
        },
        "series": [
            {
                "name": "Current Allocation",
                "type": "bar",
                "data": current_allocations,
                "color": "#1f77b4"
            },
            {
                "name": "Target Allocation",
                "type": "bar",
                "data": target_allocations,
                "color": "#2ca02c"
            }
        ],
        "annotations": []
    }
    
    # Add recommended investments as overlay if provided
    if recommended_investments:
        chart_data["series"].append({
            "name": "Recommended Investment",
            "type": "scatter",
            "data": recommended_investments,
            "color": "#ff7f0e",
            "size": 10
        })
    
    # Add variance annotations
    for i, (current, target) in enumerate(zip(current_allocations, target_allocations)):
        variance = target - current
        if abs(variance) > 5:  # Only annotate significant variances
            chart_data["annotations"].append({
                "type": "text",
                "x": strategies[i],
                "y": max(current, target),
                "label": f"{variance:+.1f}%",
                "color": "#d62728" if variance < 0 else "#2ca02c"
            })
    
    logger.debug(f"Prepared allocation chart for {len(strategies)} strategies")
    return chart_data


def prepare_waterfall_chart_data(
    categories: List[str],
    values: List[float],
    start_value: float = 0,
    end_label: str = "Total"
) -> Dict[str, Any]:
    """
    Prepare data for waterfall chart (e.g., cash flow decomposition).
    
    Args:
        categories: List of category names
        values: Incremental values for each category
        start_value: Starting value (default: 0)
        end_label: Label for final total
        
    Returns:
        Dictionary with chart data and metadata
        
    Example:
        >>> data = prepare_waterfall_chart_data(
        ...     categories=['Calls', 'Distributions', 'Fees', 'NAV Change'],
        ...     values=[-100, 150, -10, 20],
        ...     start_value=1000,
        ...     end_label='Final NAV'
        ... )
    """
    # Calculate running totals
    running_total = start_value
    waterfall_data = []
    
    for category, value in zip(categories, values):
        waterfall_data.append({
            "category": category,
            "start": running_total,
            "change": value,
            "end": running_total + value,
            "is_positive": value >= 0
        })
        running_total += value
    
    chart_data = {
        "chart_type": "waterfall",
        "start_value": start_value,
        "end_value": running_total,
        "end_label": end_label,
        "data": waterfall_data,
        "x_axis": {
            "label": "Category",
            "values": ["Start"] + categories + [end_label]
        },
        "y_axis": {
            "label": "Value",
            "unit": "currency"
        }
    }
    
    logger.debug(f"Prepared waterfall chart with {len(categories)} categories")
    return chart_data


def prepare_heatmap_data(
    x_labels: List[str],
    y_labels: List[str],
    values: List[List[float]],
    title: str = "Performance Heatmap"
) -> Dict[str, Any]:
    """
    Prepare data for heatmap visualization.
    
    Args:
        x_labels: X-axis labels (e.g., years)
        y_labels: Y-axis labels (e.g., strategies)
        values: 2D array of values
        title: Chart title
        
    Returns:
        Dictionary with chart data and metadata
        
    Example:
        >>> data = prepare_heatmap_data(
        ...     x_labels=['2020', '2021', '2022'],
        ...     y_labels=['VC', 'PE', 'RE'],
        ...     values=[[1.2, 1.5, 1.8], [1.1, 1.3, 1.6], [1.0, 1.2, 1.4]],
        ...     title='TVPI by Strategy and Year'
        ... )
    """
    chart_data = {
        "chart_type": "heatmap",
        "title": title,
        "x_axis": {
            "label": "Period",
            "values": x_labels
        },
        "y_axis": {
            "label": "Category",
            "values": y_labels
        },
        "data": values,
        "color_scale": {
            "type": "sequential",
            "colors": ["#f7fbff", "#08519c"],  # Light blue to dark blue
            "min": min([min(row) for row in values]) if values else 0,
            "max": max([max(row) for row in values]) if values else 1
        }
    }
    
    logger.debug(f"Prepared heatmap with {len(x_labels)}x{len(y_labels)} cells")
    return chart_data


# ==============================================================================
# CHART FORMATTING UTILITIES
# ==============================================================================

def format_currency(value: float, decimals: int = 0) -> str:
    """Format value as currency."""
    if abs(value) >= 1_000_000_000:
        return f"${value/1_000_000_000:.{decimals}f}B"
    elif abs(value) >= 1_000_000:
        return f"${value/1_000_000:.{decimals}f}M"
    elif abs(value) >= 1_000:
        return f"${value/1_000:.{decimals}f}K"
    else:
        return f"${value:.{decimals}f}"


def format_percentage(value: float, decimals: int = 1) -> str:
    """Format value as percentage."""
    return f"{value:.{decimals}f}%"


def format_multiple(value: float, decimals: int = 2) -> str:
    """Format value as multiple."""
    return f"{value:.{decimals}f}x"


def generate_chart_summary(chart_data: Dict[str, Any]) -> str:
    """
    Generate a text summary of chart data.
    
    Args:
        chart_data: Chart data dictionary
        
    Returns:
        Text summary suitable for LLM response
    """
    chart_type = chart_data.get("chart_type", "unknown")
    
    if chart_type == "j_curve":
        periods = chart_data["x_axis"]["values"]
        cumulative = chart_data["series"][0]["data"]
        
        start_value = cumulative[0]
        end_value = cumulative[-1]
        min_value = min(cumulative)
        
        summary = f"J-Curve Analysis ({periods[0]} to {periods[-1]}):\n"
        summary += f"- Starting position: {format_currency(start_value)}\n"
        summary += f"- Trough (lowest point): {format_currency(min_value)}\n"
        summary += f"- Current position: {format_currency(end_value)}\n"
        summary += f"- Overall trend: {'Positive' if end_value > start_value else 'Negative'}"
        
    elif chart_type == "tvpi_evolution":
        periods = chart_data["x_axis"]["values"]
        tvpi = chart_data["series"][0]["data"]
        
        start_tvpi = tvpi[0]
        end_tvpi = tvpi[-1]
        
        summary = f"TVPI Evolution ({periods[0]} to {periods[-1]}):\n"
        summary += f"- Initial TVPI: {format_multiple(start_tvpi)}\n"
        summary += f"- Current TVPI: {format_multiple(end_tvpi)}\n"
        summary += f"- Change: {format_multiple(end_tvpi - start_tvpi)} "
        summary += f"({'improved' if end_tvpi > start_tvpi else 'declined'})"
        
    elif chart_type == "allocation_comparison":
        strategies = chart_data["x_axis"]["values"]
        current = chart_data["series"][0]["data"]
        target = chart_data["series"][1]["data"]
        
        summary = "Allocation Analysis:\n"
        for strat, curr, tgt in zip(strategies, current, target):
            variance = tgt - curr
            summary += f"- {strat}: {format_percentage(curr)} current, "
            summary += f"{format_percentage(tgt)} target ({variance:+.1f}% variance)\n"
        
    else:
        summary = f"Chart data prepared for {chart_type}"
    
    return summary


# ==============================================================================
# VISUALIZATION EXPORT
# ==============================================================================

def export_chart_config(
    chart_data: Dict[str, Any],
    format: str = "plotly"
) -> Dict[str, Any]:
    """
    Export chart data in a format suitable for visualization libraries.
    
    Args:
        chart_data: Chart data dictionary
        format: Target format ('plotly', 'matplotlib', 'chartjs')
        
    Returns:
        Configuration dictionary for the target library
    """
    if format == "plotly":
        # Convert to Plotly format
        config = {
            "data": [],
            "layout": {
                "title": chart_data.get("title", ""),
                "xaxis": {"title": chart_data["x_axis"]["label"]},
                "yaxis": {"title": chart_data["y_axis"]["label"]}
            }
        }
        
        for series in chart_data.get("series", []):
            trace = {
                "x": chart_data["x_axis"]["values"],
                "y": series["data"],
                "name": series["name"],
                "type": "scatter" if series["type"] == "line" else series["type"],
                "mode": "lines+markers" if series["type"] == "line" else None
            }
            config["data"].append(trace)
        
        return config
    
    elif format == "json":
        # Return raw JSON format
        return chart_data
    
    else:
        logger.warning(f"Unsupported export format: {format}")
        return chart_data
