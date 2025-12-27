# Validation Script

## Purpose

This script validates the LangChain v1.x compatibility migration and smart caching integration.

## Usage

```bash
python3 validate_migration.py
```

## Requirements

Before running, ensure you have the correct LangChain versions installed:

```bash
pip install 'langchain>=0.3.0,<1.0.0' 'langchain-community>=0.3.0,<1.0.0' 'langchain-core>=0.3.0'
```

Or install from requirements.txt:

```bash
pip install -r requirements.txt
```

## Tests

The script runs 4 validation tests:

### 1. LangChain v1 API Imports
Verifies that all necessary LangChain v1 API components can be imported:
- `langchain_community.llms.Ollama`
- `langchain_core.tools.tool` and `Tool`
- `langchain_core.prompts.PromptTemplate`
- `langchain.agents.AgentExecutor` and `create_react_agent`

### 2. Cache Module Functionality
Tests the smart caching layer:
- Module imports
- Cache initialization
- Set/get operations
- Statistics tracking
- Cleanup

### 3. Configuration Module
Validates cache configuration settings:
- `ENABLE_CACHING`
- `CACHE_TTL_SECONDS`
- `CACHE_SIMILARITY_THRESHOLD`
- `CACHE_MAX_ENTRIES`
- `CACHE_EMBEDDING_MODEL`

### 4. Agent Files Syntax Check
Verifies Python syntax for migrated agent files:
- `src/pe_agent.py`
- `src/pe_agent_refactored.py`
- `src/temp_agent.py`

## Expected Output

When all tests pass:
```
======================================================================
VALIDATION SUMMARY
======================================================================
✅ PASS: LangChain v1 API Imports
✅ PASS: Cache Module
✅ PASS: Configuration
✅ PASS: Agent Files Syntax

Total: 4/4 tests passed

🎉 All validation tests passed!
```

## Troubleshooting

### LangChain Imports Fail

If you see:
```
⚠️  langchain.agents: cannot import name 'AgentExecutor'
```

Install the correct LangChain version:
```bash
pip install 'langchain>=0.3.0,<1.0.0' 'langchain-community>=0.3.0,<1.0.0' 'langchain-core>=0.3.0'
```

### Cache Module Fails

Ensure SQLAlchemy and NumPy are installed:
```bash
pip install sqlalchemy>=2.0.0 numpy>=1.24.0
```

### Sentence Transformers Warning

The warning `sentence-transformers not available` is expected during validation.
For full semantic search functionality, install:
```bash
pip install sentence-transformers>=2.2.2
```

## Related Documentation

- [LangChain v1.x Migration Guide](docs/LANGCHAIN_V1_MIGRATION.md)
- [Caching Architecture](docs/CACHING_ARCHITECTURE.md)
- [Compatibility Audit](docs/COMPATIBILITY_AUDIT.md)
