"""
LLM Result Cache with Semantic Search.

This module implements an intelligent caching layer for LLM results that supports:
- Exact query matching via hashing
- Semantic similarity search for related queries
- TTL-based cache expiration
- Performance monitoring and statistics
- SQLite/PostgreSQL backend support
"""

import hashlib
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path

import numpy as np
from sqlalchemy import (
    create_engine, Column, Integer, String, Float, DateTime, Text, JSON, Index
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

# For embeddings
try:
    from sentence_transformers import SentenceTransformer
    EMBEDDINGS_AVAILABLE = True
except ImportError:
    EMBEDDINGS_AVAILABLE = False
    logging.warning("sentence-transformers not available. Semantic search will be disabled.")

logger = logging.getLogger(__name__)

Base = declarative_base()


# ==============================================================================
# DATABASE MODELS
# ==============================================================================

class CachedResult(Base):
    """Database model for cached LLM results."""
    __tablename__ = 'llm_cache'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    query_hash = Column(String(64), unique=True, index=True, nullable=False)
    query_text = Column(Text, nullable=False)
    query_embedding = Column(JSON, nullable=True)  # Stored as JSON array
    result = Column(Text, nullable=False)
    metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=True, index=True)
    access_count = Column(Integer, default=0, nullable=False)
    last_accessed_at = Column(DateTime, nullable=True)
    
    __table_args__ = (
        Index('idx_expires_at', 'expires_at'),
        Index('idx_created_at', 'created_at'),
    )


class CacheStats(Base):
    """Database model for cache statistics."""
    __tablename__ = 'cache_statistics'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    total_queries = Column(Integer, default=0)
    cache_hits = Column(Integer, default=0)
    cache_misses = Column(Integer, default=0)
    semantic_hits = Column(Integer, default=0)
    total_entries = Column(Integer, default=0)
    avg_similarity_score = Column(Float, nullable=True)
    
    __table_args__ = (
        Index('idx_timestamp', 'timestamp'),
    )


# ==============================================================================
# DATA CLASSES
# ==============================================================================

@dataclass
class CacheEntry:
    """Represents a cached LLM result."""
    query_hash: str
    query_text: str
    result: str
    created_at: datetime
    expires_at: Optional[datetime]
    access_count: int
    last_accessed_at: Optional[datetime]
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data['created_at'] = self.created_at.isoformat() if self.created_at else None
        data['expires_at'] = self.expires_at.isoformat() if self.expires_at else None
        data['last_accessed_at'] = self.last_accessed_at.isoformat() if self.last_accessed_at else None
        return data


@dataclass
class SemanticSearchResult:
    """Result from semantic similarity search."""
    entry: CacheEntry
    similarity_score: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'entry': self.entry.to_dict(),
            'similarity_score': self.similarity_score
        }


@dataclass
class CacheStatistics:
    """Cache performance statistics."""
    total_queries: int
    cache_hits: int
    cache_misses: int
    semantic_hits: int
    hit_rate: float
    total_entries: int
    avg_similarity_score: Optional[float]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


# ==============================================================================
# CACHE MANAGER
# ==============================================================================

class LLMResultCache:
    """
    Intelligent cache manager for LLM results with semantic search.
    
    Features:
    - Exact query matching using hash-based lookup
    - Semantic similarity search for related queries
    - Configurable TTL for cache entries
    - Performance monitoring and statistics
    - Support for SQLite and PostgreSQL backends
    """
    
    def __init__(
        self,
        db_url: str = "sqlite:///cache.db",
        ttl_seconds: int = 3600,
        similarity_threshold: float = 0.85,
        embedding_model: str = "nomic-embed-text",
        max_entries: int = 10000,
        enable_semantic_search: bool = True
    ):
        """
        Initialize the cache manager.
        
        Args:
            db_url: Database connection URL (SQLite or PostgreSQL)
            ttl_seconds: Time-to-live for cache entries in seconds
            similarity_threshold: Minimum similarity score for semantic matches
            embedding_model: Name of the embedding model for semantic search
            max_entries: Maximum number of cache entries to keep
            enable_semantic_search: Whether to enable semantic similarity search
        """
        self.db_url = db_url
        self.ttl_seconds = ttl_seconds
        self.similarity_threshold = similarity_threshold
        self.max_entries = max_entries
        self.enable_semantic_search = enable_semantic_search and EMBEDDINGS_AVAILABLE
        
        # Initialize database
        if db_url.startswith("sqlite:"):
            # Use StaticPool for SQLite to avoid threading issues
            self.engine = create_engine(
                db_url,
                connect_args={"check_same_thread": False},
                poolclass=StaticPool
            )
        else:
            self.engine = create_engine(db_url)
        
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
        
        # Initialize embedding model if semantic search is enabled
        self.embedding_model = None
        if self.enable_semantic_search:
            try:
                self.embedding_model = SentenceTransformer(embedding_model)
                logger.info(f"Initialized embedding model: {embedding_model}")
            except Exception as e:
                logger.warning(f"Failed to initialize embedding model: {e}. Semantic search disabled.")
                self.enable_semantic_search = False
        
        # Statistics tracking
        self.total_queries = 0
        self.cache_hits = 0
        self.cache_misses = 0
        self.semantic_hits = 0
        
        logger.info(
            f"LLMResultCache initialized: TTL={ttl_seconds}s, "
            f"Semantic Search={'Enabled' if self.enable_semantic_search else 'Disabled'}"
        )
    
    def _compute_hash(self, query: str) -> str:
        """Compute SHA-256 hash of query text."""
        return hashlib.sha256(query.strip().lower().encode('utf-8')).hexdigest()
    
    def _compute_embedding(self, text: str) -> Optional[List[float]]:
        """Compute embedding vector for text."""
        if not self.embedding_model:
            return None
        
        try:
            embedding = self.embedding_model.encode(text, convert_to_numpy=True)
            return embedding.tolist()
        except Exception as e:
            logger.error(f"Error computing embedding: {e}")
            return None
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Compute cosine similarity between two vectors."""
        v1 = np.array(vec1)
        v2 = np.array(vec2)
        
        dot_product = np.dot(v1, v2)
        norm_product = np.linalg.norm(v1) * np.linalg.norm(v2)
        
        if norm_product == 0:
            return 0.0
        
        return float(dot_product / norm_product)
    
    def get(self, query: str) -> Optional[CacheEntry]:
        """
        Retrieve cached result for exact query match.
        
        Args:
            query: The query text to lookup
            
        Returns:
            CacheEntry if found and not expired, None otherwise
        """
        self.total_queries += 1
        query_hash = self._compute_hash(query)
        
        with self.SessionLocal() as session:
            result = session.query(CachedResult).filter_by(query_hash=query_hash).first()
            
            if not result:
                self.cache_misses += 1
                return None
            
            # Check if expired
            if result.expires_at and datetime.utcnow() > result.expires_at:
                session.delete(result)
                session.commit()
                self.cache_misses += 1
                return None
            
            # Update access stats
            result.access_count += 1
            result.last_accessed_at = datetime.utcnow()
            session.commit()
            
            self.cache_hits += 1
            
            entry = CacheEntry(
                query_hash=result.query_hash,
                query_text=result.query_text,
                result=result.result,
                created_at=result.created_at,
                expires_at=result.expires_at,
                access_count=result.access_count,
                last_accessed_at=result.last_accessed_at,
                metadata=result.metadata
            )
            
            logger.info(f"Cache HIT (exact): {query[:50]}...")
            return entry
    
    def search_similar(
        self,
        query: str,
        top_k: int = 5
    ) -> List[SemanticSearchResult]:
        """
        Search for semantically similar cached queries.
        
        Args:
            query: The query text to search for
            top_k: Number of top similar results to return
            
        Returns:
            List of SemanticSearchResult ordered by similarity (highest first)
        """
        if not self.enable_semantic_search:
            return []
        
        query_embedding = self._compute_embedding(query)
        if not query_embedding:
            return []
        
        with self.SessionLocal() as session:
            # Get all non-expired cached results with embeddings
            now = datetime.utcnow()
            results = session.query(CachedResult).filter(
                (CachedResult.expires_at.is_(None)) | (CachedResult.expires_at > now),
                CachedResult.query_embedding.isnot(None)
            ).all()
            
            # Compute similarities
            similarities = []
            for result in results:
                cached_embedding = result.query_embedding
                if not cached_embedding:
                    continue
                
                similarity = self._cosine_similarity(query_embedding, cached_embedding)
                
                if similarity >= self.similarity_threshold:
                    entry = CacheEntry(
                        query_hash=result.query_hash,
                        query_text=result.query_text,
                        result=result.result,
                        created_at=result.created_at,
                        expires_at=result.expires_at,
                        access_count=result.access_count,
                        last_accessed_at=result.last_accessed_at,
                        metadata=result.metadata
                    )
                    similarities.append(SemanticSearchResult(entry, similarity))
            
            # Sort by similarity (descending) and take top_k
            similarities.sort(key=lambda x: x.similarity_score, reverse=True)
            top_results = similarities[:top_k]
            
            if top_results:
                self.semantic_hits += 1
                logger.info(
                    f"Semantic search found {len(top_results)} matches "
                    f"(best score: {top_results[0].similarity_score:.3f})"
                )
            
            return top_results
    
    def set(
        self,
        query: str,
        result: str,
        metadata: Optional[Dict[str, Any]] = None,
        ttl_override: Optional[int] = None
    ) -> CacheEntry:
        """
        Store a query result in the cache.
        
        Args:
            query: The query text
            result: The LLM result to cache
            metadata: Optional metadata to store with the entry
            ttl_override: Override the default TTL for this entry
            
        Returns:
            The created CacheEntry
        """
        query_hash = self._compute_hash(query)
        embedding = self._compute_embedding(query) if self.enable_semantic_search else None
        
        ttl = ttl_override if ttl_override is not None else self.ttl_seconds
        expires_at = datetime.utcnow() + timedelta(seconds=ttl) if ttl > 0 else None
        
        with self.SessionLocal() as session:
            # Check if entry already exists
            existing = session.query(CachedResult).filter_by(query_hash=query_hash).first()
            
            if existing:
                # Update existing entry
                existing.result = result
                existing.query_embedding = embedding
                existing.metadata = metadata
                existing.expires_at = expires_at
                existing.created_at = datetime.utcnow()
                session.commit()
                
                entry = CacheEntry(
                    query_hash=existing.query_hash,
                    query_text=existing.query_text,
                    result=existing.result,
                    created_at=existing.created_at,
                    expires_at=existing.expires_at,
                    access_count=existing.access_count,
                    last_accessed_at=existing.last_accessed_at,
                    metadata=existing.metadata
                )
            else:
                # Create new entry
                cached_result = CachedResult(
                    query_hash=query_hash,
                    query_text=query,
                    query_embedding=embedding,
                    result=result,
                    metadata=metadata,
                    expires_at=expires_at
                )
                session.add(cached_result)
                session.commit()
                
                entry = CacheEntry(
                    query_hash=cached_result.query_hash,
                    query_text=cached_result.query_text,
                    result=cached_result.result,
                    created_at=cached_result.created_at,
                    expires_at=cached_result.expires_at,
                    access_count=cached_result.access_count,
                    last_accessed_at=cached_result.last_accessed_at,
                    metadata=cached_result.metadata
                )
            
            # Enforce max entries limit
            self._enforce_max_entries(session)
            
            logger.info(f"Cached result for query: {query[:50]}...")
            return entry
    
    def _enforce_max_entries(self, session: Session):
        """Remove oldest entries if cache exceeds max_entries."""
        total = session.query(CachedResult).count()
        
        if total > self.max_entries:
            to_delete = total - self.max_entries
            # Delete least recently accessed entries
            old_entries = (
                session.query(CachedResult)
                .order_by(CachedResult.last_accessed_at.nulls_first(), CachedResult.created_at)
                .limit(to_delete)
                .all()
            )
            
            for entry in old_entries:
                session.delete(entry)
            
            session.commit()
            logger.info(f"Removed {to_delete} old cache entries to enforce max limit")
    
    def clear_expired(self) -> int:
        """
        Remove all expired cache entries.
        
        Returns:
            Number of entries removed
        """
        with self.SessionLocal() as session:
            now = datetime.utcnow()
            expired = session.query(CachedResult).filter(
                CachedResult.expires_at.isnot(None),
                CachedResult.expires_at <= now
            ).all()
            
            count = len(expired)
            for entry in expired:
                session.delete(entry)
            
            session.commit()
            
            if count > 0:
                logger.info(f"Removed {count} expired cache entries")
            
            return count
    
    def clear_all(self):
        """Clear all cache entries."""
        with self.SessionLocal() as session:
            session.query(CachedResult).delete()
            session.commit()
            logger.info("Cleared all cache entries")
    
    def get_statistics(self) -> CacheStatistics:
        """
        Get current cache statistics.
        
        Returns:
            CacheStatistics object with current metrics
        """
        with self.SessionLocal() as session:
            total_entries = session.query(CachedResult).count()
            
            # Calculate average similarity score from recent semantic hits
            avg_similarity = None
            if self.semantic_hits > 0:
                # This is a simplified version - in production you'd track this more accurately
                avg_similarity = self.similarity_threshold
            
            hit_rate = (
                self.cache_hits / self.total_queries 
                if self.total_queries > 0 
                else 0.0
            )
            
            stats = CacheStatistics(
                total_queries=self.total_queries,
                cache_hits=self.cache_hits,
                cache_misses=self.cache_misses,
                semantic_hits=self.semantic_hits,
                hit_rate=hit_rate,
                total_entries=total_entries,
                avg_similarity_score=avg_similarity
            )
            
            # Store stats in database
            stat_entry = CacheStats(
                total_queries=stats.total_queries,
                cache_hits=stats.cache_hits,
                cache_misses=stats.cache_misses,
                semantic_hits=stats.semantic_hits,
                total_entries=stats.total_entries,
                avg_similarity_score=stats.avg_similarity_score
            )
            session.add(stat_entry)
            session.commit()
            
            return stats
    
    def close(self):
        """Clean up resources."""
        self.engine.dispose()
        logger.info("Cache manager closed")
