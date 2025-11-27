-- =========================================================================
-- DATABASE SETUP SCRIPT: PRIVATE MARKETS PORTFOLIO AND CASH FLOWS
-- TARGET DATABASE: PostgreSQL 
-- NOTE: Final version optimized for LLM RAG clarity.
-- Changes include: DROP DATABASE, snake_case, explicit column names (e.g., distribution), 
-- and unit context moved to SCHEMA_ANNOTATIONS (all USD values are in single dollars, NOT millions).
-- =========================================================================

-- 1. DATABASE CLEANUP AND CREATION
-------------------------------------------------------------------------
-- IMPORTANT: Drops the entire database to ensure a clean slate.
DROP DATABASE IF EXISTS private_markets_db; 

CREATE DATABASE private_markets_db;
\c private_markets_db; 
-- \c connects to the newly created database

-- -------------------------------------------------------------------------
-- 2. SCHEMA CLEANUP (DROP IF EXISTS) 
-- -------------------------------------------------------------------------

DROP TABLE IF EXISTS "pe_forecast_cash_flows"; 
DROP TABLE IF EXISTS "pe_historical_cash_flows"; 
DROP TABLE IF EXISTS "pe_modeling_rules";
DROP TABLE IF EXISTS "pe_portfolio" CASCADE; 
DROP TABLE IF EXISTS "schema_annotations"; 

-- -------------------------------------------------------------------------
-- 3. TABLE CREATION (SCHEMAS)
-- -------------------------------------------------------------------------

-- A. PE_PORTFOLIO Table (Static Fund Metadata)
CREATE TABLE pe_portfolio (
    fund_id INTEGER PRIMARY KEY,
    fund_name VARCHAR(255) NOT NULL,
    vintage_year INTEGER NOT NULL,
    primary_strategy VARCHAR(50) NOT NULL,
    sub_strategy VARCHAR(50),
    total_commitment_usd NUMERIC(10, 2) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    comment TEXT
);

-- B. PE_HISTORICAL_CASH_FLOWS Table (Past Transaction Data)
CREATE TABLE pe_historical_cash_flows (
    transaction_id SERIAL PRIMARY KEY, 
    fund_id INTEGER NOT NULL REFERENCES pe_portfolio(fund_id), -- FK
    transaction_date DATE NOT NULL,
    reporting_quarter VARCHAR(5) NOT NULL,
    transaction_type VARCHAR(20) NOT NULL, 
    investment_paid_in_usd NUMERIC(15, 4),               
    management_fees_usd NUMERIC(15, 4),                  
    return_of_cost_distribution_usd NUMERIC(15, 4),      
    profit_distribution_usd NUMERIC(15, 4),              
    net_asset_value_usd NUMERIC(20, 2),                 
    moic_multiple NUMERIC(5, 2)                         
);

-- C. PE_MODELING_RULES Table (Quantitative Inputs for Projection)
CREATE TABLE pe_modeling_rules (
    primary_strategy VARCHAR(50) PRIMARY KEY, -- Links to pe_portfolio
    expected_moic_gross_multiple NUMERIC(4, 2) NOT NULL,
    target_irr_net_percentage NUMERIC(4, 2) NOT NULL,    
    investment_period_years INTEGER NOT NULL,  
    fund_life_years INTEGER NOT NULL,          
    nav_initial_qtr_depreciation NUMERIC(5, 4) NOT NULL,
    nav_initial_depreciation_qtrs INTEGER NOT NULL,
    j_curve_model_description VARCHAR(50) NOT NULL,     
    modeling_rationale TEXT 
);

-- D. PE_FORECAST_CASH_FLOWS Table (Future Projection Data)
CREATE TABLE pe_forecast_cash_flows (
    projection_id SERIAL PRIMARY KEY,
    fund_id INTEGER NOT NULL REFERENCES pe_portfolio(fund_id), -- FK
    projection_date DATE NOT NULL,
    scenario_id VARCHAR(50) NOT NULL, 
    transaction_type VARCHAR(30) NOT NULL, 
    projected_amount_usd NUMERIC(15, 4),        
    projected_nav_usd NUMERIC(15, 4)            
);


-- E. SCHEMA_ANNOTATIONS Table (LLM Context/RAG Metadata)
CREATE TABLE schema_annotations (
    table_name VARCHAR(50) NOT NULL,
    column_name VARCHAR(50) NOT NULL,
    natural_language_description TEXT NOT NULL, 
    PRIMARY KEY (table_name, column_name)
);

-- -------------------------------------------------------------------------
-- 4. LLM CONTEXT DATA LOADING (Annotations) - UPDATED
-- Currency fields are now annotated as being in "US dollars".
-- -------------------------------------------------------------------------

INSERT INTO schema_annotations (table_name, column_name, natural_language_description) VALUES 
('pe_portfolio', 'fund_id', 'The unique identifier for each Private Equity fund. Use this column to JOIN tables.'),
('pe_portfolio', 'total_commitment_usd', 'The maximum capital committed by the investor to the PE fund, denominated in **US dollars**.'),
('pe_historical_cash_flows', 'investment_paid_in_usd', 'Represents capital called by the Fund Manager from the investor (LP). This is a cash **outflow** for the investor. Value is in **US dollars**.'),
('pe_historical_cash_flows', 'management_fees_usd', 'Represents management fees paid to the Fund Manager. This is a cash **outflow** for the investor. Value is in **US dollars**.'),
('pe_historical_cash_flows', 'return_of_cost_distribution_usd', 'Represents capital distributed back to the investor (LP), specifically the **return of cost** portion. This is a cash **inflow**. Value is in **US dollars**.'),
('pe_historical_cash_flows', 'profit_distribution_usd', 'Represents capital distributed back to the investor (LP), specifically the **profit** portion. This is a cash **inflow**. Value is in **US dollars**.'),
('pe_historical_cash_flows', 'moic_multiple', 'The **Multiple of Invested Capital (MOIC)**. This is a ratio (a performance multiple), not a currency amount. Calculated as Total Value / Paid-In Capital. Used for fund performance.'),
('pe_historical_cash_flows', 'net_asset_value_usd', 'The market value of the investment at the end of a reporting period, denominated in US dollars. Used to calculate performance metrics. Value is in **US dollars**.');


-- -------------------------------------------------------------------------
-- 5. DATA LOADING (Using ABSOLUTE Path)
-- -------------------------------------------------------------------------
-- NOTE: Update these file paths if they differ in your environment.

-- Load Portfolio Data - Column list updated
COPY pe_portfolio (fund_id, fund_name, vintage_year, primary_strategy, sub_strategy, total_commitment_usd, comment)
FROM '/workspace/setup/data/PE_Portfolio.csv'
DELIMITER ','
CSV HEADER;


-- Load Historical Cash Flow Data - Column list updated
COPY pe_historical_cash_flows (fund_id, transaction_date, reporting_quarter, transaction_type, investment_paid_in_usd, management_fees_usd, return_of_cost_distribution_usd, profit_distribution_usd, net_asset_value_usd, moic_multiple)
FROM '/workspace/setup/data/Fund_Cash_Flows.csv'
DELIMITER ','
CSV HEADER;


-- Load Model Assumptions Data
COPY pe_modeling_rules (primary_strategy, expected_moic_gross_multiple, target_irr_net_percentage, investment_period_years, fund_life_years, nav_initial_qtr_depreciation, nav_initial_depreciation_qtrs, j_curve_model_description, modeling_rationale)
FROM '/workspace/setup/data/fund_model_assumptions_data.csv'
DELIMITER ','
CSV HEADER;