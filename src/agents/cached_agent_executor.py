"""
Cached Agent Executor for LangChain Agents.

This module provides a wrapper around LangChain's AgentExecutor that
integrates with the smart caching layer to reduce redundant LLM calls.
"""

import logging
import time
from typing import Dict, Any, Optional, List

from langchain.agents import AgentExecutor
from langchain_core.agents import AgentAction, AgentFinish

from cache.llm_result_cache import LLMResultCache, CacheEntry, SemanticSearchResult

logger = logging.getLogger(__name__)


class CachedAgentExecutor:
    """
    Wrapper around LangChain AgentExecutor with intelligent caching.
    
    Features:
    - Pre-execution cache checking (exact + semantic)
    - Post-execution result caching
    - Performance monitoring
    - Configurable cache behavior
    """
    
    def __init__(
        self,
        agent_executor: AgentExecutor,
        cache: LLMResultCache,
        enable_exact_match: bool = True,
        enable_semantic_search: bool = True,
        cache_tool_outputs: bool = False,
        metadata_extractor: Optional[callable] = None
    ):
        """
        Initialize cached agent executor.
        
        Args:
            agent_executor: The underlying LangChain AgentExecutor
            cache: LLMResultCache instance for caching
            enable_exact_match: Whether to check exact query matches
            enable_semantic_search: Whether to search for similar queries
            cache_tool_outputs: Whether to cache individual tool outputs (advanced)
            metadata_extractor: Optional function to extract metadata from results
        """
        self.agent_executor = agent_executor
        self.cache = cache
        self.enable_exact_match = enable_exact_match
        self.enable_semantic_search = enable_semantic_search
        self.cache_tool_outputs = cache_tool_outputs
        self.metadata_extractor = metadata_extractor
        
        # Performance tracking
        self.cache_hit_time_saved = 0.0
        self.total_llm_calls = 0
        self.total_cached_calls = 0
        
        logger.info("CachedAgentExecutor initialized")
    
    def invoke(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute agent with caching.
        
        Args:
            inputs: Input dictionary containing 'input' key with query
            
        Returns:
            Output dictionary with 'output' key containing result
        """
        query = inputs.get('input', '')
        
        if not query:
            return self.agent_executor.invoke(inputs)
        
        # Step 1: Check exact match cache
        if self.enable_exact_match:
            cached_entry = self.cache.get(query)
            if cached_entry:
                self.total_cached_calls += 1
                logger.info(f"✅ Cache HIT (exact): {query[:50]}...")
                
                return {
                    'input': query,
                    'output': cached_entry.result,
                    'cache_hit': True,
                    'cache_type': 'exact',
                    'access_count': cached_entry.access_count
                }
        
        # Step 2: Check semantic similarity cache
        if self.enable_semantic_search:
            similar_results = self.cache.search_similar(query, top_k=1)
            
            if similar_results:
                best_match = similar_results[0]
                self.total_cached_calls += 1
                logger.info(
                    f"✅ Cache HIT (semantic, score={best_match.similarity_score:.3f}): "
                    f"{query[:50]}..."
                )
                
                return {
                    'input': query,
                    'output': best_match.entry.result,
                    'cache_hit': True,
                    'cache_type': 'semantic',
                    'similarity_score': best_match.similarity_score,
                    'similar_query': best_match.entry.query_text,
                    'access_count': best_match.entry.access_count
                }
        
        # Step 3: No cache hit - execute agent
        logger.info(f"❌ Cache MISS: {query[:50]}... (executing agent)")
        
        start_time = time.time()
        result = self.agent_executor.invoke(inputs)
        execution_time = time.time() - start_time
        
        self.total_llm_calls += 1
        
        # Step 4: Cache the result
        output = result.get('output', '')
        if output:
            metadata = {
                'execution_time': execution_time,
                'timestamp': time.time()
            }
            
            # Extract additional metadata if extractor provided
            if self.metadata_extractor:
                try:
                    extra_metadata = self.metadata_extractor(result)
                    metadata.update(extra_metadata)
                except Exception as e:
                    logger.warning(f"Metadata extraction failed: {e}")
            
            self.cache.set(query, output, metadata=metadata)
            logger.info(f"💾 Cached result for: {query[:50]}...")
        
        # Add cache info to result
        result['cache_hit'] = False
        result['execution_time'] = execution_time
        
        return result
    
    def run(self, query: str) -> str:
        """
        Legacy compatibility method (LangChain v0.x style).
        
        Args:
            query: The input query string
            
        Returns:
            The output string
        """
        result = self.invoke({'input': query})
        return result.get('output', '')
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """
        Get performance statistics for this executor.
        
        Returns:
            Dictionary with performance metrics
        """
        cache_stats = self.cache.get_statistics()
        
        total_calls = self.total_llm_calls + self.total_cached_calls
        cache_hit_rate = (
            self.total_cached_calls / total_calls 
            if total_calls > 0 
            else 0.0
        )
        
        return {
            'total_calls': total_calls,
            'llm_calls': self.total_llm_calls,
            'cached_calls': self.total_cached_calls,
            'cache_hit_rate': cache_hit_rate,
            'global_cache_stats': cache_stats.to_dict()
        }
    
    def clear_cache(self):
        """Clear all cached results."""
        self.cache.clear_all()
        logger.info("Cache cleared")
    
    def clear_expired(self) -> int:
        """
        Remove expired cache entries.
        
        Returns:
            Number of entries removed
        """
        return self.cache.clear_expired()


class CachedAgentExecutorBuilder:
    """
    Builder pattern for creating CachedAgentExecutor instances.
    
    Simplifies configuration and initialization.
    """
    
    def __init__(self):
        self._cache_db_url = "sqlite:///cache.db"
        self._ttl_seconds = 3600
        self._similarity_threshold = 0.85
        self._embedding_model = "nomic-embed-text"
        self._max_entries = 10000
        self._enable_exact_match = True
        self._enable_semantic_search = True
        self._cache_tool_outputs = False
        self._metadata_extractor = None
    
    def with_cache_db(self, db_url: str) -> 'CachedAgentExecutorBuilder':
        """Set cache database URL."""
        self._cache_db_url = db_url
        return self
    
    def with_ttl(self, ttl_seconds: int) -> 'CachedAgentExecutorBuilder':
        """Set cache TTL in seconds."""
        self._ttl_seconds = ttl_seconds
        return self
    
    def with_similarity_threshold(self, threshold: float) -> 'CachedAgentExecutorBuilder':
        """Set semantic similarity threshold."""
        self._similarity_threshold = threshold
        return self
    
    def with_embedding_model(self, model: str) -> 'CachedAgentExecutorBuilder':
        """Set embedding model name."""
        self._embedding_model = model
        return self
    
    def with_max_entries(self, max_entries: int) -> 'CachedAgentExecutorBuilder':
        """Set maximum cache entries."""
        self._max_entries = max_entries
        return self
    
    def enable_exact_matching(self, enable: bool) -> 'CachedAgentExecutorBuilder':
        """Enable/disable exact matching."""
        self._enable_exact_match = enable
        return self
    
    def enable_semantic_matching(self, enable: bool) -> 'CachedAgentExecutorBuilder':
        """Enable/disable semantic matching."""
        self._enable_semantic_search = enable
        return self
    
    def with_metadata_extractor(self, extractor: callable) -> 'CachedAgentExecutorBuilder':
        """Set metadata extractor function."""
        self._metadata_extractor = extractor
        return self
    
    def build(self, agent_executor: AgentExecutor) -> CachedAgentExecutor:
        """
        Build the CachedAgentExecutor.
        
        Args:
            agent_executor: The underlying AgentExecutor to wrap
            
        Returns:
            Configured CachedAgentExecutor instance
        """
        cache = LLMResultCache(
            db_url=self._cache_db_url,
            ttl_seconds=self._ttl_seconds,
            similarity_threshold=self._similarity_threshold,
            embedding_model=self._embedding_model,
            max_entries=self._max_entries,
            enable_semantic_search=self._enable_semantic_search
        )
        
        return CachedAgentExecutor(
            agent_executor=agent_executor,
            cache=cache,
            enable_exact_match=self._enable_exact_match,
            enable_semantic_search=self._enable_semantic_search,
            cache_tool_outputs=self._cache_tool_outputs,
            metadata_extractor=self._metadata_extractor
        )
