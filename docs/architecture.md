# PE Portfolio Analysis System - Architecture Documentation

## Overview

This system implements a **Computation-First Hybrid Architecture** for Private Equity portfolio analysis. The key principle is to use pure Python computation modules for all financial calculations, while leveraging the LLM exclusively for natural language understanding, query routing, and result formatting.

## Architecture Diagram

```
┌─────────────┐
│ User Query  │
└──────┬──────┘
       │
       ▼
┌──────────────────────────────────────┐
│   LLM Agent (DeepSeek R1)            │
│   - Query parsing                     │
│   - Intent routing                    │
│   - Result formatting                 │
└──────┬───────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────┐
│   Computation Layer (Pure Python)    │
│   ┌────────────────────────────────┐ │
│   │  PE Metrics Engine             │ │
│   │  - IRR, TVPI, DPI, MoIC        │ │
│   │  - Called %, Distribution %    │ │
│   └────────────────────────────────┘ │
│   ┌────────────────────────────────┐ │
│   │  Cash Flow Engine              │ │
│   │  - Aggregation & filtering     │ │
│   │  - J-Curve analysis            │ │
│   │  - YTD calculations            │ │
│   └────────────────────────────────┘ │
│   ┌────────────────────────────────┐ │
│   │  Projection Engine             │ │
│   │  - Takahashi/Alexander model   │ │
│   │  - Allocation optimizer        │ │
│   └────────────────────────────────┘ │
│   ┌────────────────────────────────┐ │
│   │  Visualization Engine          │ │
│   │  - Chart data preparation      │ │
│   └────────────────────────────────┘ │
└──────┬───────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────┐
│   Database Layer (PostgreSQL)        │
│   - Raw transaction data             │
│   - Cached computed metrics          │
│   - Modeling assumptions             │
└──────────────────────────────────────┘
```

## Design Principles

### 1. Separation of Concerns

- **LLM Layer**: Only handles natural language tasks
  - Understanding user queries
  - Routing to appropriate computation functions
  - Formatting results for human consumption
  
- **Computation Layer**: All financial calculations
  - Deterministic, testable pure functions
  - No LLM involvement in calculations
  - Independent of database implementation
  
- **Data Layer**: Data persistence and retrieval
  - Database queries
  - Result caching
  - Data transformation

### 2. Testability

All computation modules are:
- Pure Python functions
- Unit testable
- Independent of external services
- Deterministic (same inputs → same outputs)

### 3. Debuggability

- Clear separation between layers
- Comprehensive logging at each layer
- No complex PL/Python stored procedures
- Standard Python debugging tools work

### 4. Maintainability

- Modular design with clear interfaces
- Type hints throughout
- Comprehensive docstrings
- Easy to extend with new metrics

## Module Descriptions

### Core Computation Modules

#### `engines/pe_metrics_engine.py`

Calculates all PE metrics:
- **IRR**: Internal Rate of Return using Newton-Raphson method
- **TVPI**: Total Value to Paid-In multiple
- **DPI**: Distributions to Paid-In multiple
- **RVPI**: Residual Value to Paid-In multiple
- **MoIC**: Multiple on Invested Capital
- **Called %**: Percentage of commitment called
- **Distributed %**: Percentage of commitment distributed

All calculations use standard financial formulas with no approximations.

#### `engines/cash_flow_engine.py`

Handles cash flow processing:
- Aggregation by time period (quarterly, yearly, all-time)
- Cumulative cash flow calculations
- Separation of calls and distributions
- Date range filtering
- J-Curve analysis
- YTD metrics

#### `engines/projection_engine.py`

Future cash flow forecasting:
- **Takahashi/Alexander Model**: Industry-standard PE projection model
- **Strategy-specific curves**: Different S-curves and J-curves per strategy
- **NAV evolution**: Models initial depreciation and long-term appreciation
- **Allocation optimizer**: Calculates optimal new investments to maintain target exposures

#### `engines/visualization_engine.py`

Chart data preparation:
- J-Curve charts (cumulative net cash flows)
- TVPI evolution over time
- Allocation comparison charts
- Waterfall charts
- Heatmaps
- Chart summaries for LLM responses

### Data Layer

#### `data/db_adapter.py`

Database interface:
- Connection management
- Query execution
- Data retrieval functions
- Metric calculation with database
- Results caching

### Agent Layer

#### `pe_agent_refactored.py`

LLM agent implementation:
- LangChain integration
- Tool definitions for each capability
- Query routing logic
- Response formatting
- Error handling

## Data Flow

### Example: "What is the TVPI of the Venture Capital strategy?"

1. **User Query** → Agent receives natural language question

2. **LLM Processing**:
   - Parses query
   - Identifies: metric="TVPI", level="STRATEGY", name="Venture Capital"
   - Routes to `get_strategy_metrics` tool

3. **Tool Execution**:
   ```python
   get_strategy_metrics("Venture Capital")
   ```

4. **Database Query** (via `db_adapter.py`):
   - Retrieves all funds in Venture Capital strategy
   - Retrieves cash flows for each fund

5. **Computation** (via `pe_metrics_engine.py`):
   - Calculates metrics for each fund
   - Aggregates to strategy level
   - Returns: `{"tvpi": 1.85, "dpi": 0.45, ...}`

6. **Response Formatting**:
   - LLM formats JSON into natural language
   - "The Venture Capital strategy has a TVPI of 1.85x..."

7. **User receives answer**

## 4-Level Hierarchy Support

The system supports analysis at four levels:

1. **Portfolio**: Entire PE portfolio aggregated
2. **Strategy**: Primary strategy (e.g., Venture Capital, Private Equity)
3. **Sub-Strategy**: Secondary classification (e.g., Growth Equity, Buyout)
4. **Fund**: Individual fund level

Each level can be queried independently, with automatic aggregation from the fund level up.

## Caching Strategy

To optimize performance:
- Computed metrics are cached in the database
- Cache invalidation on new transactions
- TTL-based cache expiration (default: 1 hour)
- Can be disabled for real-time calculations

## Error Handling

The system implements comprehensive error handling:
- Database connection failures
- Missing data
- Invalid calculations (divide by zero, etc.)
- LLM parsing errors
- Network timeouts

All errors are:
- Logged with context
- Returned as JSON with error messages
- Handled gracefully without system crashes

## Testing Strategy

### Unit Tests
- All computation functions have unit tests
- Test edge cases (zero values, negative flows, etc.)
- Test mathematical accuracy
- No database dependencies

### Integration Tests
- Test database adapter functions
- Test end-to-end agent workflows
- Test with sample data

### Performance Tests
- Benchmark calculation times
- Test caching effectiveness
- Test large portfolio handling

## Configuration

All configuration is centralized in `config.py`:

```python
# Database
DB_CONFIG = {...}

# LLM
LLM_MODEL = "deepseek-r1:32b"
LLM_TEMPERATURE = 0

# Computation
IRR_MAX_ITERATIONS = 100
IRR_TOLERANCE = 1e-6

# Caching
ENABLE_CACHING = True
CACHE_TTL_SECONDS = 3600
```

## Extending the System

### Adding a New Metric

1. Add calculation function to `engines/pe_metrics_engine.py`
2. Add unit tests to `tests/test_pe_metrics_engine.py`
3. Update `calculate_all_metrics()` to include new metric
4. Update documentation

### Adding a New Tool

1. Create tool function in `pe_agent_refactored.py` with `@tool` decorator
2. Call appropriate computation engine functions
3. Format results as JSON
4. Add to tools list in `setup_agent()`
5. Test with sample queries

### Adding a New Projection Model

1. Implement model in `engines/projection_engine.py`
2. Add to `ProjectionModel` enum
3. Create unit tests
4. Update agent tool to support new model

## Performance Considerations

- **Database queries**: Optimized with indexes
- **Caching**: Reduces redundant calculations
- **Lazy loading**: Only compute what's requested
- **Batch operations**: Aggregate queries where possible
- **Connection pooling**: Reuse database connections

## Security Considerations

- Database credentials via environment variables
- Input validation on all tool parameters
- SQL injection prevention with parameterized queries
- No user input directly in SQL
- Logging sanitization (no secrets in logs)

## Monitoring and Logging

All components log:
- Info: Successful operations
- Warning: Degraded performance, missing data
- Error: Failures with stack traces
- Debug: Detailed calculation steps

Logs include:
- Timestamps
- Component name
- Log level
- Message with context

## Future Enhancements

1. **Real-time updates**: WebSocket support for live data
2. **More projection models**: Yale Model, Cambridge Associates
3. **Advanced visualizations**: Interactive charts
4. **Multi-currency support**: Handle non-USD investments
5. **Benchmark comparisons**: Compare to industry benchmarks
6. **What-if analysis**: Scenario modeling
7. **API endpoints**: REST API for integration
8. **Dashboard**: Web UI for portfolio monitoring
