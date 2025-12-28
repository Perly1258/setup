-- Table to store calculated metrics for caching and analysis
-- This table persists the results of calculation engines (TVPI, DPI, IRR, etc.)

CREATE TABLE IF NOT EXISTS pe_computed_metrics (
    metric_id SERIAL PRIMARY KEY,
    calculation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    hierarchy_level VARCHAR(20) NOT NULL, -- 'PORTFOLIO', 'STRATEGY', 'SUB_STRATEGY', 'FUND'
    entity_id VARCHAR(100), -- Fund ID (as string) or Strategy Name
    paid_in NUMERIC,
    distributions NUMERIC,
    total_value NUMERIC,
    current_nav NUMERIC,
    tvpi NUMERIC,
    dpi NUMERIC,
    rvpi NUMERIC,
    irr NUMERIC,
    metrics_json JSONB -- Catch-all for extra data like dates, counts, etc.
);

-- Index for fast retrieval by entity
CREATE INDEX IF NOT EXISTS idx_metrics_lookup ON pe_computed_metrics(hierarchy_level, entity_id);
CREATE INDEX IF NOT EXISTS idx_metrics_date ON pe_computed_metrics(calculation_date);

COMMENT ON TABLE pe_computed_metrics IS 'Stores calculated Private Equity metrics (TVPI, DPI, IRR) for historical tracking and fast retrieval';
