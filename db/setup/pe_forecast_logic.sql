-- =========================================================================
-- PRIVATE EQUITY FORECASTING ENGINE (TAKAHASHI-ALEXANDER MODEL)
-- Purpose: Project future cash flows based on Strategy Assumptions.
-- Logic: PL/Python implementation of the Yale Model (Contributions/Distributions/NAV).
-- =========================================================================

-- 1. SETUP: MODELING ASSUMPTIONS TABLE
-- Stores the J-Curve and Growth parameters for each strategy.
DROP TABLE IF EXISTS pe_modeling_rules CASCADE;
CREATE TABLE pe_modeling_rules (
    primary_strategy VARCHAR(50) PRIMARY KEY,
    expected_moic_gross_multiple NUMERIC(4, 2),
    target_irr_net_percentage NUMERIC(4, 2), -- e.g. 0.15 for 15%
    investment_period_years INTEGER,
    fund_life_years INTEGER,
    nav_initial_qtr_depreciation NUMERIC(5, 4), -- Initial J-Curve hit
    nav_initial_depreciation_qtrs INTEGER,
    j_curve_model_description VARCHAR(50),
    modeling_rationale TEXT
);

-- 2. DATA LOAD (Assumes file is in /workspace/setup/data/ or adjust path)
-- In a real deployment, use \COPY. For this script, we insert the CSV data directly 
-- based on the file 'fund_model_assumptions_data.csv' you uploaded.
INSERT INTO pe_modeling_rules VALUES
('Venture Capital', 2.75, 0.22, 5, 12, -0.0150, 8, 'Deep Initial Drop', 'High-risk, long-gestation assets. Deep J-Curve expected (-1.5% Qtrly for 8 Qtrs).'),
('Private Equity', 1.85, 0.16, 6, 10, -0.0050, 6, 'Moderate Drop', 'Standard J-Curve dip due to fees and transaction costs (-0.5% Qtrly for 6 Qtrs).'),
('Real Estate', 1.60, 0.13, 5, 10, -0.0010, 4, 'Shallow Initial Drop', 'Minimal J-Curve, offset by early income/yield (-0.1% Qtrly for 4 Qtrs).'),
('Infrastructure', 1.50, 0.10, 7, 15, -0.0001, 2, 'Negligible Drop', 'Very stable assets; virtually no J-Curve (-0.01% Qtrly for 2 Qtrs).'),
('Private Credit', 1.35, 0.09, 4, 7, 0.0000, 0, 'No J-Curve (Flat)', 'Primarily debt payments; capital is returned quickly, not relying on equity exit.'),
('Secondaries', 1.70, 0.14, 2, 8, -0.0030, 3, 'Accelerated Shallow Drop', 'Acquiring mature portfolios accelerates distributions and minimizes the initial J-Curve dip.'),
('Fund of Funds (FoF)', 1.65, 0.13, 5, 12, -0.0040, 5, 'Moderate Drop (Smoothed)', 'Diversification across multiple underlying funds smooths out J-Curve volatility.'),
('Co-Investment', 1.80, 0.15, 4, 9, -0.0060, 7, 'Lumpy Drop', 'Deployment is tied directly to opportunistic deal flow, leading to more volatile but short-lived initial drops.'),
('Real Assets', 1.65, 0.11, 5, 15, -0.0015, 4, 'Shallow Drop', 'Tangible assets with periodic yield; stable valuation.');

-- 3. TABLE: FORECAST RESULTS
-- Stores the output of the simulation so the Agent can query it later.
DROP TABLE IF EXISTS pe_forecast_output;
CREATE TABLE pe_forecast_output (
    forecast_id SERIAL PRIMARY KEY,
    fund_id INTEGER,
    strategy VARCHAR(50),
    quarter_date DATE,
    forecast_type VARCHAR(20), -- 'Capital Call', 'Distribution', 'NAV'
    amount_usd NUMERIC(20, 2)
);

-- 4. FUNCTION: TAKAHASHI-ALEXANDER ENGINE (PL/PYTHON)
-- This function runs the simulation quarter-by-quarter.
CREATE OR REPLACE FUNCTION fn_run_takahashi_forecast(
    p_strategy text,       -- Filter by Strategy (Optional)
    p_quarters_to_project integer DEFAULT 20
)
RETURNS json AS $$
    import datetime
    from dateutil.relativedelta import relativedelta
    import json

    # --- A. HELPER: TAKAHASHI PARAMETERS ---
    # The Yale model uses "Bow Curves" for Contribution (RC) and Distribution (RD).
    def get_rate_contribution(age_qtrs, life_qtrs, inv_period_qtrs):
        # Rate of Contribution decreases as fund ages
        if age_qtrs >= inv_period_qtrs: return 0.0
        # Simple linear decay model for RC
        remaining = inv_period_qtrs - age_qtrs
        return remaining / sum(range(1, inv_period_qtrs + 1)) if inv_period_qtrs > 0 else 0

    def get_rate_distribution(age_qtrs, life_qtrs):
        # Rate of Distribution increases as fund ages (back-ended)
        if age_qtrs > life_qtrs: return 1.0 # Liquidate everything
        # Exponential ramp-up (The "Bow")
        return (age_qtrs / life_qtrs) ** 2.5 

    # --- B. FETCH RULES & CURRENT STATE ---
    # 1. Get Modeling Assumptions
    rules_plan = plpy.prepare("SELECT * FROM pe_modeling_rules WHERE primary_strategy = $1", ["text"])
    rules = plpy.execute(rules_plan, [p_strategy])
    
    if not rules:
        return json.dumps({"error": f"No modeling rules found for strategy {p_strategy}"})
    
    rule = rules[0]
    target_irr_qtrly = (1 + float(rule['target_irr_net_percentage']))**(1/4) - 1
    life_qtrs = rule['fund_life_years'] * 4
    inv_qtrs = rule['investment_period_years'] * 4
    
    # 2. Get Current Portfolio State (Actuals)
    # We need: Remaining Commitment (Uncalled) and Current NAV
    state_query = """
        SELECT 
            p.fund_id,
            p.vintage_year,
            (p.total_commitment_usd - COALESCE(SUM(ABS(cf.investment_paid_in_usd) + ABS(cf.management_fees_usd)), 0)) as uncalled,
            COALESCE((SELECT net_asset_value_usd FROM pe_historical_cash_flows WHERE fund_id = p.fund_id ORDER BY transaction_date DESC LIMIT 1), 0) as current_nav
        FROM pe_portfolio p
        LEFT JOIN pe_historical_cash_flows cf ON p.fund_id = cf.fund_id
        WHERE p.primary_strategy = $1
        GROUP BY p.fund_id, p.vintage_year, p.total_commitment_usd
    """
    state_plan = plpy.prepare(state_query, ["text"])
    funds = plpy.execute(state_plan, [p_strategy])

    # --- C. RUN SIMULATION LOOP ---
    results = []
    current_date = datetime.date.today()
    
    # Clear old forecasts for this strategy
    plpy.execute(f"DELETE FROM pe_forecast_output WHERE strategy = '{p_strategy}'")

    for fund in funds:
        fund_id = fund['fund_id']
        uncalled = float(fund['uncalled'])
        nav = float(fund['current_nav'])
        
        # Calculate Fund Age in Quarters
        vintage_date = datetime.date(fund['vintage_year'], 1, 1)
        age_years = (current_date - vintage_date).days / 365.25
        age_qtrs = int(age_years * 4)
        
        sim_date = current_date

        for q in range(p_quarters_to_project):
            # 1. Advance Time
            sim_date += relativedelta(months=3)
            age_qtrs += 1
            
            # 2. Calculate Rates
            rc = get_rate_contribution(age_qtrs, life_qtrs, inv_qtrs)
            rd = get_rate_distribution(age_qtrs, life_qtrs)
            
            # 3. Calculate Flows
            # Call: Depends on Uncalled Capital & Contribution Rate
            capital_call = uncalled * rc
            uncalled -= capital_call # Decrement uncalled
            
            # Growth: NAV grows by target IRR (or shrinks by J-Curve depreciation if early)
            growth_factor = target_irr_qtrly
            if age_qtrs <= rule['nav_initial_depreciation_qtrs']:
                growth_factor = float(rule['nav_initial_qtr_depreciation']) # Apply J-Curve hit

            # Distribution: Depends on (NAV + New Call) & Distribution Rate
            distribution = (nav * (1 + growth_factor) + capital_call) * rd
            
            # 4. Update NAV (Takahashi Formula)
            # NAV_new = NAV_old * (1+Growth) + Call - Dist
            nav = nav * (1 + growth_factor) + capital_call - distribution
            
            # 5. Store Results
            if capital_call > 100:
                results.append(f"({fund_id}, '{p_strategy}', '{sim_date}', 'Capital Call', {-capital_call})")
            if distribution > 100:
                results.append(f"({fund_id}, '{p_strategy}', '{sim_date}', 'Distribution', {distribution})")
            results.append(f"({fund_id}, '{p_strategy}', '{sim_date}', 'NAV', {nav})")

    # --- D. BATCH INSERT RESULTS ---
    if results:
        # Batch insert for performance
        values_str = ",".join(results)
        insert_sql = f"INSERT INTO pe_forecast_output (fund_id, strategy, quarter_date, forecast_type, amount_usd) VALUES {values_str}"
        plpy.execute(insert_sql)
        
    return json.dumps({
        "status": "success", 
        "strategy": p_strategy, 
        "projected_quarters": p_quarters_to_project,
        "rows_generated": len(results)
    })
$$ LANGUAGE plpython3u;