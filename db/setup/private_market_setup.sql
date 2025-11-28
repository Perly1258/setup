-- =========================================================================
-- PART 1: INFRASTRUCTURE & DATA LOAD
-- Filename: private_market_setup.sql
-- Run this ONCE to build the database and load raw data.
-- =========================================================================

-- 1. DATABASE CLEANUP AND CREATION
DROP DATABASE IF EXISTS private_markets_db; 
CREATE DATABASE private_markets_db;
\c private_markets_db; 

-- 2. TABLE CREATION
-- A. PE_PORTFOLIO
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

-- B. PE_HISTORICAL_CASH_FLOWS
CREATE TABLE pe_historical_cash_flows (
    transaction_id SERIAL PRIMARY KEY, 
    fund_id INTEGER NOT NULL REFERENCES pe_portfolio(fund_id),
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

-- C. PE_MODELING_RULES
CREATE TABLE pe_modeling_rules (
    primary_strategy VARCHAR(50) PRIMARY KEY, 
    expected_moic_gross_multiple NUMERIC(4, 2) NOT NULL,
    target_irr_net_percentage NUMERIC(4, 2) NOT NULL,    
    investment_period_years INTEGER NOT NULL,  
    fund_life_years INTEGER NOT NULL,          
    nav_initial_qtr_depreciation NUMERIC(5, 4) NOT NULL,
    nav_initial_depreciation_qtrs INTEGER NOT NULL,
    j_curve_model_description VARCHAR(50) NOT NULL,     
    modeling_rationale TEXT 
);

-- D. PE_FORECAST_CASH_FLOWS
CREATE TABLE pe_forecast_cash_flows (
    projection_id SERIAL PRIMARY KEY,
    fund_id INTEGER NOT NULL REFERENCES pe_portfolio(fund_id),
    projection_date DATE NOT NULL,
    scenario_id VARCHAR(50) NOT NULL, 
    transaction_type VARCHAR(30) NOT NULL, 
    projected_amount_usd NUMERIC(15, 4),        
    projected_nav_usd NUMERIC(15, 4)            
);

-- E. SCHEMA_ANNOTATIONS (Structure Only)
CREATE TABLE schema_annotations (
    table_name VARCHAR(50) NOT NULL,
    column_name VARCHAR(50) NOT NULL,
    natural_language_description TEXT NOT NULL, 
    PRIMARY KEY (table_name, column_name)
);

-- 3. DATA LOADING (Raw CSVs)
COPY pe_portfolio (fund_id, fund_name, vintage_year, primary_strategy, sub_strategy, total_commitment_usd, comment)
FROM '/workspace/setup/data/PE_Portfolio.csv' DELIMITER ',' CSV HEADER;

COPY pe_historical_cash_flows (fund_id, transaction_date, reporting_quarter, transaction_type, investment_paid_in_usd, management_fees_usd, return_of_cost_distribution_usd, profit_distribution_usd, net_asset_value_usd, moic_multiple)
FROM '/workspace/setup/data/Fund_Cash_Flows.csv' DELIMITER ',' CSV HEADER;

COPY pe_modeling_rules (primary_strategy, expected_moic_gross_multiple, target_irr_net_percentage, investment_period_years, fund_life_years, nav_initial_qtr_depreciation, nav_initial_depreciation_qtrs, j_curve_model_description, modeling_rationale)
FROM '/workspace/setup/data/fund_model_assumptions_data.csv' DELIMITER ',' CSV HEADER;