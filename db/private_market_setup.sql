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
FROM 'PE_Portfolio.csv'
DELIMITER ','
CSV HEADER;


-- Load Cash Flow Data
COPY Fund_Cash_Flows (Fund_ID, Transaction_Date, Reporting_Quarter, Transaction_Type, Investment_MM_USD, Fees_MM_USD, Return_of_Cost_MM_USD, Profit_MM_USD, Quarterly_NAV_USD, MOIC)
FROM 'Fund_Cash_Flows.csv'
DELIMITER ','
CSV HEADER;

-- =========================================================================
-- 4. MODEL INPUT ASSUMPTIONS TABLE
-- Used to parameterize the cash flow and NAV projection engine 
-- for each Primary Strategy in the PE_Portfolio table.
-- =========================================================================

CREATE TABLE FUND_MODEL_ASSUMPTIONS (
    -- 1. IDENTIFICATION
    Primary_Strategy VARCHAR(50) PRIMARY KEY, -- Links to PE_Portfolio.Primary_Strategy
    
    -- 2. RETURN ASSUMPTIONS (Magnitude)
    Expected_MOIC_Gross NUMERIC(4, 2) NOT NULL, -- Target Total Distributions / Invested Capital
    Target_IRR_Net NUMERIC(4, 2) NOT NULL,     -- Target internal rate of return (annualized)

    -- 3. TIMING ASSUMPTIONS (Pacing and Horizon)
    Investment_Period_Years INTEGER NOT NULL,  -- Years where primary capital calls occur
    Fund_Life_Years INTEGER NOT NULL,          -- Total projected life of the fund
    
    -- 4. CURVE SHAPE ASSUMPTIONS (Qualitative Pacing)
    Contribution_Pace VARCHAR(50) NOT NULL, -- e.g., 'Aggressive S-Curve', 'Steady Linear'
    Distribution_Pace VARCHAR(50) NOT NULL, -- e.g., 'Late Peak', 'Early and Steady'
    NAV_Valuation_Initial_Impact VARCHAR(50) NOT NULL, -- Initial J-Curve effect (e.g., 'Deep Initial Drop', 'Shallow Drop')
    
    -- 5. COMMENTARY
    Modeling_Rationale TEXT -- Explanation for the assumptions
);

-- =========================================================================
-- DATA INSERTION: Simulated Input Drivers
-- =========================================================================

INSERT INTO FUND_MODEL_ASSUMPTIONS (
    Primary_Strategy, Expected_MOIC_Gross, Target_IRR_Net, 
    Investment_Period_Years, Fund_Life_Years, 
    Contribution_Pace, Distribution_Pace, NAV_Valuation_Initial_Impact, Modeling_Rationale
) VALUES
('Venture Capital', 2.75, 0.22, 5, 12, 
 'Aggressive S-Curve', 'Late Peak (Years 8-10)', 'Deep Initial Drop', 
 'High-risk, long-gestation assets. Requires high MOIC to offset failure rate. Deep J-Curve expected.'),

('Private Equity', 1.85, 0.16, 6, 10, 
 'Standard S-Curve', 'Mid-to-Late Peak (Years 5-8)', 'Moderate Drop', 
 'Focus on operational improvements and value-add over a medium hold period.'),

('Real Estate', 1.60, 0.13, 5, 10, 
 'Long & Linear Drawdown', 'Early and Steady Yield', 'Shallow Initial Drop', 
 'Assets often generate income immediately (rent/yield), mitigating the J-Curve.'),

('Infrastructure', 1.50, 0.10, 7, 15, 
 'Long, Flat Drawdown', 'Ongoing/Steady Yield', 'Negligible Drop', 
 'Very long life assets with stable, regulated cash flows (yield focus). Low J-Curve volatility.'),

('Private Credit', 1.35, 0.09, 4, 7, 
 'Rapid Drawdown', 'Immediate/Early Distribution', 'No J-Curve (Flat)', 
 'Primarily debt payments (interest/coupon). Capital is returned quickly, not relying on equity exit.'),

('Secondaries', 1.70, 0.14, 2, 8, 
 'Very Rapid Drawdown', 'Accelerated/Early Peak (Years 2-4)', 'Shallow Drop', 
 'Acquiring mature portfolios accelerates distributions and minimizes the initial J-Curve dip.'),

('Fund of Funds (FoF)', 1.65, 0.13, 5, 12, 
 'Standard S-Curve (Smoother)', 'Smoother Mid-to-Late Peak', 'Moderate Drop', 
 'Diversification across multiple underlying funds smooths out contributions and distributions.'),

('Co-Investment', 1.80, 0.15, 4, 9, 
 'Deal-Specific Lumpiness', 'Mid-Term Peak (Years 4-7)', 'Moderate Drop', 
 'Mimics Buyout/Growth, but deployment is tied directly to opportunistic deal flow.'),

('Real Assets', 1.65, 0.11, 5, 15, 
 'Long & Stable Drawdown', 'Moderate to Long Yield', 'Shallow Drop', 
 'Includes assets like farmland, timber, and commodities—tangible and often generating periodic yield.')
;
-- =========================================================================
-- EXECUTION INSTRUCTIONS
-- To run this script and create the database and load data:
-- 1. Ensure PostgreSQL is running.
-- 2. Ensure 'PE_Portfolio.csv' and 'Fund_Cash_Flows.csv' are in the same directory.
-- 3. Run the following command (using user 'psogresql' and assuming you are running this from a shell):
--    psql -U psogresql -d postgres -f private_market_setup.sql
--    (You will be prompted to enter the password 'psogresql')
-- =========================================================================
