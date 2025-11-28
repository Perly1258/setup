-- =========================================================================
-- FINAL MASTER RAG ANNOTATIONS
-- Incorporates ALL logic:
-- 1. Table Roles: Portfolio = "Positions Master", Cash Flows = "History Log"
-- 2. Time Routing: Historical = "Actuals", Forecast = "Projections"
-- 3. Math: Cap Calls (Inv+Fees), Distros (Profit+Return), Dry Powder
-- 4. Critical Logic: Latest NAV (Max Date), Strategy Joins
-- =========================================================================

\c private_markets_db;

-- 1. WIPE OLD INSTRUCTIONS
TRUNCATE TABLE schema_annotations;

-- 2. LOAD COMPREHENSIVE LOGIC
INSERT INTO schema_annotations (table_name, column_name, natural_language_description) VALUES 

-- === A. THE POSITIONS (Parent Table) ===
('pe_portfolio', 'fund_id', 'PRIMARY KEY for the "Positions" table. Each row is a unique Fund Position ("What we own"). Use this to list Fund Names, Vintages, or Strategies.'),
('pe_portfolio', 'primary_strategy', 'Investment Strategy (e.g., Venture Capital, Buyout). **CRITICAL:** To filter cash flows by strategy, you MUST JOIN "pe_historical_cash_flows" to this table on "fund_id".'),
('pe_portfolio', 'total_commitment_usd', 'The total capital committed. Synonyms: "Fund Size". **FORMULA:** "Dry Powder" (Unfunded) = total_commitment_usd - SUM(investment_paid_in_usd + management_fees_usd).'),
('pe_portfolio', 'vintage_year', 'The inception year. Use for queries like "2022 Vintage funds".'),

-- === B. THE HISTORY LOG (Child Table - Actuals) ===
('pe_historical_cash_flows', 'transaction_id', 'The Log of History. This table contains the ENTIRE time-series history of "Past", "Actual", or "Realized" events. Do not query this for forecasts.'),
('pe_historical_cash_flows', 'fund_id', 'Foreign Key. Connects the History Log to the Positions table. Required for Joins.'),

-- === C. THE FORECASTS (Child Table - Future) ===
('pe_forecast_cash_flows', 'projection_id', 'The Forecast Log. Query this table ONLY for "Future", "Projected", or "Estimated" cash flows. Do not mix with historical data.'),

-- === D. NAV INTELLIGENCE (The "Latest" Rule) ===
('pe_historical_cash_flows', 'net_asset_value_usd', 'History of Valuations (NAV). **CRITICAL RULE:** This is a history log. Summing this column is WRONG. To get "Current Value" or "Latest NAV", you MUST filter for the row with the MAXIMUM "transaction_date" for each fund_id.'),

-- === E. CAPITAL CALLS (Math: Inv + Fees) ===
('pe_historical_cash_flows', 'investment_paid_in_usd', 'Pure Investment amount. Synonyms: "Drawdowns", "Called Capital". **FORMULA:** To calculate "Total Capital Calls" or "Total Paid-In", you MUST SUM(investment_paid_in_usd + management_fees_usd).'),
('pe_historical_cash_flows', 'management_fees_usd', 'Management Fees. Always ADD this to "investment_paid_in_usd" when calculating Total Capital Calls.'),

-- === F. DISTRIBUTIONS (Math: Profit + Return) ===
('pe_historical_cash_flows', 'profit_distribution_usd', 'Realized Gains. Synonyms: "Carry". Part 1 of Distributions. **FORMULA:** Total Distributions = SUM(profit_distribution_usd + return_of_cost_distribution_usd).'),
('pe_historical_cash_flows', 'return_of_cost_distribution_usd', 'Return of Capital. Part 2 of Distributions. **FORMULA:** Total Distributions = SUM(return_of_cost_distribution_usd + profit_distribution_usd).'),

-- === G. DATES & REPORTING ===
('pe_historical_cash_flows', 'transaction_date', 'The date of the event. Use for filtering (e.g., "In 2022") or finding the Latest NAV (MAX date).'),
('pe_historical_cash_flows', 'reporting_quarter', 'The financial quarter (e.g., "Q3"). Use for quarterly aggregation.');