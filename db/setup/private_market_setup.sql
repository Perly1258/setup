-- =========================================================================
-- DATABASE SETUP SCRIPT: PRIVATE MARKETS PORTFOLIO AND CASH FLOWS
-- TARGET DATABASE: PostgreSQL 
-- USER: postgres | INITIAL DB: postgres
-- This script creates the database, schema, and loads data from CSVs 
-- located in the absolute path: /workspace/setup/data/
-- =========================================================================

-- 1. DATABASE CREATION AND CONNECTION
-- Creates the target database (must be run from 'postgres' database)
CREATE DATABASE private_markets_db;

-- Connects to the newly created database (psql meta-command)
\c private_markets_db; 

-- -------------------------------------------------------------------------
-- 2. TABLE CREATION (SCHEMAS)
-- -------------------------------------------------------------------------

-- A. PE_Portfolio Table (Static Fund Metadata)
CREATE TABLE PE_Portfolio (
    Fund_ID INTEGER PRIMARY KEY, -- Primary key for linking
    Fund_Name VARCHAR(255) NOT NULL,
    Vintage_Year INTEGER NOT NULL,
    Primary_Strategy VARCHAR(50) NOT NULL,
    Sub_Strategy VARCHAR(50),
    Total_Commitment_MM_USD NUMERIC(10, 2) NOT NULL,
    Comment TEXT
);

-- B. Fund_Cash_Flows Table (Historical Transaction Data)
CREATE TABLE Fund_Cash_Flows (
    Transaction_ID SERIAL PRIMARY KEY, 
    Fund_ID INTEGER NOT NULL,
    Transaction_Date DATE NOT NULL,
    Reporting_Quarter VARCHAR(5) NOT NULL,
    Transaction_Type VARCHAR(20) NOT NULL, 
    Investment_MM_USD NUMERIC(15, 4), 
    Fees_MM_USD NUMERIC(15, 4),        
    Return_of_Cost_MM_USD NUMERIC(15, 4), 
    Profit_MM_USD NUMERIC(15, 4),      
    Quarterly_NAV_USD NUMERIC(20, 2),  
    MOIC NUMERIC(5, 2),
    
    FOREIGN KEY (Fund_ID) REFERENCES PE_Portfolio(Fund_ID)
);

-- C. FUND_MODEL_ASSUMPTIONS Table (Quantitative Inputs for Projection)
CREATE TABLE FUND_MODEL_ASSUMPTIONS (
    Primary_Strategy VARCHAR(50) PRIMARY KEY,
    Expected_MOIC_Gross NUMERIC(4, 2) NOT NULL, 
    Target_IRR_Net NUMERIC(4, 2) NOT NULL,     
    Investment_Period_Years INTEGER NOT NULL,  
    Fund_Life_Years INTEGER NOT NULL,          
    NAV_Initial_Qtr_Depreciation NUMERIC(5, 4) NOT NULL, -- Numeric J-Curve parameter
    NAV_Initial_Depreciation_Qtrs INTEGER NOT NULL,
    J_Curve_Description VARCHAR(50) NOT NULL, 
    Modeling_Rationale TEXT 
);

-- D. PROJECTED_CASH_FLOWS Table (Output from Python Engine - REQUIRED by RAG)
CREATE TABLE PROJECTED_CASH_FLOWS (
    Projection_ID SERIAL PRIMARY KEY,
    Fund_ID INTEGER NOT NULL REFERENCES PE_Portfolio(Fund_ID),
    Projection_Date DATE NOT NULL,
    Scenario_ID VARCHAR(50) NOT NULL, -- e.g., 'Baseline_5Y_Forecast'
    Transaction_Type VARCHAR(30) NOT NULL, -- Call, Distribution, NAV
    Projected_Amount_MM_USD NUMERIC(15, 4),
    Projected_NAV_MM_USD NUMERIC(15, 4)
);


-- -------------------------------------------------------------------------
-- 3. DATA LOADING (Using ABSOLUTE Path)
-- Assumes /workspace/setup is the project root on the remote server
-- -------------------------------------------------------------------------

-- Load Portfolio Data
COPY PE_Portfolio (Fund_ID, Fund_Name, Vintage_Year, Primary_Strategy, Sub_Strategy, Total_Commitment_MM_USD, Comment)
FROM '/workspace/setup/data/PE_Portfolio.csv'
DELIMITER ','
CSV HEADER;


-- Load Cash Flow Data
COPY Fund_Cash_Flows (Fund_ID, Transaction_Date, Reporting_Quarter, Transaction_Type, Investment_MM_USD, Fees_MM_USD, Return_of_Cost_MM_USD, Profit_MM_USD, Quarterly_NAV_USD, MOIC)
FROM '/workspace/setup/data/Fund_Cash_Flows.csv'
DELIMITER ','
CSV HEADER;


-- Load Model Assumptions Data
COPY FUND_MODEL_ASSUMPTIONS (Primary_Strategy, Expected_MOIC_Gross, Target_IRR_Net, Investment_Period_Years, Fund_Life_Years, NAV_Initial_Qtr_Depreciation, NAV_Initial_Depreciation_Qtrs, J_Curve_Description, Modeling_Rationale)
FROM '/workspace/setup/data/fund_model_assumptions_data.csv'
DELIMITER ','
CSV HEADER;

-- =========================================================================
-- EXECUTION INSTRUCTIONS: This script must be run by the postgres user.
-- =========================================================================