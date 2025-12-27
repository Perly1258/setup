# LangChain v1.x Migration Guide

This document provides a comprehensive guide for migrating from LangChain v0.x to v1.x in the PE Portfolio Analysis System.

## Table of Contents

- [Overview](#overview)
- [Breaking Changes](#breaking-changes)
- [Import Path Changes](#import-path-changes)
- [Code Pattern Changes](#code-pattern-changes)
- [Migration Checklist](#migration-checklist)
- [Before/After Examples](#beforeafter-examples)
- [Troubleshooting](#troubleshooting)

## Overview

LangChain v1.x introduces significant architectural changes that improve modularity and compatibility. The main changes include:

- **Import reorganization**: Core functionality moved to `langchain_core`
- **Community integrations**: Third-party integrations moved to `langchain_community`
- **Pydantic v2**: Full migration to Pydantic v2 for data validation
- **API consistency**: More consistent method naming and signatures

## Breaking Changes

### 1. Package Structure

LangChain is now split into multiple packages:

- **`langchain-core`**: Core abstractions and base classes
- **`langchain-community`**: Third-party integrations (Ollama, databases, etc.)
- **`langchain`**: Main orchestration package
- **`langchain-ollama`**: DEPRECATED - Use `langchain_community.llms.Ollama` instead

### 2. Required Versions

```txt
langchain==1.2.0
langchain-community==1.2.0
langchain-core>=0.3.0
pydantic>=2.0.0
```

### 3. Method Changes

- `.run()` → `.invoke()` for agent execution
- Pydantic v1 models → Pydantic v2 models

## Import Path Changes

### LLM Integrations

#### ❌ Old (v0.x / deprecated)
```python
from langchain_ollama import OllamaLLM
```

#### ✅ New (v1.x)
```python
from langchain_community.llms import Ollama
```

### Tool Decorators

#### ❌ Old (v0.x)
```python
from langchain.tools import tool
```

#### ✅ New (v1.x)
```python
from langchain_core.tools import tool
```

### Prompts

#### ❌ Old (v0.x)
```python
from langchain.prompts import PromptTemplate
```

#### ✅ New (v1.x)
```python
from langchain_core.prompts import PromptTemplate
```

### Agents

#### ✅ Unchanged
```python
from langchain.agents import AgentExecutor, create_react_agent
```

### Complete Import Mapping Table

| Component | Old Import (v0.x) | New Import (v1.x) |
|-----------|-------------------|-------------------|
| Ollama LLM | `langchain_ollama.OllamaLLM` | `langchain_community.llms.Ollama` |
| Tool Decorator | `langchain.tools.tool` | `langchain_core.tools.tool` |
| Tool Class | `langchain.agents.Tool` | `langchain_core.tools.Tool` |
| PromptTemplate | `langchain.prompts.PromptTemplate` | `langchain_core.prompts.PromptTemplate` |
| AgentExecutor | `langchain.agents.AgentExecutor` | `langchain.agents.AgentExecutor` (unchanged) |
| create_react_agent | `langchain.agents.create_react_agent` | `langchain.agents.create_react_agent` (unchanged) |
| SQLDatabase | `langchain_community.utilities.SQLDatabase` | `langchain_community.utilities.SQLDatabase` (unchanged) |

## Code Pattern Changes

### 1. Agent Execution

#### ❌ Old Pattern (v0.x)
```python
agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)
result = agent_executor.run("What is the portfolio TVPI?")
print(result)  # Direct string output
```

#### ✅ New Pattern (v1.x)
```python
agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)
result = agent_executor.invoke({"input": "What is the portfolio TVPI?"})
print(result['output'])  # Dictionary with 'output' key
```

### 2. Custom LLM Wrapper

#### ❌ Old Pattern (v0.x)
```python
from langchain_ollama import OllamaLLM

class CustomLLM(OllamaLLM):
    def _call(self, prompt: str, stop: List[str] = None, **kwargs) -> str:
        response = super()._call(prompt, stop, **kwargs)
        return clean_response(response)
```

#### ✅ New Pattern (v1.x)
```python
from langchain_community.llms import Ollama

class CustomLLM(Ollama):
    def _call(self, prompt: str, stop: List[str] = None, **kwargs) -> str:
        response = super()._call(prompt, stop, **kwargs)
        return clean_response(response)
```

### 3. Tool Definition

#### ❌ Old Pattern (v0.x)
```python
from langchain.tools import tool

@tool
def get_portfolio_metrics(query: str) -> str:
    """Get portfolio metrics."""
    return calculate_metrics()
```

#### ✅ New Pattern (v1.x)
```python
from langchain_core.tools import tool

@tool
def get_portfolio_metrics(query: str) -> str:
    """Get portfolio metrics."""
    return calculate_metrics()
```

### 4. Tool Class Instantiation

#### ❌ Old Pattern (v0.x)
```python
from langchain.agents import Tool

tool = Tool(
    name="SQL_Query",
    func=run_sql,
    description="Execute SQL queries"
)
```

#### ✅ New Pattern (v1.x)
```python
from langchain_core.tools import Tool

tool = Tool(
    name="SQL_Query",
    func=run_sql,
    description="Execute SQL queries"
)
```

## Migration Checklist

Use this checklist when migrating a file:

- [ ] Update all import statements to v1.x paths
- [ ] Replace `OllamaLLM` with `Ollama`
- [ ] Replace `.run()` with `.invoke()` and update response handling
- [ ] Update custom LLM wrappers to extend `Ollama` instead of `OllamaLLM`
- [ ] Verify tool definitions use `langchain_core.tools`
- [ ] Remove any try/except fallback imports for v0.x compatibility
- [ ] Test the file with the new imports
- [ ] Update type hints if using Pydantic models

## Before/After Examples

### Example 1: pe_agent.py

#### ❌ Before (v0.x)
```python
from langchain_ollama import OllamaLLM
from langchain.agents import AgentExecutor, create_react_agent
from langchain.prompts import PromptTemplate
from langchain.tools import tool

class DeepSeekR1Ollama(OllamaLLM):
    def _call(self, prompt: str, stop: List[str] = None, **kwargs: Any) -> str:
        response = super()._call(prompt, stop, **kwargs)
        return clean_response(response)

@tool
def get_portfolio_overview(dummy_arg: str = "") -> str:
    """Get portfolio metrics."""
    return db_tool.run_sql_func("fn_get_pe_metrics_py", ('PORTFOLIO', None))

# Later in code
result = agent_executor.run("What is the portfolio TVPI?")
```

#### ✅ After (v1.x)
```python
from langchain_community.llms import Ollama
from langchain.agents import AgentExecutor, create_react_agent
from langchain_core.prompts import PromptTemplate
from langchain_core.tools import tool

class DeepSeekR1Ollama(Ollama):
    def _call(self, prompt: str, stop: List[str] = None, **kwargs: Any) -> str:
        response = super()._call(prompt, stop, **kwargs)
        return clean_response(response)

@tool
def get_portfolio_overview(dummy_arg: str = "") -> str:
    """Get portfolio metrics."""
    return db_tool.run_sql_func("fn_get_pe_metrics_py", ('PORTFOLIO', None))

# Later in code
result = agent_executor.invoke({"input": "What is the portfolio TVPI?"})
output = result['output']
```

### Example 2: temp_agent.py (Removing Fallback Imports)

#### ❌ Before (v0.x with fallbacks)
```python
# Try/except pattern for compatibility
try:
    from langchain.agents import Tool, AgentExecutor, create_react_agent
except ImportError:
    try:
        from langchain_core.tools import Tool
        from langchain.agents import AgentExecutor, create_react_agent
    except ImportError:
        from langchain.tools import Tool
        from langchain.agents import AgentExecutor, create_react_agent
```

#### ✅ After (v1.x clean imports)
```python
# Direct v1.x imports - no fallbacks needed
from langchain_core.tools import Tool
from langchain.agents import AgentExecutor, create_react_agent
```

### Example 3: Agent Setup and Execution

#### ❌ Before (v0.x)
```python
def main():
    agent_executor = setup_agent()
    
    questions = [
        "What is the TVPI?",
        "Show me the J-Curve"
    ]
    
    for question in questions:
        try:
            answer = agent_executor.run(question)
            print(f"Answer: {answer}")
        except Exception as e:
            print(f"Error: {e}")
```

#### ✅ After (v1.x)
```python
def main():
    agent_executor = setup_agent()
    
    questions = [
        "What is the TVPI?",
        "Show me the J-Curve"
    ]
    
    for question in questions:
        try:
            result = agent_executor.invoke({"input": question})
            print(f"Answer: {result['output']}")
        except Exception as e:
            print(f"Error: {e}")
```

## Troubleshooting

### Common Errors and Solutions

#### Error: `ImportError: cannot import name 'OllamaLLM'`

**Solution**: Replace `langchain_ollama.OllamaLLM` with `langchain_community.llms.Ollama`

```python
# Before
from langchain_ollama import OllamaLLM
llm = OllamaLLM(model="deepseek-r1:32b")

# After
from langchain_community.llms import Ollama
llm = Ollama(model="deepseek-r1:32b")
```

#### Error: `ImportError: cannot import name 'tool' from 'langchain.tools'`

**Solution**: Import from `langchain_core.tools` instead

```python
# Before
from langchain.tools import tool

# After
from langchain_core.tools import tool
```

#### Error: `AttributeError: 'dict' object has no attribute 'run'`

**Solution**: Use `.invoke()` instead of `.run()`

```python
# Before
result = agent_executor.run(query)

# After
result = agent_executor.invoke({"input": query})
output = result['output']
```

#### Error: Pydantic validation errors

**Solution**: Ensure you're using Pydantic v2 compatible models

```bash
pip install --upgrade pydantic>=2.0.0
```

### Compatibility Testing

To verify your migration:

1. **Import Test**: Verify all imports work
```python
python -c "from langchain_community.llms import Ollama; \
           from langchain_core.tools import tool; \
           from langchain_core.prompts import PromptTemplate; \
           print('✅ All imports successful')"
```

2. **Agent Test**: Run a simple agent query
```python
python -c "from src.pe_agent_refactored import setup_agent; \
           agent = setup_agent(); \
           result = agent.invoke({'input': 'test'}); \
           print('✅ Agent execution successful')"
```

3. **Run Existing Tests**
```bash
python -m pytest tests/ -v
```

## Related Documentation

- [LangChain Official Migration Guide](https://python.langchain.com/docs/guides/development/migrating_chains)
- [Caching Architecture](./CACHING_ARCHITECTURE.md) - Smart caching layer
- [Compatibility Audit](./COMPATIBILITY_AUDIT.md) - File-by-file status

## Support

For issues or questions about the migration:

1. Check the [Troubleshooting](#troubleshooting) section above
2. Review the [Before/After Examples](#beforeafter-examples)
3. Consult the LangChain v1.x official documentation
4. Check existing tests in `/tests` for working examples

---

**Last Updated**: 2025-12-27  
**LangChain Version**: 1.2.0  
**Compatibility**: OpenWebUI 0.6.43, Pydantic 2.x
