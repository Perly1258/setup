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
-- EXECUTION INSTRUCTIONS
-- To run this script and create the database and load data:
-- 1. Ensure PostgreSQL is running.
-- 2. Ensure 'PE_Portfolio.csv' and 'Fund_Cash_Flows.csv' are in the same directory.
-- 3. Run the following command (using user 'psogresql' and assuming you are running this from a shell):
--    psql -U psogresql -d postgres -f private_market_setup.sql
--    (You will be prompted to enter the password 'psogresql')
-- =========================================================================
