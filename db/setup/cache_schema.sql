-- ============================================================================
-- LLM Result Cache Schema
-- ============================================================================
-- 
-- This schema supports the smart caching layer for LLM results.
-- It provides:
-- - Query result caching with exact and semantic matching
-- - Performance statistics tracking
-- - TTL-based expiration
--
-- Compatible with PostgreSQL and SQLite (with minor adjustments)
-- ============================================================================

-- Drop existing tables if they exist
DROP TABLE IF EXISTS cache_statistics CASCADE;
DROP TABLE IF EXISTS llm_cache CASCADE;

-- ============================================================================
-- Table: llm_cache
-- Stores cached LLM query results with embeddings for semantic search
-- ============================================================================
CREATE TABLE llm_cache (
    id SERIAL PRIMARY KEY,
    query_hash VARCHAR(64) UNIQUE NOT NULL,
    query_text TEXT NOT NULL,
    query_embedding JSON,  -- Stored as JSON array of floats
    result TEXT NOT NULL,
    result_metadata JSON,  -- Additional metadata (execution time, etc.) - renamed from 'metadata'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    expires_at TIMESTAMP,
    access_count INTEGER DEFAULT 0 NOT NULL,
    last_accessed_at TIMESTAMP
);

-- Indexes for performance
CREATE INDEX idx_llm_cache_query_hash ON llm_cache(query_hash);
CREATE INDEX idx_llm_cache_expires_at ON llm_cache(expires_at);
CREATE INDEX idx_llm_cache_created_at ON llm_cache(created_at);
-- Compound index for efficient cleanup of expired entries
CREATE INDEX idx_llm_cache_expires_created ON llm_cache(expires_at, created_at) WHERE expires_at IS NOT NULL;

-- ============================================================================
-- Table: cache_statistics
-- Tracks cache performance metrics over time
-- ============================================================================
CREATE TABLE cache_statistics (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    total_queries INTEGER DEFAULT 0,
    cache_hits INTEGER DEFAULT 0,
    cache_misses INTEGER DEFAULT 0,
    semantic_hits INTEGER DEFAULT 0,
    total_entries INTEGER DEFAULT 0,
    avg_similarity_score FLOAT
);

-- Index for time-series queries
CREATE INDEX idx_cache_stats_timestamp ON cache_statistics(timestamp);

-- ============================================================================
-- Functions and Triggers
-- ============================================================================

-- Function to automatically cleanup expired entries
CREATE OR REPLACE FUNCTION cleanup_expired_cache()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM llm_cache
    WHERE expires_at IS NOT NULL 
      AND expires_at < CURRENT_TIMESTAMP;
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- Maintenance Queries
-- ============================================================================

-- View to get current cache statistics
CREATE OR REPLACE VIEW v_cache_current_stats AS
SELECT 
    COUNT(*) as total_entries,
    COUNT(CASE WHEN expires_at IS NOT NULL AND expires_at > CURRENT_TIMESTAMP THEN 1 END) as active_entries,
    COUNT(CASE WHEN expires_at IS NOT NULL AND expires_at <= CURRENT_TIMESTAMP THEN 1 END) as expired_entries,
    SUM(access_count) as total_accesses,
    AVG(access_count) as avg_accesses_per_entry,
    MIN(created_at) as oldest_entry,
    MAX(created_at) as newest_entry,
    MIN(last_accessed_at) as least_recently_accessed,
    MAX(last_accessed_at) as most_recently_accessed
FROM llm_cache;

-- View to get cache hit rate over time (last 24 hours, hourly buckets)
CREATE OR REPLACE VIEW v_cache_hit_rate_hourly AS
SELECT 
    DATE_TRUNC('hour', timestamp) as hour,
    SUM(cache_hits) as total_hits,
    SUM(cache_misses) as total_misses,
    SUM(semantic_hits) as total_semantic_hits,
    SUM(total_queries) as total_queries,
    CASE 
        WHEN SUM(total_queries) > 0 
        THEN ROUND(100.0 * SUM(cache_hits) / SUM(total_queries), 2)
        ELSE 0
    END as hit_rate_percent
FROM cache_statistics
WHERE timestamp >= CURRENT_TIMESTAMP - INTERVAL '24 hours'
GROUP BY DATE_TRUNC('hour', timestamp)
ORDER BY hour DESC;

-- View to get top accessed queries
CREATE OR REPLACE VIEW v_top_accessed_queries AS
SELECT 
    query_text,
    access_count,
    created_at,
    last_accessed_at,
    CASE 
        WHEN expires_at IS NOT NULL AND expires_at > CURRENT_TIMESTAMP THEN 'Active'
        WHEN expires_at IS NOT NULL AND expires_at <= CURRENT_TIMESTAMP THEN 'Expired'
        ELSE 'No Expiry'
    END as status
FROM llm_cache
WHERE access_count > 0
ORDER BY access_count DESC
LIMIT 100;

-- ============================================================================
-- Utility Functions
-- ============================================================================

-- Get cache statistics summary
CREATE OR REPLACE FUNCTION get_cache_summary()
RETURNS TABLE (
    metric VARCHAR,
    value TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 'Total Entries'::VARCHAR, COUNT(*)::TEXT FROM llm_cache
    UNION ALL
    SELECT 'Active Entries'::VARCHAR, COUNT(*)::TEXT FROM llm_cache 
        WHERE expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP
    UNION ALL
    SELECT 'Expired Entries'::VARCHAR, COUNT(*)::TEXT FROM llm_cache 
        WHERE expires_at IS NOT NULL AND expires_at <= CURRENT_TIMESTAMP
    UNION ALL
    SELECT 'Total Accesses'::VARCHAR, SUM(access_count)::TEXT FROM llm_cache
    UNION ALL
    SELECT 'Avg Accesses/Entry'::VARCHAR, ROUND(AVG(access_count), 2)::TEXT FROM llm_cache
    UNION ALL
    SELECT 'Oldest Entry'::VARCHAR, MIN(created_at)::TEXT FROM llm_cache
    UNION ALL
    SELECT 'Newest Entry'::VARCHAR, MAX(created_at)::TEXT FROM llm_cache;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- Comments for Documentation
-- ============================================================================

COMMENT ON TABLE llm_cache IS 'Stores cached LLM query results with embeddings for semantic search';
COMMENT ON COLUMN llm_cache.query_hash IS 'SHA-256 hash of normalized query text for exact matching';
COMMENT ON COLUMN llm_cache.query_embedding IS 'Vector embedding of query for semantic similarity search';
COMMENT ON COLUMN llm_cache.result IS 'Cached LLM response';
COMMENT ON COLUMN llm_cache.result_metadata IS 'Additional metadata like execution time, model info, etc.';
COMMENT ON COLUMN llm_cache.expires_at IS 'Expiration timestamp (NULL = never expires)';
COMMENT ON COLUMN llm_cache.access_count IS 'Number of times this cached result was accessed';

COMMENT ON TABLE cache_statistics IS 'Historical cache performance metrics';
COMMENT ON COLUMN cache_statistics.semantic_hits IS 'Number of hits from semantic similarity search';
COMMENT ON COLUMN cache_statistics.avg_similarity_score IS 'Average similarity score for semantic matches';

-- ============================================================================
-- Sample Queries for Testing
-- ============================================================================

-- Insert a sample cache entry
-- INSERT INTO llm_cache (query_hash, query_text, result, expires_at)
-- VALUES (
--     'abc123',
--     'What is the portfolio TVPI?',
--     'The portfolio TVPI is 1.45x',
--     CURRENT_TIMESTAMP + INTERVAL '1 hour'
-- );

-- Get current cache status
-- SELECT * FROM v_cache_current_stats;

-- Get cache summary
-- SELECT * FROM get_cache_summary();

-- Cleanup expired entries
-- SELECT cleanup_expired_cache();

-- ============================================================================
-- End of Schema
-- ============================================================================
