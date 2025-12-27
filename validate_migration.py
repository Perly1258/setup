#!/usr/bin/env python3
"""
Validation script for LangChain v1.x compatibility and caching integration.

This script tests:
1. LangChain v1 API imports
2. Cache module functionality
3. Cached agent executor integration
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_langchain_imports():
    """Test that all LangChain v1 API imports work."""
    print("=" * 70)
    print("TEST 1: LangChain v1 API Imports")
    print("=" * 70)
    
    try:
        from langchain_community.llms import Ollama
        print("✅ langchain_community.llms.Ollama")
    except ImportError as e:
        print(f"❌ langchain_community.llms.Ollama: {e}")
        return False
    
    try:
        from langchain_core.tools import tool, Tool
        print("✅ langchain_core.tools.tool")
        print("✅ langchain_core.tools.Tool")
    except ImportError as e:
        print(f"❌ langchain_core.tools: {e}")
        return False
    
    try:
        from langchain_core.prompts import PromptTemplate
        print("✅ langchain_core.prompts.PromptTemplate")
    except ImportError as e:
        print(f"❌ langchain_core.prompts.PromptTemplate: {e}")
        return False
    
    try:
        from langchain.agents import AgentExecutor, create_react_agent
        print("✅ langchain.agents.AgentExecutor")
        print("✅ langchain.agents.create_react_agent")
    except ImportError as e:
        print(f"⚠️  langchain.agents: {e}")
        print("   Note: AgentExecutor requires LangChain 0.3.x")
        print("   Run: pip install 'langchain>=0.3.0,<1.0.0'")
        return False
    
    print("\n✅ All LangChain v1 API imports successful!\n")
    return True


def test_cache_module():
    """Test cache module functionality."""
    print("=" * 70)
    print("TEST 2: Cache Module Functionality")
    print("=" * 70)
    
    try:
        from cache.llm_result_cache import LLMResultCache, CacheEntry, CacheStatistics
        print("✅ Cache module imports successful")
    except ImportError as e:
        print(f"❌ Cache module import failed: {e}")
        return False
    
    # Test cache initialization
    try:
        cache = LLMResultCache(
            db_url='sqlite:///test_validation_cache.db',
            ttl_seconds=3600,
            enable_semantic_search=False  # Disable to avoid sentence-transformers dependency
        )
        print("✅ Cache initialized")
    except Exception as e:
        print(f"❌ Cache initialization failed: {e}")
        return False
    
    # Test basic operations
    try:
        # Set a value
        entry = cache.set(
            query="What is the portfolio TVPI?",
            result="The portfolio TVPI is 1.45x",
            metadata={"test": True}
        )
        print(f"✅ Cache set: {entry.query_text[:30]}...")
        
        # Get the value
        retrieved = cache.get("What is the portfolio TVPI?")
        if retrieved and retrieved.result == "The portfolio TVPI is 1.45x":
            print(f"✅ Cache get: {retrieved.result}")
        else:
            print("❌ Cache get failed: value mismatch")
            return False
        
        # Get statistics
        stats = cache.get_statistics()
        print(f"✅ Cache statistics: {stats.total_queries} queries, {stats.hit_rate:.1%} hit rate")
        
        # Clean up
        cache.close()
        os.remove('test_validation_cache.db')
        print("✅ Cache cleanup successful")
        
    except Exception as e:
        print(f"❌ Cache operations failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n✅ All cache module tests passed!\n")
    return True


def test_config():
    """Test configuration module."""
    print("=" * 70)
    print("TEST 3: Configuration Module")
    print("=" * 70)
    
    try:
        from config import (
            ENABLE_CACHING,
            CACHE_TTL_SECONDS,
            CACHE_SIMILARITY_THRESHOLD,
            CACHE_MAX_ENTRIES,
            CACHE_EMBEDDING_MODEL
        )
        print(f"✅ ENABLE_CACHING: {ENABLE_CACHING}")
        print(f"✅ CACHE_TTL_SECONDS: {CACHE_TTL_SECONDS}")
        print(f"✅ CACHE_SIMILARITY_THRESHOLD: {CACHE_SIMILARITY_THRESHOLD}")
        print(f"✅ CACHE_MAX_ENTRIES: {CACHE_MAX_ENTRIES}")
        print(f"✅ CACHE_EMBEDDING_MODEL: {CACHE_EMBEDDING_MODEL}")
    except Exception as e:
        print(f"❌ Config import failed: {e}")
        return False
    
    print("\n✅ Configuration module tests passed!\n")
    return True


def test_agent_files_syntax():
    """Test that agent files have valid Python syntax."""
    print("=" * 70)
    print("TEST 4: Agent Files Syntax Check")
    print("=" * 70)
    
    agent_files = [
        'src/pe_agent.py',
        'src/pe_agent_refactored.py',
        'src/temp_agent.py'
    ]
    
    import py_compile
    
    for filepath in agent_files:
        try:
            py_compile.compile(filepath, doraise=True)
            print(f"✅ {filepath}")
        except py_compile.PyCompileError as e:
            print(f"❌ {filepath}: {e}")
            return False
    
    print("\n✅ All agent files have valid syntax!\n")
    return True


def main():
    """Run all validation tests."""
    print("\n")
    print("=" * 70)
    print("LangChain v1.x Compatibility & Caching Validation")
    print("=" * 70)
    print()
    
    results = []
    
    # Test 1: LangChain imports
    results.append(("LangChain v1 API Imports", test_langchain_imports()))
    
    # Test 2: Cache module
    results.append(("Cache Module", test_cache_module()))
    
    # Test 3: Configuration
    results.append(("Configuration", test_config()))
    
    # Test 4: Syntax check
    results.append(("Agent Files Syntax", test_agent_files_syntax()))
    
    # Summary
    print("=" * 70)
    print("VALIDATION SUMMARY")
    print("=" * 70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All validation tests passed!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. See details above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
