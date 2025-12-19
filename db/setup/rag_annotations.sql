-- =========================================================================
-- FINAL MASTER RAG ANNOTATIONS
-- Incorporates ALL logic:
-- 1. Table Roles: Portfolio = "Positions Master", Cash Flows = "History Log"
-- 2. Time Routing: Historical = "Actuals", Forecast = "Projections"
-- 3. Math: Cap Calls (Inv+Fees), Distros (Profit+Return), Dry Powder
-- 4. Critical Logic: Latest NAV (Max Date), Strategy Joins
-- =========================================================================

-- NOTE: Ensure you are already connected to 'private_markets_db' before running.

-- 1. WIPE OLD INSTRUCTIONS
TRUNCATE TABLE schema_annotations;

-- 2. LOAD COMPREHENSIVE LOGIC
INSERT INTO schema_annotations (table_name, column_name, natural_language_description) VALUES 

-- === A. THE POSITIONS (Parent Table) ===
('pe_portfolio', 'fund_id', 'PRIMARY KEY for the "Positions" table. Each row is a unique Fund Position ("What we own"). Use this to list Fund Names, Vintages, or Strategies.'),
('pe_portfolio', 'primary_strategy', 'Investment Strategy (e.g., Venture Capital, Buyout). **CRITICAL:** To filter cash flows by strategy, you MUST JOIN "pe_historical_cash_flows" to this table on "fund_id".'),
('pe_portfolio', 'sub_strategy', 'Detailed Strategy (e.g., LBO, Growth Equity). **SEARCH RULE:** When filtering by strategy, always check BOTH "primary_strategy" AND "sub_strategy" using OR.'),
('pe_portfolio', 'total_commitment_usd', 'The total capital committed. Synonyms: "Fund Size". **FORMULA:** "Dry Powder" (Unfunded/Remaining) = total_commitment_usd - SUM(ABS(investment_paid_in_usd + management_fees_usd)). Note: Investments are negative in DB, so use ABS() or add them back.'),
('pe_portfolio', 'vintage_year', 'The inception year. Use for queries like "2022 Vintage funds".'),

-- === B. THE HISTORY LOG (Child Table) ===
('pe_historical_cash_flows', 'fund_id', 'FOREIGN KEY links to "pe_portfolio". Use this to join Strategy or Fund Name info.'),
('pe_historical_cash_flows', 'net_asset_value_usd', 'History of Valuations (NAV). **CRITICAL RULE:** This is a history log. Summing this column is WRONG. To get "Current Value" or "Latest NAV", you MUST filter for the row with the MAXIMUM "transaction_date" for each fund_id. **IRR RULE:** For IRR calculations, the Latest NAV must be treated as a positive Terminal Value cash flow.'),

-- === C. CAPITAL CALLS (Math: Inv + Fees) ===
('pe_historical_cash_flows', 'investment_paid_in_usd', 'Pure Investment amount. **SIGN NOTE:** This value is stored as NEGATIVE in the database (e.g., -500000). To calculate "Total Paid In", simply SUM() it (result will be negative) or SUM(ABS()) it (result will be positive).'),
('pe_historical_cash_flows', 'management_fees_usd', 'Management Fees. **SIGN NOTE:** Stored as NEGATIVE. Always ADD this to "investment_paid_in_usd" when calculating Net Cash Flow.'),

-- === D. DISTRIBUTIONS (Math: Profit + Return) ===
('pe_historical_cash_flows', 'profit_distribution_usd', 'Realized Gains. Synonyms: "Carry". Stored as POSITIVE. **FORMULA:** Total Distributions = SUM(profit_distribution_usd + return_of_cost_distribution_usd).'),
('pe_historical_cash_flows', 'return_of_cost_distribution_usd', 'Return of Capital. Stored as POSITIVE. **FORMULA:** Total Distributions = SUM(return_of_cost_distribution_usd + profit_distribution_usd).'),

-- === E. NET CASH FLOW FORMULA ===
('pe_historical_cash_flows', 'transaction_type', '**NET CASH FLOW FORMULA:** Net Amount = (profit_distribution_usd + return_of_cost_distribution_usd) + (investment_paid_in_usd + management_fees_usd). Since investments are negative, simply adding them subtracts the cost correctly.');