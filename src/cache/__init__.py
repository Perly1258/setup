"""
Smart Caching Layer for LLM Results.

This package provides intelligent caching capabilities for LLM results,
including exact-match and semantic similarity-based cache retrieval.
"""

from .llm_result_cache import (
    LLMResultCache,
    CacheEntry,
    CacheStatistics,
    SemanticSearchResult
)

__all__ = [
    'LLMResultCache',
    'CacheEntry',
    'CacheStatistics',
    'SemanticSearchResult'
]
