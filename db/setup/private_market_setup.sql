-- =========================================================================
-- DATABASE SETUP SCRIPT: PRIVATE MARKETS PORTFOLIO AND CASH FLOWS
-- TARGET DATABASE: PostgreSQL or compatible system (e.g., SQLite via CLI)
-- =========================================================================

-- 1. DATABASE CREATION AND CONNECTION
-- This command creates the database (must be run while connected to 'postgres' or similar default db)
CREATE DATABASE private_markets_db;

-- This command connects to the newly created database to execute the rest of the script
\c private_markets_db; 

-- -------------------------------------------------------------------------
-- 1. Create PE_Portfolio Table (Static Fund Metadata)
-- Primary Key: Fund_ID
-- Commitment is in Millions of USD (MM USD).
-- -------------------------------------------------------------------------
CREATE TABLE PE_Portfolio (
    Fund_ID INTEGER PRIMARY KEY, -- Use INTEGER for explicit IDs
    Fund_Name VARCHAR(255) NOT NULL,
    Vintage_Year INTEGER NOT NULL,
    Primary_Strategy VARCHAR(50) NOT NULL,
    Sub_Strategy VARCHAR(50),
    Total_Commitment_MM_USD NUMERIC(10, 2) NOT NULL,
    Comment TEXT
);

-- -------------------------------------------------------------------------
-- 2. Create Fund_Cash_Flows Table (Time-Series Transaction Data)
-- Primary Key: Transaction_ID (uses implicit or explicit IDENTITY depending on DB)
-- Foreign Key: Fund_ID references PE_Portfolio(Fund_ID)
-- Amounts are in Millions of USD (MM USD). NAV is in actual USD.
-- -------------------------------------------------------------------------
CREATE TABLE Fund_Cash_Flows (
    Transaction_ID SERIAL PRIMARY KEY, -- SERIAL for PostgreSQL auto-incrementing key
    Fund_ID INTEGER NOT NULL,
    Transaction_Date DATE NOT NULL,
    Reporting_Quarter VARCHAR(5) NOT NULL,
    Transaction_Type VARCHAR(20) NOT NULL, -- e.g., 'Capital Call', 'Distribution', 'NAV Update'
    Investment_MM_USD NUMERIC(15, 4), -- Negative for calls
    Fees_MM_USD NUMERIC(15, 4),        -- Negative for calls
    Return_of_Cost_MM_USD NUMERIC(15, 4), -- Positive for distributions
    Profit_MM_USD NUMERIC(15, 4),      -- Positive for distributions
    Quarterly_NAV_USD NUMERIC(20, 2),  -- Actual USD value (not millions)
    MOIC NUMERIC(5, 2),
    
    FOREIGN KEY (Fund_ID) REFERENCES PE_Portfolio(Fund_ID)
);


-- =========================================================================
-- 3. Data Loading: Load from CSV Files (PostgreSQL COPY Commands)
-- You must first ensure your DB is running and the CSV files are accessible.
-- =========================================================================

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

-- =========================================================================
-- 4. MODEL INPUT ASSUMPTIONS TABLE
-- Used to parameterize the cash flow and NAV projection engine 
-- for each Primary Strategy in the PE_Portfolio table.
-- =========================================================================

CREATE TABLE FUND_MODEL_ASSUMPTIONS (
    Primary_Strategy VARCHAR(50) PRIMARY KEY,
    
    -- 1. RETURN ASSUMPTIONS
    Expected_MOIC_Gross NUMERIC(4, 2) NOT NULL, 
    Target_IRR_Net NUMERIC(4, 2) NOT NULL,     

    -- 2. TIMING AND DURATION
    Investment_Period_Years INTEGER NOT NULL,  
    Fund_Life_Years INTEGER NOT NULL,          
    
    -- 3. QUANTITATIVE J-CURVE PARAMETERS (New & Improved Fields)
    NAV_Initial_Qtr_Depreciation NUMERIC(5, 4) NOT NULL, -- e.g., -0.0050 for -0.50%
    NAV_Initial_Depreciation_Qtrs INTEGER NOT NULL,     -- e.g., 6 (quarters)
    
    -- 4. QUALITATIVE DESCRIPTION (Kept for LLM interpretation)
    J_Curve_Description VARCHAR(50) NOT NULL, -- e.g., 'Moderate Drop'
    Modeling_Rationale TEXT 
);

-- =========================================================================
-- DATA INSERTION: Simulated Quantitative Input Drivers
-- =========================================================================

INSERT INTO FUND_MODEL_ASSUMPTIONS (
    Primary_Strategy, Expected_MOIC_Gross, Target_IRR_Net, 
    Investment_Period_Years, Fund_Life_Years, 
    NAV_Initial_Qtr_Depreciation, NAV_Initial_Depreciation_Qtrs,
    J_Curve_Description, Modeling_Rationale
) VALUES
('Venture Capital', 2.75, 0.22, 5, 12, 
 -0.0150, 8, 'Deep Initial Drop', 
 'High-risk, long-gestation assets. Deep J-Curve expected (-1.5% Qtrly for 8 Qtrs).'),

('Private Equity', 1.85, 0.16, 6, 10, 
 -0.0050, 6, 'Moderate Drop', 
 'Standard J-Curve dip due to fees and transaction costs (-0.5% Qtrly for 6 Qtrs).'),

('Real Estate', 1.60, 0.13, 5, 10, 
 -0.0010, 4, 'Shallow Initial Drop', 
 'Minimal J-Curve, offset by early income/yield (-0.1% Qtrly for 4 Qtrs).'),

('Infrastructure', 1.50, 0.10, 7, 15, 
 -0.0001, 2, 'Negligible Drop', 
 'Very stable assets; virtually no J-Curve (-0.01% Qtrly for 2 Qtrs).'),

('Private Credit', 1.35, 0.09, 4, 7, 
 0.0000, 0, 'No J-Curve (Flat)', 
 'Primarily debt payments; capital is returned quickly, not relying on equity exit.'),

('Secondaries', 1.70, 0.14, 2, 8, 
 -0.0030, 3, 'Accelerated Shallow Drop', 
 'Acquiring mature portfolios accelerates distributions and minimizes the initial J-Curve dip.'),
 
('Fund of Funds (FoF)', 1.65, 0.13, 5, 12, 
 -0.0040, 5, 'Moderate Drop (Smoothed)', 
 'Diversification across multiple underlying funds smooths out J-Curve volatility.'),
 
('Co-Investment', 1.80, 0.15, 4, 9, 
 -0.0060, 7, 'Lumpy Drop', 
 'Deployment is tied directly to opportunistic deal flow, leading to more volatile but short-lived initial drops.'),
 
('Real Assets', 1.65, 0.11, 5, 15, 
 -0.0015, 4, 'Shallow Drop', 
 'Tangible assets with periodic yield; stable valuation.')
-- =========================================================================
-- EXECUTION INSTRUCTIONS
-- To run this script and create the database and load data:
-- 1. Ensure PostgreSQL is running.
-- 2. Ensure 'PE_Portfolio.csv' and 'Fund_Cash_Flows.csv' are in the same directory.
-- 3. Run the following command (using user 'psogresql' and assuming you are running this from a shell):
--    psql -U psogresql -d postgres -f private_market_setup.sql
--    (You will be prompted to enter the password 'psogresql')
-- =========================================================================
