import logging
import sys
import os
import nest_asyncio
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from contextlib import asynccontextmanager

# LlamaIndex Imports
from llama_index.core.agent import ReActAgent
from llama_index.core.tools import QueryEngineTool, ToolMetadata
from llama_index.llms.ollama import Ollama
from llama_index.core import Settings

# Import your existing modules
# Ensure pdf_rag_module.py and sql_rag_module.py are in the same folder
try:
    from pdf_rag_module import setup_environment_and_engine as get_pdf_engine
    from sql_rag_module import get_sql_query_engine
except ImportError as e:
    print(f"❌ Critical Import Error: {e}")
    print("Ensure you are running this script from the /workspace/setup/src/ directory!")
    sys.exit(1)

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("RAG_API")

# Apply Asyncio Patch
nest_asyncio.apply()

# --- CONFIGURATION ---
PORT = 9000
HOST = "0.0.0.0"
MODEL_ID = "mistral-financial-rag" # Name visible in Open WebUI

# Dynamic Ollama URL
OLLAMA_URL = os.environ.get("OLLAMA_HOST", "http://localhost:21434").strip()
if not OLLAMA_URL.startswith("http"):
    OLLAMA_URL = f"http://{OLLAMA_URL}"

# Global Agent
rag_agent = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup Logic: Initialize the Brain"""
    global rag_agent
    logger.info(f"⏳ Starting RAG Agent... (Ollama: {OLLAMA_URL})")
    
    try:
        # 1. Set Global LLM
        Settings.llm = Ollama(model="mistral", base_url=OLLAMA_URL, request_timeout=120.0)
        logger.info("✅ LLM Initialized")
        
        # 2. Load SQL Tool
        # get_sql_query_engine returns (engine, tool). We just need the tool usually, 
        # but let's verify what it returns based on your module.
        # Assuming it returns (query_engine, tool_obj) based on previous files.
        try:
            _, sql_tool = get_sql_query_engine()
            logger.info("✅ SQL Tool Ready")
        except Exception as e:
             logger.error(f"❌ SQL Tool Failed: {e}")
             raise e

        # 3. Load PDF Tool
        try:
            pdf_engine = get_pdf_engine()
            pdf_tool = QueryEngineTool(
                query_engine=pdf_engine,
                metadata=ToolMetadata(
                    name="pdf_docs",
                    description="Reads PDF documents for definitions, strategies, and text analysis.",
                ),
            )
            logger.info("✅ PDF Tool Ready")
        except Exception as e:
             logger.error(f"❌ PDF Tool Failed: {e}")
             raise e
        
        # 4. Create Agent
        try:
            rag_agent = ReActAgent.from_tools(
                [sql_tool, pdf_tool],
                llm=Settings.llm,
                verbose=True,
                context="You are a Financial Expert. Use 'sql_table_tool' for numbers/db data and 'pdf_docs' for text/concepts."
            )
            logger.info(f"🚀 Agent '{MODEL_ID}' is LIVE on Port {PORT}!")
        except Exception as e:
            logger.error(f"❌ Agent Creation Failed (from_tools): {e}")
            raise e
        
    except Exception as e:
        logger.error(f"❌ Startup Failed: {e}")
    
    yield
    logger.info("🛑 Shutting down.")

app = FastAPI(title="Simple RAG API", lifespan=lifespan)

# --- DATA MODELS ---
class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    model: str
    messages: List[Message]

# --- ENDPOINTS ---

@app.get("/v1/models")
async def list_models():
    return {
        "object": "list",
        "data": [{"id": MODEL_ID, "object": "model", "owned_by": "user"}]
    }

@app.post("/v1/chat/completions")
async def chat(request: ChatRequest):
    global rag_agent
    if not rag_agent:
        raise HTTPException(status_code=503, detail="Agent not ready")

    query = request.messages[-1].content
    logger.info(f"📩 Query: {query}")

    try:
        response = rag_agent.chat(query)
        return {
            "id": "chatcmpl-rag",
            "object": "chat.completion",
            "model": request.model,
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": str(response)},
                "finish_reason": "stop"
            }]
        }
    except Exception as e:
        logger.error(f"⚠️ Agent Error: {e}")
        return {
            "id": "error",
            "choices": [{
                "message": {"role": "assistant", "content": f"Error: {str(e)}"}
            }]
        }

if __name__ == "__main__":
    import uvicorn
    import asyncio
    
    # Robust startup using existing loop
    config = uvicorn.Config(app, host=HOST, port=PORT)
    server = uvicorn.Server(config)
    loop = asyncio.get_event_loop()
    loop.run_until_complete(server.serve())