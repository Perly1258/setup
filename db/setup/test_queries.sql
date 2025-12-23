-- =========================================================================
-- TEST SCRIPT FOR PRIVATE EQUITY FUNCTIONS AND VIEWS
-- This script executes 50 queries to test various functionalities.
-- =========================================================================

-- Ensure a clean state for forecast output before running new forecasts
DELETE FROM pe_forecast_output;

-- 1. Test fn_get_pe_metrics_py (10 queries)
-- -------------------------------------------------------------------------
SELECT '--- fn_get_pe_metrics_py: Portfolio Level ---' AS test_case;
SELECT fn_get_pe_metrics_py('PORTFOLIO', NULL) AS portfolio_metrics;

SELECT '--- fn_get_pe_metrics_py: Strategy Level (Private Equity) ---' AS test_case;
SELECT fn_get_pe_metrics_py('STRATEGY', 'Private Equity') AS pe_metrics;

SELECT '--- fn_get_pe_metrics_py: Strategy Level (Venture Capital) ---' AS test_case;
SELECT fn_get_pe_metrics_py('STRATEGY', 'Venture Capital') AS vc_metrics;

SELECT '--- fn_get_pe_metrics_py: Strategy Level (Real Estate) ---' AS test_case;
SELECT fn_get_pe_metrics_py('STRATEGY', 'Real Estate') AS re_metrics;

SELECT '--- fn_get_pe_metrics_py: Strategy Level (Infrastructure) ---' AS test_case;
SELECT fn_get_pe_metrics_py('STRATEGY', 'Infrastructure') AS infra_metrics;

SELECT '--- fn_get_pe_metrics_py: Strategy Level (Private Credit) ---' AS test_case;
SELECT fn_get_pe_metrics_py('STRATEGY', 'Private Credit') AS pc_metrics;

SELECT '--- fn_get_pe_metrics_py: Strategy Level (Secondaries) ---' AS test_case;
SELECT fn_get_pe_metrics_py('STRATEGY', 'Secondaries') AS secondaries_metrics;

SELECT '--- fn_get_pe_metrics_py: Strategy Level (Fund of Funds (FoF)) ---' AS test_case;
SELECT fn_get_pe_metrics_py('STRATEGY', 'Fund of Funds (FoF)') AS fof_metrics;

SELECT '--- fn_get_pe_metrics_py: Fund Level (Pinnacle Tech Fund VI) ---' AS test_case;
SELECT fn_get_pe_metrics_py('FUND', 'Pinnacle Tech Fund VI') AS fund1_metrics;

SELECT '--- fn_get_pe_metrics_py: Fund Level (Global Buyout Capital X) ---' AS test_case;
SELECT fn_get_pe_metrics_py('FUND', 'Global Buyout Capital X') AS fund3_metrics;

-- 2. Test view_pe_hierarchy_metrics (10 queries)
-- -------------------------------------------------------------------------
SELECT '--- view_pe_hierarchy_metrics: Portfolio Level ---' AS test_case;
SELECT * FROM view_pe_hierarchy_metrics WHERE hierarchy_level = 'Portfolio';

SELECT '--- view_pe_hierarchy_metrics: All Strategies ---' AS test_case;
SELECT * FROM view_pe_hierarchy_metrics WHERE hierarchy_level = 'Strategy' LIMIT 5;

SELECT '--- view_pe_hierarchy_metrics: Private Equity Strategy ---' AS test_case;
SELECT * FROM view_pe_hierarchy_metrics WHERE primary_strategy = 'Private Equity' AND hierarchy_level = 'Strategy';

SELECT '--- view_pe_hierarchy_metrics: Venture Capital Strategy ---' AS test_case;
SELECT * FROM view_pe_hierarchy_metrics WHERE primary_strategy = 'Venture Capital' AND hierarchy_level = 'Strategy';

SELECT '--- view_pe_hierarchy_metrics: Infrastructure Strategy ---' AS test_case;
SELECT * FROM view_pe_hierarchy_metrics WHERE primary_strategy = 'Infrastructure' AND hierarchy_level = 'Strategy';

SELECT '--- view_pe_hierarchy_metrics: Specific Fund (Pinnacle Tech Fund VI) ---' AS test_case;
SELECT * FROM view_pe_hierarchy_metrics WHERE fund_name = 'Pinnacle Tech Fund VI';

SELECT '--- view_pe_hierarchy_metrics: Specific Fund (Apex Venture Partners III) ---' AS test_case;
SELECT * FROM view_pe_hierarchy_metrics WHERE fund_name = 'Apex Venture Partners III';

SELECT '--- view_pe_hierarchy_metrics: Specific Fund (Global Buyout Capital X) ---' AS test_case;
SELECT * FROM view_pe_hierarchy_metrics WHERE fund_name = 'Global Buyout Capital X';

SELECT '--- view_pe_hierarchy_metrics: All Sub-Strategies ---' AS test_case;
SELECT * FROM view_pe_hierarchy_metrics WHERE hierarchy_level = 'Sub-Strategy' LIMIT 5;

SELECT '--- view_pe_hierarchy_metrics: Specific Sub-Strategy (Venture Capital) ---' AS test_case;
SELECT * FROM view_pe_hierarchy_metrics WHERE sub_strategy = 'Venture Capital' AND hierarchy_level = 'Sub-Strategy';

-- 3. Test view_yearly_cash_flows (10 queries)
-- -------------------------------------------------------------------------
SELECT '--- view_yearly_cash_flows: Total Portfolio ---' AS test_case;
SELECT * FROM view_yearly_cash_flows WHERE primary_strategy = 'Total Portfolio' ORDER BY cf_year LIMIT 5;

SELECT '--- view_yearly_cash_flows: Private Equity ---' AS test_case;
SELECT * FROM view_yearly_cash_flows WHERE primary_strategy = 'Private Equity' ORDER BY cf_year LIMIT 5;

SELECT '--- view_yearly_cash_flows: Venture Capital ---' AS test_case;
SELECT * FROM view_yearly_cash_flows WHERE primary_strategy = 'Venture Capital' ORDER BY cf_year LIMIT 5;

SELECT '--- view_yearly_cash_flows: Real Estate ---' AS test_case;
SELECT * FROM view_yearly_cash_flows WHERE primary_strategy = 'Real Estate' ORDER BY cf_year LIMIT 5;

SELECT '--- view_yearly_cash_flows: Infrastructure ---' AS test_case;
SELECT * FROM view_yearly_cash_flows WHERE primary_strategy = 'Infrastructure' ORDER BY cf_year LIMIT 5;

SELECT '--- view_yearly_cash_flows: Private Credit ---' AS test_case;
SELECT * FROM view_yearly_cash_flows WHERE primary_strategy = 'Private Credit' ORDER BY cf_year LIMIT 5;

SELECT '--- view_yearly_cash_flows: Secondaries ---' AS test_case;
SELECT * FROM view_yearly_cash_flows WHERE primary_strategy = 'Secondaries' ORDER BY cf_year LIMIT 5;

SELECT '--- view_yearly_cash_flows: Fund of Funds (FoF) ---' AS test_case;
SELECT * FROM view_yearly_cash_flows WHERE primary_strategy = 'Fund of Funds (FoF)' ORDER BY cf_year LIMIT 5;

SELECT '--- view_yearly_cash_flows: Total Portfolio for 2023 ---' AS test_case;
SELECT * FROM view_yearly_cash_flows WHERE primary_strategy = 'Total Portfolio' AND cf_year = 2023;

SELECT '--- view_yearly_cash_flows: Private Equity for 2022 ---' AS test_case;
SELECT * FROM view_yearly_cash_flows WHERE primary_strategy = 'Private Equity' AND cf_year = 2022;

-- 4. Test view_j_curve_cumulative (10 queries)
-- -------------------------------------------------------------------------
SELECT '--- view_j_curve_cumulative: Total Portfolio ---' AS test_case;
SELECT * FROM view_j_curve_cumulative WHERE primary_strategy = 'Total Portfolio' ORDER BY cf_year LIMIT 5;

SELECT '--- view_j_curve_cumulative: Private Equity ---' AS test_case;
SELECT * FROM view_j_curve_cumulative WHERE primary_strategy = 'Private Equity' ORDER BY cf_year LIMIT 5;

SELECT '--- view_j_curve_cumulative: Venture Capital ---' AS test_case;
SELECT * FROM view_j_curve_cumulative WHERE primary_strategy = 'Venture Capital' ORDER BY cf_year LIMIT 5;

SELECT '--- view_j_curve_cumulative: Real Estate ---' AS test_case;
SELECT * FROM view_j_curve_cumulative WHERE primary_strategy = 'Real Estate' ORDER BY cf_year LIMIT 5;

SELECT '--- view_j_curve_cumulative: Infrastructure ---' AS test_case;
SELECT * FROM view_j_curve_cumulative WHERE primary_strategy = 'Infrastructure' ORDER BY cf_year LIMIT 5;

SELECT '--- view_j_curve_cumulative: Private Credit ---' AS test_case;
SELECT * FROM view_j_curve_cumulative WHERE primary_strategy = 'Private Credit' ORDER BY cf_year LIMIT 5;

SELECT '--- view_j_curve_cumulative: Secondaries ---' AS test_case;
SELECT * FROM view_j_curve_cumulative WHERE primary_strategy = 'Secondaries' ORDER BY cf_year LIMIT 5;

SELECT '--- view_j_curve_cumulative: Fund of Funds (FoF) ---' AS test_case;
SELECT * FROM view_j_curve_cumulative WHERE primary_strategy = 'Fund of Funds (FoF)' ORDER BY cf_year LIMIT 5;

SELECT '--- view_j_curve_cumulative: Total Portfolio for 2023 ---' AS test_case;
SELECT * FROM view_j_curve_cumulative WHERE primary_strategy = 'Total Portfolio' AND cf_year = 2023;

SELECT '--- view_j_curve_cumulative: Venture Capital for 2021 ---' AS test_case;
SELECT * FROM view_j_curve_cumulative WHERE primary_strategy = 'Venture Capital' AND cf_year = 2021;

-- 5. Test fn_run_takahashi_forecast and pe_forecast_output (10 queries)
-- -------------------------------------------------------------------------
SELECT '--- fn_run_takahashi_forecast: Venture Capital (12 quarters) ---' AS test_case;
SELECT fn_run_takahashi_forecast('Venture Capital', 12) AS forecast_log_vc;
SELECT '--- pe_forecast_output: Venture Capital (first 5 rows) ---' AS test_case;
SELECT * FROM pe_forecast_output WHERE strategy = 'Venture Capital' ORDER BY quarter_date LIMIT 5;

SELECT '--- fn_run_takahashi_forecast: Private Equity (8 quarters) ---' AS test_case;
SELECT fn_run_takahashi_forecast('Private Equity', 8) AS forecast_log_pe;
SELECT '--- pe_forecast_output: Private Equity (first 5 rows) ---' AS test_case;
SELECT * FROM pe_forecast_output WHERE strategy = 'Private Equity' ORDER BY quarter_date LIMIT 5;

SELECT '--- fn_run_takahashi_forecast: Real Estate (16 quarters) ---' AS test_case;
SELECT fn_run_takahashi_forecast('Real Estate', 16) AS forecast_log_re;
SELECT '--- pe_forecast_output: Real Estate (first 5 rows) ---' AS test_case;
SELECT * FROM pe_forecast_output WHERE strategy = 'Real Estate' ORDER BY quarter_date LIMIT 5;

SELECT '--- fn_run_takahashi_forecast: Infrastructure (20 quarters) ---' AS test_case;
SELECT fn_run_takahashi_forecast('Infrastructure', 20) AS forecast_log_infra;
SELECT '--- pe_forecast_output: Infrastructure (first 5 rows) ---' AS test_case;
SELECT * FROM pe_forecast_output WHERE strategy = 'Infrastructure' ORDER BY quarter_date LIMIT 5;

SELECT '--- fn_run_takahashi_forecast: Secondaries (10 quarters) ---' AS test_case;
SELECT fn_run_takahashi_forecast('Secondaries', 10) AS forecast_log_secondaries;
SELECT '--- pe_forecast_output: Secondaries (first 5 rows) ---' AS test_case;
SELECT * FROM pe_forecast_output WHERE strategy = 'Secondaries' ORDER BY quarter_date LIMIT 5;
```
