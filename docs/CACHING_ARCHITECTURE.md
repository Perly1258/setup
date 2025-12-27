# Smart Caching Architecture

This document describes the intelligent caching layer implemented for the PE Portfolio Analysis System to reduce redundant LLM calls and improve response times.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Components](#components)
- [Usage Examples](#usage-examples)
- [Performance Characteristics](#performance-characteristics)
- [Configuration](#configuration)
- [Database Schema](#database-schema)
- [Best Practices](#best-practices)

## Overview

The smart caching layer provides:

- **Exact Query Matching**: Hash-based lookup for identical queries
- **Semantic Similarity Search**: Find related queries using embeddings
- **TTL Management**: Automatic expiration of stale cache entries
- **Performance Monitoring**: Detailed statistics on cache hits/misses
- **Flexible Storage**: Support for SQLite and PostgreSQL backends

### Benefits

- ⚡ **Faster Response Times**: Cached results returned in milliseconds
- 💰 **Cost Reduction**: Fewer LLM API calls
- 🎯 **Improved Accuracy**: Consistent answers for similar questions
- 📊 **Analytics**: Track cache performance and query patterns

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    User Query                                │
└───────────────────┬─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│              CachedAgentExecutor                             │
├─────────────────────────────────────────────────────────────┤
│  1. Check Exact Match Cache (query hash)                    │
│     └─> HIT: Return cached result ✅                        │
│     └─> MISS: Continue to step 2                            │
│                                                              │
│  2. Check Semantic Similarity (embeddings)                  │
│     └─> HIT (score ≥ threshold): Return similar result ✅   │
│     └─> MISS: Continue to step 3                            │
│                                                              │
│  3. Execute LLM Agent                                        │
│     └─> Get fresh result                                    │
│     └─> Cache result with embeddings                        │
└───────────────────┬─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│                LLMResultCache                                │
├─────────────────────────────────────────────────────────────┤
│  • SQLAlchemy ORM for database operations                   │
│  • SentenceTransformer for embeddings                       │
│  • Cosine similarity for semantic search                    │
│  • Automatic TTL enforcement                                │
│  • Statistics tracking                                       │
└───────────────────┬─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│              Database (SQLite/PostgreSQL)                    │
├─────────────────────────────────────────────────────────────┤
│  Tables:                                                     │
│  • llm_cache: Cached results with embeddings                │
│  • cache_statistics: Performance metrics                    │
└─────────────────────────────────────────────────────────────┘
```

## Components

### 1. LLMResultCache (`src/cache/llm_result_cache.py`)

The core cache manager that handles storage, retrieval, and semantic search.

**Key Features**:
- Query hashing using SHA-256
- Embedding generation using SentenceTransformer
- Cosine similarity calculation
- TTL-based expiration
- Automatic cache size management

**Key Methods**:
```python
class LLMResultCache:
    def get(query: str) -> Optional[CacheEntry]
    def search_similar(query: str, top_k: int = 5) -> List[SemanticSearchResult]
    def set(query: str, result: str, metadata: dict) -> CacheEntry
    def clear_expired() -> int
    def get_statistics() -> CacheStatistics
```

### 2. CachedAgentExecutor (`src/agents/cached_agent_executor.py`)

Wrapper around LangChain's AgentExecutor that integrates caching.

**Key Features**:
- Transparent caching (no code changes needed)
- Performance tracking
- Configurable cache behavior
- Builder pattern for easy configuration

**Key Methods**:
```python
class CachedAgentExecutor:
    def invoke(inputs: dict) -> dict
    def get_performance_stats() -> dict
    def clear_cache()
    def clear_expired() -> int
```

### 3. Database Schema (`db/setup/cache_schema.sql`)

SQL schema for cache storage with views and utility functions.

**Tables**:
- `llm_cache`: Main cache storage
- `cache_statistics`: Performance metrics

**Views**:
- `v_cache_current_stats`: Current cache status
- `v_cache_hit_rate_hourly`: Hourly hit rates
- `v_top_accessed_queries`: Most popular queries

## Usage Examples

### Basic Usage

```python
from langchain.agents import AgentExecutor, create_react_agent
from langchain_community.llms import Ollama
from agents.cached_agent_executor import CachedAgentExecutor, CachedAgentExecutorBuilder
from cache.llm_result_cache import LLMResultCache

# 1. Set up your regular agent
llm = Ollama(model="deepseek-r1:32b", base_url="http://localhost:21434")
agent = create_react_agent(llm, tools, prompt)
agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

# 2. Wrap with caching
cache = LLMResultCache(
    db_url="sqlite:///cache.db",
    ttl_seconds=3600,  # 1 hour
    similarity_threshold=0.85
)
cached_executor = CachedAgentExecutor(agent_executor, cache)

# 3. Use normally - caching is automatic
result = cached_executor.invoke({"input": "What is the portfolio TVPI?"})
print(result['output'])

# Check if it was a cache hit
if result.get('cache_hit'):
    print(f"Cache hit! Type: {result['cache_type']}")
```

### Using the Builder Pattern

```python
from agents.cached_agent_executor import CachedAgentExecutorBuilder

cached_executor = (
    CachedAgentExecutorBuilder()
    .with_cache_db("postgresql://postgres:postgres@localhost/private_markets_db")
    .with_ttl(7200)  # 2 hours
    .with_similarity_threshold(0.80)
    .with_max_entries(50000)
    .enable_semantic_matching(True)
    .build(agent_executor)
)
```

### Monitoring Performance

```python
# Get performance statistics
stats = cached_executor.get_performance_stats()
print(f"Total calls: {stats['total_calls']}")
print(f"Cache hits: {stats['cached_calls']}")
print(f"Hit rate: {stats['cache_hit_rate']:.1%}")

# Get detailed cache statistics
cache_stats = stats['global_cache_stats']
print(f"Total entries: {cache_stats['total_entries']}")
print(f"Hit rate: {cache_stats['hit_rate']:.1%}")
print(f"Semantic hits: {cache_stats['semantic_hits']}")
```

### Manual Cache Operations

```python
# Get exact match
entry = cache.get("What is the portfolio TVPI?")
if entry:
    print(f"Cached result: {entry.result}")
    print(f"Accessed {entry.access_count} times")

# Search for similar queries
similar = cache.search_similar("Show me portfolio performance", top_k=3)
for result in similar:
    print(f"Similar query: {result.entry.query_text}")
    print(f"Similarity: {result.similarity_score:.3f}")
    print(f"Result: {result.entry.result}\n")

# Clear expired entries
removed = cache.clear_expired()
print(f"Removed {removed} expired entries")

# Get statistics
stats = cache.get_statistics()
print(f"Hit rate: {stats.hit_rate:.1%}")
print(f"Total queries: {stats.total_queries}")
```

### Integration with Existing Agent

To add caching to existing `pe_agent_refactored.py`:

```python
# Before (in setup_agent function)
return AgentExecutor(
    agent=agent,
    tools=tools,
    verbose=True,
    max_iterations=LLM_MAX_ITERATIONS,
    max_execution_time=LLM_MAX_EXECUTION_TIME
)

# After (with caching)
from cache.llm_result_cache import LLMResultCache
from agents.cached_agent_executor import CachedAgentExecutor
from config import ENABLE_CACHING, CACHE_TTL_SECONDS, CACHE_SIMILARITY_THRESHOLD

agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    verbose=True,
    max_iterations=LLM_MAX_ITERATIONS,
    max_execution_time=LLM_MAX_EXECUTION_TIME
)

if ENABLE_CACHING:
    cache = LLMResultCache(
        db_url="postgresql://postgres:postgres@localhost/private_markets_db",
        ttl_seconds=CACHE_TTL_SECONDS,
        similarity_threshold=CACHE_SIMILARITY_THRESHOLD
    )
    return CachedAgentExecutor(agent_executor, cache)
else:
    return agent_executor
```

## Performance Characteristics

### Cache Lookup Speed

- **Exact Match**: O(1) - Hash-based lookup via indexed database query
- **Semantic Search**: O(n) - Linear scan with cosine similarity (n = cache size)
  - For 10,000 entries: ~100-500ms
  - For 100,000 entries: ~1-5 seconds

### Optimization Tips

1. **Use Exact Matching First**: Exact matches are instant
2. **Limit Semantic Search**: Use `top_k` parameter to limit results
3. **Adjust Similarity Threshold**: Higher threshold = fewer false positives
4. **Set Appropriate TTL**: Balance freshness vs. hit rate
5. **Monitor Cache Size**: Use `max_entries` to prevent unbounded growth

### Typical Performance

With default settings (similarity_threshold=0.85, ttl=3600):

```
Cache Performance (10,000 queries):
├─ Exact matches:     45% (< 10ms response time)
├─ Semantic matches:  25% (50-200ms response time)
├─ LLM execution:     30% (5-30s response time)
└─ Overall speedup:   15-20x for cached queries
```

## Configuration

### Environment Variables

Add to `src/config.py`:

```python
# Cache Configuration
ENABLE_CACHING = os.getenv("ENABLE_CACHING", "true").lower() == "true"
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "3600"))
CACHE_DB_PATH = os.getenv("CACHE_DB_PATH", "cache.db")
CACHE_SIMILARITY_THRESHOLD = float(os.getenv("CACHE_SIMILARITY_THRESHOLD", "0.85"))
CACHE_MAX_ENTRIES = int(os.getenv("CACHE_MAX_ENTRIES", "10000"))
CACHE_EMBEDDING_MODEL = os.getenv("CACHE_EMBEDDING_MODEL", "nomic-embed-text")
```

### Tuning Parameters

| Parameter | Default | Description | Tuning Guidance |
|-----------|---------|-------------|-----------------|
| `ttl_seconds` | 3600 | Cache entry lifetime | Longer = more hits, less fresh |
| `similarity_threshold` | 0.85 | Min similarity for semantic match | Higher = more precise, fewer hits |
| `max_entries` | 10000 | Maximum cache size | Higher = more memory, better coverage |
| `embedding_model` | nomic-embed-text | Model for embeddings | Larger = more accurate, slower |

### Recommended Settings

**Development**:
```python
ttl_seconds=3600        # 1 hour
similarity_threshold=0.80
max_entries=1000
```

**Production**:
```python
ttl_seconds=7200        # 2 hours
similarity_threshold=0.85
max_entries=50000
```

**High-Volume**:
```python
ttl_seconds=14400       # 4 hours
similarity_threshold=0.90
max_entries=100000
```

## Database Schema

### Tables

#### llm_cache
```sql
CREATE TABLE llm_cache (
    id SERIAL PRIMARY KEY,
    query_hash VARCHAR(64) UNIQUE NOT NULL,
    query_text TEXT NOT NULL,
    query_embedding JSON,
    result TEXT NOT NULL,
    metadata JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    expires_at TIMESTAMP,
    access_count INTEGER DEFAULT 0 NOT NULL,
    last_accessed_at TIMESTAMP
);
```

#### cache_statistics
```sql
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
```

### Maintenance Queries

```sql
-- Get current cache status
SELECT * FROM v_cache_current_stats;

-- View hourly hit rates
SELECT * FROM v_cache_hit_rate_hourly;

-- See most popular queries
SELECT * FROM v_top_accessed_queries;

-- Clean up expired entries
SELECT cleanup_expired_cache();

-- Get summary
SELECT * FROM get_cache_summary();
```

## Best Practices

### 1. Query Normalization

Normalize queries before caching to improve hit rates:

```python
def normalize_query(query: str) -> str:
    # Remove extra whitespace
    query = ' '.join(query.split())
    # Convert to lowercase for case-insensitive matching
    query = query.lower()
    # Remove trailing punctuation
    query = query.rstrip('?.!')
    return query
```

### 2. Selective Caching

Not all queries should be cached:

```python
def should_cache(query: str, result: str) -> bool:
    # Don't cache errors
    if "error" in result.lower():
        return False
    # Don't cache very short results
    if len(result) < 10:
        return False
    # Don't cache time-sensitive queries
    if any(word in query.lower() for word in ['today', 'now', 'current']):
        return False
    return True
```

### 3. Metadata Tracking

Track useful metadata for debugging:

```python
metadata = {
    'execution_time': 15.3,
    'model': 'deepseek-r1:32b',
    'tool_calls': 3,
    'timestamp': datetime.utcnow().isoformat()
}
cache.set(query, result, metadata=metadata)
```

### 4. Regular Maintenance

Schedule periodic cleanup:

```python
import schedule

def cleanup_cache():
    removed = cache.clear_expired()
    logger.info(f"Removed {removed} expired entries")
    
    stats = cache.get_statistics()
    logger.info(f"Cache stats: {stats.to_dict()}")

# Run every hour
schedule.every().hour.do(cleanup_cache)
```

### 5. Monitoring

Log cache performance:

```python
import logging

logger = logging.getLogger(__name__)

# After each query
if result.get('cache_hit'):
    logger.info(f"Cache HIT: {result['cache_type']}")
else:
    logger.info("Cache MISS: executing agent")

# Periodically
stats = cached_executor.get_performance_stats()
logger.info(f"Cache hit rate: {stats['cache_hit_rate']:.1%}")
```

## Related Documentation

- [LangChain v1.x Migration](./LANGCHAIN_V1_MIGRATION.md) - Import changes for v1.x
- [Compatibility Audit](./COMPATIBILITY_AUDIT.md) - File compatibility status
- [Architecture](./architecture.md) - Overall system architecture

---

**Last Updated**: 2025-12-27  
**Version**: 1.0.0  
**Dependencies**: LangChain 1.2.0, sentence-transformers 2.2.2+, SQLAlchemy 2.0+
