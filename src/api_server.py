import os
import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import AsyncGenerator
import asyncio
from contextlib import asynccontextmanager

# NOTE: This imports the setup_environment_and_engine function from your core RAG logic file.
# We are assuming 'pdf_rag_module.py' is located at the project root,
# which allows it to be imported from the 'src' subdirectory.
try:
    from pdf_rag_module import setup_environment_and_engine 
except ImportError:
    # Fallback assumption if both files were placed in the 'src' directory (less likely)
    from .pdf_rag_module import setup_environment_and_engine 

# 2. CONFIGURATION
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- API Setup ---
query_engine = None

class QueryRequest(BaseModel):
    """Schema for the incoming query request."""
    query: str

class QueryResponse(BaseModel):
    """Schema for the outgoing query response (non-streaming)."""
    response: str
    
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Handles startup and shutdown events.
    Loads the LlamaIndex query engine on startup.
    """
    global query_engine
    
    logger.info("Starting RAG API Server...")
    try:
        # Run the synchronous initialization function in a separate thread
        # This function connects to Ollama and PostgreSQL and loads/creates the index.
        query_engine = await asyncio.to_thread(setup_environment_and_engine)
        logger.info("✅ RAG Engine Loaded and Ready!")
    except Exception as e:
        # Log the error but allow the app to start so the user can see the health check
        logger.error(f"❌ Failed to initialize RAG engine. Check Ollama and PostgreSQL status: {e}")
        query_engine = None

    yield  # Application is running

    logger.info("Shutting down RAG API Server.")

# Initialize FastAPI app with the lifespan context manager
app = FastAPI(
    title="PDF RAG Query API",
    version="1.0.0",
    description="Backend API for querying documents via LlamaIndex, Ollama, and PostgreSQL.",
    lifespan=lifespan
)

@app.get("/health")
def health_check():
    """Endpoint to check if the server is running and the engine is loaded."""
    if query_engine:
        return {"status": "ok", "engine_ready": True}
    return {"status": "initializing", "engine_ready": False, "message": "RAG Engine is not yet loaded or failed to connect to dependencies."}

@app.post("/query", response_model=QueryResponse)
async def query_rag(request: QueryRequest):
    """
    Processes a user query using the loaded RAG query engine.
    """
    if not query_engine:
        raise HTTPException(status_code=503, detail="RAG Engine is not initialized yet. Check server logs for errors with Ollama or PostgreSQL.")
    
    logger.info(f"Received query: {request.query}")

    try:
        # LlamaIndex query is synchronous, so run it in a thread pool
        response = await asyncio.to_thread(query_engine.query, request.query)
        
        return QueryResponse(response=str(response))
    except Exception as e:
        logger.error(f"Error during query processing: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")