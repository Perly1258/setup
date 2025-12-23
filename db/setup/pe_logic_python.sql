-- =========================================================================
-- PRIVATE EQUITY LOGIC LAYER (PL/PYTHON)
-- Dependencies: Requires 'postgresql-plpython3-16' (or 14) installed on OS.
-- =========================================================================

-- 1. ENABLE PYTHON EXTENSION
CREATE EXTENSION IF NOT EXISTS plpython3u;

-- 2. VIEW: MASTER HIERARCHY CUBE (The "Rollup")
-- Calculates Scalar Metrics (TVPI, DPI, NAV) for ALL levels:
-- Portfolio -> Strategy -> Sub-Strategy -> Fund
DROP VIEW IF EXISTS view_pe_hierarchy_metrics CASCADE;
CREATE OR REPLACE VIEW view_pe_hierarchy_metrics AS
WITH 
latest_nav AS (
    SELECT DISTINCT ON (fund_id) fund_id, net_asset_value_usd
    FROM pe_historical_cash_flows ORDER BY fund_id, transaction_date DESC
),
fund_aggregates AS (
    SELECT 
        cf.fund_id,
        SUM(ABS(cf.investment_paid_in_usd) + ABS(cf.management_fees_usd)) as total_paid_in,
        SUM(cf.profit_distribution_usd + cf.return_of_cost_distribution_usd) as total_distributed
    FROM pe_historical_cash_flows cf
    GROUP BY cf.fund_id
)
SELECT 
    CASE 
        WHEN p.primary_strategy IS NULL THEN 'Portfolio'
        WHEN p.sub_strategy IS NULL THEN 'Strategy'
        WHEN p.fund_name IS NULL THEN 'Sub-Strategy'
        ELSE 'Fund' 
    END as hierarchy_level,
    COALESCE(p.primary_strategy, 'Total Portfolio') as primary_strategy,
    COALESCE(p.sub_strategy, '-') as sub_strategy,
    COALESCE(p.fund_name, '-') as fund_name,
    SUM(p.total_commitment_usd) as total_commitment,
    SUM(fa.total_paid_in) as total_paid_in,
    SUM(fa.total_distributed) as total_distributed,
    SUM(ln.net_asset_value_usd) as total_nav,
    (SUM(fa.total_distributed) + SUM(ln.net_asset_value_usd)) as total_value,
    CASE WHEN SUM(fa.total_paid_in) > 0 THEN ROUND(SUM(fa.total_distributed) / SUM(fa.total_paid_in), 2) ELSE 0 END as dpi,
    CASE WHEN SUM(fa.total_paid_in) > 0 THEN ROUND((SUM(fa.total_distributed) + SUM(ln.net_asset_value_usd)) / SUM(fa.total_paid_in), 2) ELSE 0 END as tvpi,
    SUM(p.total_commitment_usd) - SUM(fa.total_paid_in) as remaining_commitment
FROM pe_portfolio p
LEFT JOIN fund_aggregates fa ON p.fund_id = fa.fund_id
LEFT JOIN latest_nav ln ON p.fund_id = ln.fund_id
GROUP BY ROLLUP (p.primary_strategy, p.sub_strategy, p.fund_name)
ORDER BY p.primary_strategy NULLS FIRST, p.sub_strategy NULLS FIRST, p.fund_name NULLS FIRST;

-- 3. VIEW: YEARLY CASH FLOWS (Discrete)
-- Updated with ROLLUP(primary_strategy) to include 'Total Portfolio' J-Curve
DROP VIEW IF EXISTS view_yearly_cash_flows CASCADE;
CREATE OR REPLACE VIEW view_yearly_cash_flows AS
SELECT 
    COALESCE(p.primary_strategy, 'Total Portfolio') as primary_strategy,
    EXTRACT(YEAR FROM cf.transaction_date) as cf_year,
    SUM(cf.profit_distribution_usd + cf.return_of_cost_distribution_usd) as yearly_dist,
    SUM(cf.investment_paid_in_usd + cf.management_fees_usd) as yearly_contributions,
    SUM((cf.profit_distribution_usd + cf.return_of_cost_distribution_usd) + 
        (cf.investment_paid_in_usd + cf.management_fees_usd)) as net_cash_flow
FROM pe_historical_cash_flows cf
JOIN pe_portfolio p ON cf.fund_id = p.fund_id
-- This allows J-Curves for individual strategies AND the total portfolio (NULL strategy)
GROUP BY ROLLUP(p.primary_strategy), cf_year
ORDER BY p.primary_strategy NULLS FIRST, cf_year;

-- 4. VIEW: CUMULATIVE J-CURVE (Running Totals)
DROP VIEW IF EXISTS view_j_curve_cumulative CASCADE;
CREATE OR REPLACE VIEW view_j_curve_cumulative AS
SELECT 
    primary_strategy,
    cf_year,
    net_cash_flow as discrete_cash_flow,
    SUM(net_cash_flow) OVER (
        PARTITION BY primary_strategy 
        ORDER BY cf_year ASC
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) as cumulative_net_cash_flow
FROM view_yearly_cash_flows;

-- 5. FUNCTION: MAIN METRICS ENGINE (PL/PYTHON)
-- Calculates complex metrics (IRR, YTD) on demand
CREATE OR REPLACE FUNCTION fn_get_pe_metrics_py(
    filter_level text, -- 'PORTFOLIO', 'STRATEGY', 'SUB_STRATEGY', 'FUND'
    filter_name text   -- e.g., 'Venture Capital' or NULL for Portfolio
)
RETURNS json AS $$
    import json
    import datetime

    # --- HELPER: XIRR SOLVER ---
    def xirr(cashflows, dates):
        if not cashflows or len(cashflows) < 2: return 0.0
        start_date = dates[0]
        years = [(d - start_date).days / 365.25 for d in dates]
        rate = 0.1 
        for _ in range(50):
            try:
                npv = sum([cf / (1 + rate)**t for cf, t in zip(cashflows, years)])
                d_npv = sum([-t * cf / (1 + rate)**(t + 1) for cf, t in zip(cashflows, years)])
                if abs(npv) < 1e-6: return rate
                if d_npv == 0: break
                rate = rate - npv / d_npv
            except: break
        return rate

    # --- A. DYNAMIC QUERY BUILDER ---
    sql_filter = "1=1"
    params = []
    
    if filter_level == 'STRATEGY':
        sql_filter = "p.primary_strategy = $1"
        params = [filter_name]
    elif filter_level == 'SUB_STRATEGY':
        sql_filter = "p.sub_strategy = $1"
        params = [filter_name]
    elif filter_level == 'FUND':
        sql_filter = "p.fund_name = $1"
        params = [filter_name]
    
    # --- B. FETCH CASH FLOWS ---
    cf_query = f"""
        SELECT 
            cf.transaction_date,
            (cf.profit_distribution_usd + cf.return_of_cost_distribution_usd + 
             cf.investment_paid_in_usd + cf.management_fees_usd) as net_flow,
            cf.investment_paid_in_usd,
            cf.management_fees_usd,
            cf.profit_distribution_usd,
            cf.return_of_cost_distribution_usd
        FROM pe_historical_cash_flows cf
        JOIN pe_portfolio p ON cf.fund_id = p.fund_id
        WHERE {sql_filter}
        ORDER BY cf.transaction_date ASC
    """
    
    cf_plan = plpy.prepare(cf_query, ["text"] if params else [])
    cf_rows = plpy.execute(cf_plan, params)

    if not cf_rows:
        return json.dumps({"error": f"No data found for {filter_name}"})

    # --- C. FETCH LATEST NAV ---
    nav_query = f"""
        WITH latest_dates AS (
            SELECT fund_id, MAX(transaction_date) as max_date
            FROM pe_historical_cash_flows
            GROUP BY fund_id
        )
        SELECT SUM(cf.net_asset_value_usd) as total_nav
        FROM pe_historical_cash_flows cf
        JOIN latest_dates ld ON cf.fund_id = ld.fund_id AND cf.transaction_date = ld.max_date
        JOIN pe_portfolio p ON cf.fund_id = p.fund_id
        WHERE {sql_filter}
    """
    nav_plan = plpy.prepare(nav_query, ["text"] if params else [])
    nav_result = plpy.execute(nav_plan, params)
    total_nav = nav_result[0]['total_nav'] or 0.0

    # --- D. CALCULATE METRICS (INCEPTION & YTD) ---
    last_tx_date = datetime.datetime.strptime(str(cf_rows[-1]['transaction_date']), '%Y-%m-%d')
    current_year = last_tx_date.year

    total_paid_in = 0.0
    total_distributed = 0.0
    ytd_paid_in = 0.0
    ytd_distributed = 0.0

    irr_amounts = []
    irr_dates = []

    for row in cf_rows:
        paid_in = abs(float(row['investment_paid_in_usd'] or 0)) + abs(float(row['management_fees_usd'] or 0))
        dist = float(row['profit_distribution_usd'] or 0) + float(row['return_of_cost_distribution_usd'] or 0)
        net = row['net_flow']
        
        dt = datetime.datetime.strptime(str(row['transaction_date']), '%Y-%m-%d')
        
        # Inception Totals
        total_paid_in += paid_in
        total_distributed += dist
        if net is not None:
            irr_amounts.append(float(net))
            irr_dates.append(dt)
            
        # YTD Logic
        if dt.year == current_year:
            ytd_paid_in += paid_in
            ytd_distributed += dist

    # Add Terminal Value (NAV) for IRR
    if total_nav > 0 and irr_dates:
        irr_amounts.append(float(total_nav))
        irr_dates.append(irr_dates[-1])

    dpi = (total_distributed / total_paid_in) if total_paid_in else 0.0
    tvpi = ((total_distributed + float(total_nav)) / total_paid_in) if total_paid_in else 0.0
    calculated_irr = xirr(irr_amounts, irr_dates)

    # --- E. RETURN JSON ---
    result = {
        "level": filter_level,
        "scope": filter_name if filter_name else "Entire Portfolio",
        "data_as_of_year": current_year,
        "metrics_since_inception": {
            "total_paid_in": total_paid_in,
            "total_distributed": total_distributed,
            "total_nav": float(total_nav),
            "dpi": round(dpi, 2),
            "tvpi": round(tvpi, 2),
            "irr": round(calculated_irr * 100, 2)
        },
        "metrics_ytd": {
            "year": current_year,
            "ytd_paid_in": ytd_paid_in,
            "ytd_distributed": ytd_distributed,
            "ytd_net_cash_flow": ytd_distributed - ytd_paid_in
        }
    }

    return json.dumps(result)
$$ LANGUAGE plpython3u;