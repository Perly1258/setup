# API Reference

Complete API documentation for all computation engines and modules.

## PE Metrics Engine

Module: `engines.pe_metrics_engine`

### Functions

#### `calculate_xirr(cash_flows, dates, initial_guess=0.1, max_iterations=100, tolerance=1e-6)`

Calculate the Internal Rate of Return (IRR) for irregular cash flows.

**Parameters:**
- `cash_flows` (List[float]): Cash flow amounts (negative for investments, positive for returns)
- `dates` (List[datetime]): Dates corresponding to each cash flow
- `initial_guess` (float, optional): Initial guess for IRR. Default: 0.1
- `max_iterations` (int, optional): Maximum iterations. Default: 100
- `tolerance` (float, optional): Convergence tolerance. Default: 1e-6

**Returns:**
- `float | None`: IRR as decimal (e.g., 0.15 for 15%), or None if calculation fails

**Example:**
```python
from datetime import date
from engines.pe_metrics_engine import calculate_xirr

cash_flows = [-100000, 10000, 20000, 30000, 50000]
dates = [date(2020, 1, 1), date(2021, 1, 1), date(2022, 1, 1), 
         date(2023, 1, 1), date(2024, 1, 1)]
irr = calculate_xirr(cash_flows, dates)
print(f"IRR: {irr:.2%}")  # IRR: 5.12%
```

---

#### `calculate_tvpi(total_value, paid_in)`

Calculate Total Value to Paid-In (TVPI) multiple.

**Formula:** `TVPI = (Distributions + NAV) / Paid-In Capital`

**Parameters:**
- `total_value` (float): Sum of distributions and current NAV
- `paid_in` (float): Total capital paid in (contributions + fees)

**Returns:**
- `float | None`: TVPI multiple, or None if paid_in is zero

**Example:**
```python
tvpi = calculate_tvpi(total_value=150000, paid_in=100000)
print(f"TVPI: {tvpi:.2f}x")  # TVPI: 1.50x
```

---

#### `calculate_dpi(distributions, paid_in)`

Calculate Distributions to Paid-In (DPI) multiple.

**Formula:** `DPI = Total Distributions / Paid-In Capital`

**Parameters:**
- `distributions` (float): Total distributions to investors
- `paid_in` (float): Total capital paid in

**Returns:**
- `float | None`: DPI multiple, or None if paid_in is zero

---

#### `calculate_rvpi(nav, paid_in)`

Calculate Residual Value to Paid-In (RVPI) multiple.

**Formula:** `RVPI = Current NAV / Paid-In Capital`

**Parameters:**
- `nav` (float): Current Net Asset Value
- `paid_in` (float): Total capital paid in

**Returns:**
- `float | None`: RVPI multiple, or None if paid_in is zero

---

#### `calculate_moic(total_value, invested_capital)`

Calculate Multiple on Invested Capital (MoIC).

**Parameters:**
- `total_value` (float): Sum of distributions and current NAV
- `invested_capital` (float): Total invested capital

**Returns:**
- `float | None`: MoIC multiple, or None if invested_capital is zero

---

#### `calculate_called_percent(paid_in, commitment)`

Calculate percentage of committed capital that has been called.

**Formula:** `Called % = (Paid-In / Total Commitment) × 100`

**Parameters:**
- `paid_in` (float): Total capital paid in
- `commitment` (float): Total committed capital

**Returns:**
- `float | None`: Percentage called (0-100), or None if commitment is zero

---

#### `calculate_all_metrics(cash_flows, dates, total_commitment, current_nav)`

Calculate all PE metrics for a given investment.

**Parameters:**
- `cash_flows` (List[float]): Cash flows (negative for calls, positive for distributions)
- `dates` (List[datetime]): Corresponding dates
- `total_commitment` (float): Total committed capital
- `current_nav` (float): Current Net Asset Value

**Returns:**
- `Dict[str, Any]`: Dictionary containing all calculated metrics

**Example:**
```python
metrics = calculate_all_metrics(
    cash_flows=[-100000, 10000, 20000],
    dates=[date(2020, 1, 1), date(2021, 1, 1), date(2022, 1, 1)],
    total_commitment=150000,
    current_nav=50000
)
print(f"IRR: {metrics['irr']:.2%}")
print(f"TVPI: {metrics['tvpi']:.2f}x")
print(f"DPI: {metrics['dpi']:.2f}x")
```

---

#### `aggregate_metrics(fund_metrics_list)`

Aggregate metrics across multiple funds for portfolio/strategy level.

**Parameters:**
- `fund_metrics_list` (List[Dict[str, Any]]): List of metric dictionaries from individual funds

**Returns:**
- `Dict[str, Any]`: Aggregated metrics dictionary

---

## Cash Flow Engine

Module: `engines.cash_flow_engine`

### Classes

#### `CashFlow`

Represents a single cash flow transaction.

**Attributes:**
- `transaction_id` (int): Unique transaction identifier
- `fund_id` (int): Fund identifier
- `date` (datetime): Transaction date
- `cf_type` (str): Cash flow type
- `amount` (float): Amount (negative for calls, positive for distributions)

**Methods:**
- `is_call()`: Returns True if this is a capital call
- `is_distribution()`: Returns True if this is a distribution

**Example:**
```python
from engines.cash_flow_engine import CashFlow
from datetime import datetime

cf = CashFlow(
    transaction_id=1,
    fund_id=100,
    date=datetime(2020, 1, 1),
    cf_type='call_investment',
    amount=-50000
)
print(cf.is_call())  # True
```

---

#### `AggregationPeriod` (Enum)

Time period aggregation options.

**Values:**
- `QUARTERLY`: Aggregate by quarter
- `YEARLY`: Aggregate by year
- `MONTHLY`: Aggregate by month
- `ALL_TIME`: Single aggregation for all time

---

### Functions

#### `aggregate_by_period(cash_flows, period)`

Aggregate cash flows by time period.

**Parameters:**
- `cash_flows` (List[CashFlow]): List of CashFlow objects
- `period` (AggregationPeriod): Aggregation period

**Returns:**
- `Dict[str, float]`: Dictionary mapping period keys to total cash flow amounts

**Example:**
```python
from engines.cash_flow_engine import aggregate_by_period, AggregationPeriod

yearly_totals = aggregate_by_period(cash_flows, AggregationPeriod.YEARLY)
print(yearly_totals)  # {'2020': -50000, '2021': 30000, '2022': 80000}
```

---

#### `calculate_j_curve(cash_flows, period=AggregationPeriod.YEARLY)`

Calculate J-Curve data showing cumulative net cash flows over time.

**Parameters:**
- `cash_flows` (List[CashFlow]): List of CashFlow objects
- `period` (AggregationPeriod, optional): Time period for aggregation

**Returns:**
- `List[Dict[str, Any]]`: List of dictionaries with period, net_flow, and cumulative_flow

**Example:**
```python
j_curve = calculate_j_curve(cash_flows, AggregationPeriod.YEARLY)
# [{'period': '2020', 'net_flow': -100, 'cumulative_flow': -100},
#  {'period': '2021', 'net_flow': 20, 'cumulative_flow': -80}, ...]
```

---

#### `calculate_ytd_metrics(cash_flows, reference_date=None)`

Calculate year-to-date metrics.

**Parameters:**
- `cash_flows` (List[CashFlow]): List of CashFlow objects
- `reference_date` (datetime, optional): Reference date for YTD. Defaults to today

**Returns:**
- `Dict[str, Any]`: Dictionary with YTD calls, distributions, and net flow

---

#### `generate_cash_flow_summary(cash_flows, include_fees=True, period=AggregationPeriod.YEARLY)`

Generate a comprehensive summary of cash flows.

**Parameters:**
- `cash_flows` (List[CashFlow]): List of CashFlow objects
- `include_fees` (bool, optional): Include management fees. Default: True
- `period` (AggregationPeriod, optional): Aggregation period

**Returns:**
- `Dict[str, Any]`: Comprehensive cash flow analysis

---

## Projection Engine

Module: `engines.projection_engine`

### Functions

#### `project_cash_flows_takahashi(unfunded_commitment, current_nav, expected_moic, target_irr, strategy, num_periods, management_fee_rate=0.02, vintage_year=None)`

Project future cash flows using the Takahashi/Alexander model.

**Parameters:**
- `unfunded_commitment` (float): Remaining unfunded commitment
- `current_nav` (float): Current Net Asset Value
- `expected_moic` (float): Expected Multiple on Invested Capital
- `target_irr` (float): Target Internal Rate of Return (as decimal)
- `strategy` (str): Primary strategy name
- `num_periods` (int): Number of quarters to project
- `management_fee_rate` (float, optional): Annual management fee rate. Default: 0.02
- `vintage_year` (int, optional): Fund vintage year

**Returns:**
- `List[Dict[str, Any]]`: List of projected cash flow dictionaries by period

**Example:**
```python
projection = project_cash_flows_takahashi(
    unfunded_commitment=50000,
    current_nav=100000,
    expected_moic=2.5,
    target_irr=0.18,
    strategy="Venture Capital",
    num_periods=20
)
```

---

#### `calculate_optimal_allocation(current_exposures, target_exposures, available_capital, projected_distributions, constraints=None)`

Calculate optimal new investments to maintain target strategy exposures.

**Parameters:**
- `current_exposures` (Dict[str, float]): Current NAV by strategy
- `target_exposures` (Dict[str, float]): Target allocation percentages by strategy
- `available_capital` (float): Available capital for new investments
- `projected_distributions` (Dict[str, float]): Expected distributions by strategy
- `constraints` (Dict[str, Any], optional): Optional constraints

**Returns:**
- `Dict[str, float]`: Recommended allocations by strategy

**Example:**
```python
allocations = calculate_optimal_allocation(
    current_exposures={"VC": 1000, "PE": 2000, "RE": 1000},
    target_exposures={"VC": 0.30, "PE": 0.50, "RE": 0.20},
    available_capital=500,
    projected_distributions={"VC": 100, "PE": 200, "RE": 150}
)
```

---

## Visualization Engine

Module: `engines.visualization_engine`

### Functions

#### `prepare_j_curve_data(periods, cumulative_flows, discrete_flows=None)`

Prepare data for J-Curve visualization.

**Parameters:**
- `periods` (List[str]): List of period labels
- `cumulative_flows` (List[float]): Cumulative net cash flows
- `discrete_flows` (List[float], optional): Discrete cash flows per period

**Returns:**
- `Dict[str, Any]`: Chart data and metadata

---

#### `prepare_tvpi_evolution_data(periods, tvpi_values, dpi_values=None, rvpi_values=None)`

Prepare data for TVPI evolution chart.

**Parameters:**
- `periods` (List[str]): List of period labels
- `tvpi_values` (List[float]): TVPI values over time
- `dpi_values` (List[float], optional): DPI values over time
- `rvpi_values` (List[float], optional): RVPI values over time

**Returns:**
- `Dict[str, Any]`: Chart data and metadata

---

#### `format_currency(value, decimals=0)`

Format value as currency.

**Parameters:**
- `value` (float): Numeric value
- `decimals` (int, optional): Decimal places. Default: 0

**Returns:**
- `str`: Formatted currency string (e.g., "$1.5M", "$250K")

---

## Database Adapter

Module: `data.db_adapter`

### Classes

#### `DatabaseConnection`

Manages database connection lifecycle.

**Methods:**
- `__init__(config=None)`: Initialize connection
- `close()`: Close connection
- `execute_query(query, params=None, fetch='all')`: Execute SQL query

**Example:**
```python
from data.db_adapter import DatabaseConnection

db = DatabaseConnection()
results = db.execute_query("SELECT * FROM pe_portfolio WHERE fund_id = %s", (1,), fetch='one')
db.close()
```

---

### Functions

#### `get_fund_list(db, strategy=None, sub_strategy=None, is_active=True)`

Get list of funds with optional filtering.

**Parameters:**
- `db` (DatabaseConnection): Database connection
- `strategy` (str, optional): Filter by primary strategy
- `sub_strategy` (str, optional): Filter by sub-strategy
- `is_active` (bool, optional): Include only active funds. Default: True

**Returns:**
- `List[Dict[str, Any]]`: List of fund dictionaries

---

#### `calculate_fund_metrics(db, fund_id)`

Calculate all metrics for a specific fund.

**Parameters:**
- `db` (DatabaseConnection): Database connection
- `fund_id` (int): Fund ID

**Returns:**
- `Dict[str, Any] | None`: Dictionary with all calculated metrics

---

#### `calculate_strategy_metrics(db, strategy, sub_strategy=None)`

Calculate aggregated metrics for a strategy or sub-strategy.

**Parameters:**
- `db` (DatabaseConnection): Database connection
- `strategy` (str): Primary strategy name
- `sub_strategy` (str, optional): Sub-strategy name

**Returns:**
- `Dict[str, Any] | None`: Aggregated metrics dictionary

---

#### `calculate_portfolio_metrics(db)`

Calculate metrics for entire portfolio.

**Parameters:**
- `db` (DatabaseConnection): Database connection

**Returns:**
- `Dict[str, Any] | None`: Portfolio-level metrics

---

## Configuration

Module: `config`

### Constants

- `DB_CONFIG`: Database configuration dictionary
- `LLM_MODEL`: LLM model name
- `OLLAMA_HOST`: Ollama server URL
- `LLM_TEMPERATURE`: LLM temperature setting
- `IRR_MAX_ITERATIONS`: Maximum iterations for IRR calculation
- `IRR_TOLERANCE`: Convergence tolerance for IRR
- `DEFAULT_PROJECTION_QUARTERS`: Default projection horizon
- `HIERARCHY_LEVELS`: List of supported hierarchy levels
- `LOG_LEVEL`: Logging level
- `ENABLE_CACHING`: Enable/disable caching
- `CACHE_TTL_SECONDS`: Cache time-to-live

---

## Error Handling

All functions return `None` or raise exceptions on errors. Common exceptions:

- `ValueError`: Invalid input parameters
- `ZeroDivisionError`: Division by zero in calculations
- `psycopg2.Error`: Database errors
- `ConnectionError`: Database connection failures

Always wrap calls in try-except blocks for production use.
