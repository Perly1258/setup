"""
Configuration management for PE Portfolio Analysis System.

This module centralizes all configuration settings including database
connection, LLM parameters, and computation defaults.
"""

import os
from typing import Dict, Any


# ==============================================================================
# DATABASE CONFIGURATION
# ==============================================================================

DB_CONFIG: Dict[str, Any] = {
    "dbname": os.getenv("DB_NAME", "private_markets_db"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "postgres"),
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432")
}


# ==============================================================================
# LLM CONFIGURATION
# ==============================================================================

LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-r1:32b")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:21434")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0"))
LLM_MAX_ITERATIONS = int(os.getenv("LLM_MAX_ITERATIONS", "15"))
LLM_MAX_EXECUTION_TIME = int(os.getenv("LLM_MAX_EXECUTION_TIME", "60"))


# ==============================================================================
# COMPUTATION CONFIGURATION
# ==============================================================================

# IRR Calculation Parameters
IRR_MAX_ITERATIONS = 100
IRR_TOLERANCE = 1e-6
IRR_INITIAL_GUESS = 0.1

# Default projection horizon (quarters)
DEFAULT_PROJECTION_QUARTERS = 20  # 5 years

# Hierarchy levels
HIERARCHY_LEVELS = ["PORTFOLIO", "STRATEGY", "SUB_STRATEGY", "FUND"]


# ==============================================================================
# LOGGING CONFIGURATION
# ==============================================================================

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


# ==============================================================================
# CACHE CONFIGURATION
# ==============================================================================

ENABLE_CACHING = os.getenv("ENABLE_CACHING", "true").lower() == "true"
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "3600"))  # 1 hour default
CACHE_DB_PATH = os.getenv("CACHE_DB_PATH", "cache.db")  # SQLite cache database
CACHE_SIMILARITY_THRESHOLD = float(os.getenv("CACHE_SIMILARITY_THRESHOLD", "0.85"))  # Semantic similarity threshold
CACHE_MAX_ENTRIES = int(os.getenv("CACHE_MAX_ENTRIES", "10000"))  # Maximum cache entries
CACHE_EMBEDDING_MODEL = os.getenv("CACHE_EMBEDDING_MODEL", "nomic-embed-text")  # Model for query embeddings
