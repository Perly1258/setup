# PE Portfolio Analysis System

A **Computation-First Hybrid Architecture** for Private Equity portfolio analysis that combines precise Python calculations with LLM-powered natural language understanding.

## 🎯 Overview

This system solves the precision and maintainability problems of pure LLM-based PE analysis by:
- Using **pure Python** for all financial calculations (IRR, TVPI, DPI, projections)
- Leveraging **LLM** only for query understanding and response formatting
- Providing **deterministic, testable** metric computations
- Supporting **4-level hierarchy** analysis (Portfolio → Strategy → Sub-Strategy → Fund)

## ✨ Features

### Core Capabilities
- ✅ **Precise PE Metrics**: IRR (XIRR), TVPI, DPI, RVPI, MoIC, Called %, Distributed %
- ✅ **Flexible Cash Flow Analysis**: Net, cumulative, by period, YTD, with/without fees
- ✅ **4-Level Hierarchy Support**: Portfolio, Strategy, Sub-Strategy, Fund
- ✅ **J-Curve Analysis**: Cumulative net cash flows over time
- ✅ **TVPI Evolution**: Performance tracking across periods
- ✅ **Future Projections**: Takahashi/Alexander model for cash flow forecasting
- ✅ **Allocation Optimizer**: Optimal investments to maintain target exposures

### Technical Advantages
- ✅ **Testable**: 33 unit tests for all computations
- ✅ **Debuggable**: Pure Python, no complex stored procedures
- ✅ **Maintainable**: Modular design with clear separation of concerns
- ✅ **Extensible**: Easy to add new metrics and capabilities
- ✅ **Documented**: Complete architecture and API documentation

## 🏗️ Architecture

```
User Query → LLM Agent → Computation Engines → Database
              (routing)   (precise math)      (caching)
```

### Components

1. **Computation Engines** (`src/engines/`)
   - `pe_metrics_engine.py` - Financial metrics calculations
   - `cash_flow_engine.py` - Cash flow processing and analysis
   - `projection_engine.py` - Future cash flow forecasting
   - `visualization_engine.py` - Chart data preparation

2. **Data Layer** (`src/data/`)
   - `db_adapter.py` - Database interface and metric calculation

3. **Agent Layer** (`src/`)
   - `pe_agent_refactored.py` - LLM agent with computation tools
   - `config.py` - Centralized configuration

4. **Tests** (`tests/`)
   - `test_pe_metrics_engine.py` - 17 tests for metrics
   - `test_cash_flow_engine.py` - 16 tests for cash flows

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- PostgreSQL with PE portfolio data
- Ollama with DeepSeek R1 model (or compatible LLM)

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/Perly1258/setup.git
cd setup
```

2. **Install dependencies**
```bash
pip install psycopg2-binary langchain langchain-ollama
```

3. **Configure environment**
```bash
export DB_NAME="private_markets_db"
export DB_USER="postgres"
export DB_PASSWORD="postgres"
export DB_HOST="localhost"
export OLLAMA_HOST="http://localhost:21434"
export LLM_MODEL="deepseek-r1:32b"
```

4. **Run the agent**
```bash
python src/pe_agent_refactored.py
```

## 💡 Usage Examples

### Command Line Agent

```python
from src.pe_agent_refactored import setup_agent

agent = setup_agent()

# Ask questions in natural language
response = agent.invoke({
    "input": "What is the TVPI and DPI of the entire portfolio?"
})
print(response['output'])
```

### Direct API Usage

```python
from src.data.db_adapter import DatabaseConnection, calculate_portfolio_metrics

# Connect to database
db = DatabaseConnection()

# Calculate portfolio metrics
metrics = calculate_portfolio_metrics(db)
print(f"Portfolio TVPI: {metrics['tvpi']:.2f}x")
print(f"Portfolio DPI: {metrics['dpi']:.2f}x")

db.close()
```

### Computation Engine Usage

```python
from datetime import date
from src.engines.pe_metrics_engine import calculate_all_metrics

# Calculate metrics for specific cash flows
metrics = calculate_all_metrics(
    cash_flows=[-100000, -20000, 30000, 40000],
    dates=[date(2020, 1, 1), date(2020, 6, 1), 
           date(2021, 1, 1), date(2022, 1, 1)],
    total_commitment=150000,
    current_nav=60000
)

print(f"IRR: {metrics['irr']:.2%}")
print(f"TVPI: {metrics['tvpi']:.2f}x")
print(f"Called: {metrics['called_percent']:.1f}%")
```

### Cash Flow Analysis

```python
from src.engines.cash_flow_engine import (
    CashFlow, calculate_j_curve, AggregationPeriod
)
from datetime import datetime

# Create cash flows
cash_flows = [
    CashFlow(1, 100, datetime(2020, 1, 1), 'call', -100000),
    CashFlow(2, 100, datetime(2021, 1, 1), 'dist', 30000),
    CashFlow(3, 100, datetime(2022, 1, 1), 'dist', 80000)
]

# Calculate J-Curve
j_curve = calculate_j_curve(cash_flows, AggregationPeriod.YEARLY)
for point in j_curve:
    print(f"{point['period']}: Cumulative={point['cumulative_flow']}")
```

### Future Projections

```python
from src.engines.projection_engine import project_cash_flows_takahashi

# Project 5 years of cash flows
projection = project_cash_flows_takahashi(
    unfunded_commitment=50000,
    current_nav=100000,
    expected_moic=2.5,
    target_irr=0.18,
    strategy="Venture Capital",
    num_periods=20  # 5 years × 4 quarters
)

# Analyze projection
total_calls = sum([abs(p['call_investment']) for p in projection])
total_distributions = sum([p['distribution'] for p in projection])
print(f"Projected calls: ${total_calls:,.0f}")
print(f"Projected distributions: ${total_distributions:,.0f}")
```

## 🧪 Testing

Run unit tests:

```bash
# Test PE metrics engine
python -m unittest tests.test_pe_metrics_engine -v

# Test cash flow engine
python -m unittest tests.test_cash_flow_engine -v

# Run all tests
python -m unittest discover tests -v
```

All 33 tests should pass:
- ✅ 17 tests for PE metrics calculations
- ✅ 16 tests for cash flow processing

## 📊 Supported Queries

The LLM agent can answer questions like:

- "What is the TVPI and DPI of the entire portfolio?"
- "Which strategy has the highest IRR?"
- "Show me the J-Curve for Venture Capital"
- "What is the total Paid-In for Private Equity funds?"
- "Which fund has distributed the most capital?"
- "Run a 5-year forecast for Real Estate"
- "Why is the Venture Capital J-Curve so deep?"
- "What are the top 5 funds by TVPI?"

## 📚 Documentation

- **[Architecture Guide](docs/architecture.md)** - System design and data flow
- **[API Reference](docs/api_reference.md)** - Complete API documentation
- **Database Schema** - See `db/setup/README.md`

## 🔧 Configuration

Edit `src/config.py` or use environment variables:

```python
# Database
DB_CONFIG = {
    "dbname": "private_markets_db",
    "user": "postgres",
    "password": "postgres",
    "host": "localhost",
    "port": "5432"
}

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

## 🛠️ Development

### Adding a New Metric

1. Add calculation function to `src/engines/pe_metrics_engine.py`
2. Write unit tests in `tests/test_pe_metrics_engine.py`
3. Update `calculate_all_metrics()` to include the new metric
4. Document in API reference

### Adding a New Tool

1. Create `@tool` function in `src/pe_agent_refactored.py`
2. Call appropriate computation engine
3. Format results as JSON
4. Add to tools list in `setup_agent()`

## 📈 Performance

- **IRR calculation**: < 1ms per fund
- **Portfolio aggregation**: < 100ms for 50+ funds
- **J-Curve analysis**: < 50ms per strategy
- **5-year projection**: < 200ms per strategy

## 🔒 Security

- ✅ Database credentials via environment variables
- ✅ Parameterized queries (no SQL injection)
- ✅ Input validation on all tools
- ✅ No secrets in logs
- ✅ Type hints for safety

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## 📝 License

[Your License Here]

## 🙏 Acknowledgments

- **Takahashi/Alexander Model**: Industry-standard PE projection methodology
- **LangChain**: Agent framework
- **DeepSeek R1**: LLM for query understanding

## 📞 Support

For questions or issues:
- Open an issue on GitHub
- Check documentation in `docs/`
- Review test files for usage examples

---

**Built with ❤️ for precise and maintainable PE portfolio analysis**
