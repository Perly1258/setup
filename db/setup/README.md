# Database Setup SQL Files

This directory contains SQL setup scripts for the Private Equity database system.

## Files Overview

### 1. `private_market_setup.sql`
**Purpose**: Initial database schema creation and data loading  
**Execution Order**: FIRST  
**Description**: 
- Creates core tables: `pe_portfolio`, `pe_historical_cash_flows`, `pe_modeling_rules`, `pe_forecast_cash_flows`, `schema_annotations`
- Loads initial data from CSV files in `/data` directory
- Must be run before any other SQL files

**Tables Created**:
- `pe_portfolio` - Fund positions master table
- `pe_historical_cash_flows` - Historical cash flow transactions
- `pe_modeling_rules` - Strategy-specific modeling parameters
- `pe_forecast_cash_flows` - Projected future cash flows
- `schema_annotations` - Natural language descriptions for RAG

### 2. `rag_annotations.sql`
**Purpose**: Load semantic annotations for database schema  
**Execution Order**: SECOND  
**Description**:
- Populates `schema_annotations` table with natural language descriptions
- Enables AI/RAG systems to understand database structure
- Provides context for column meanings and calculations

### 3. `pe_logic_python.sql`
**Purpose**: Core business logic functions using PL/Python  
**Execution Order**: THIRD  
**Description**:
- Enables PL/Python extension
- Creates analytical views: `view_pe_hierarchy_metrics`, `view_yearly_cash_flows`, `view_j_curve_cumulative`
- Implements `fn_get_pe_metrics_py()` function for metrics calculation (IRR, DPI, TVPI)

**Prerequisites**: PostgreSQL with `plpython3u` extension installed

### 4. `pe_forecast_logic.sql`
**Purpose**: Forecasting engine using Takahashi-Alexander Model  
**Execution Order**: FOURTH  
**Description**:
- Creates/updates `pe_modeling_rules` table with strategy parameters
- Creates `pe_forecast_output` table for simulation results
- Implements `fn_run_takahashi_forecast()` function for cash flow projection

**Prerequisites**: PostgreSQL with `plpython3u` extension and `dateutil` Python package

### 5. `test_queries.sql`
**Purpose**: Comprehensive test suite for all functions and views  
**Execution Order**: LAST (for testing)  
**Description**:
- Contains 50+ test queries
- Validates all functions and views
- Tests multiple strategies and fund levels

## Execution Order

The correct execution order is:
```bash
psql -d private_markets_db -f private_market_setup.sql
psql -d private_markets_db -f rag_annotations.sql
psql -d private_markets_db -f pe_logic_python.sql
psql -d private_markets_db -f pe_forecast_logic.sql
# Optional: Test everything
psql -d private_markets_db -f test_queries.sql
```

## Automated Setup

The `setup_ml_only.sh` script in the root directory automates the entire setup process:
- Creates PostgreSQL database
- Executes SQL files in correct order
- Installs required Python packages
- Configures the environment

## Schema Consistency

All SQL files use consistent column naming for `pe_modeling_rules` table:
- `expected_moic_gross_multiple` (NUMERIC(4,2))
- `target_irr_net_percentage` (NUMERIC(4,2))
- `investment_period_years` (INTEGER)
- `fund_life_years` (INTEGER)
- `nav_initial_qtr_depreciation` (NUMERIC(5,4))
- `nav_initial_depreciation_qtrs` (INTEGER)
- `j_curve_model_description` (VARCHAR(50))
- `modeling_rationale` (TEXT)

## Data Files Required

The following CSV files must exist in `/data` directory:
- `PE_Portfolio.csv` - Fund portfolio data
- `Fund_Cash_Flows.csv` - Historical cash flow transactions
- `fund_model_assumptions_data.csv` - Strategy modeling parameters

## Troubleshooting

### Database Already Exists Error
The `private_market_setup.sql` file assumes the database is created externally. If running standalone, uncomment the database creation commands at the top of the file.

### PL/Python Extension Error
Ensure `postgresql-plpython3-16` (or appropriate version) is installed:
```bash
sudo apt-get install postgresql-plpython3-16
```

### Column Not Found Error
This indicates a schema version mismatch. Drop all tables and re-run setup scripts in order.

## Validation

Use the provided validation script to check SQL syntax:
```bash
bash validate_sql.sh
```
