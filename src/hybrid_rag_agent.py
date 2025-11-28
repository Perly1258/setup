import os
import sys
import logging
from llama_index.core import Settings
from llama_index.core.query_engine import RouterQueryEngine
from llama_index.core.tools import QueryEngineTool
from llama_index.core.selectors import LLMSingleSelector 
from llama_index.llms.ollama import Ollama
from llama_index.embeddings.ollama import OllamaEmbedding

# Import the two modular RAG components
from pdf_rag_module import get_vector_query_engine
from sql_rag_module import get_sql_query_engine

# Configure logging
logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logging.getLogger().addHandler(logging.StreamHandler(stream=sys.stdout))

# --- Configuration ---
OLLAMA_MODEL = "mistral"     
EMBEDDING_MODEL = "nomic-embed-text" 

# Connection string is defined in sql_rag_module, but we need the host for Ollama
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434") 
# Get connection string from SQL module to pass to PDF module
from sql_rag_module import CONNECTION_STRING, DB_NAME

# System prompt to guide the LLM's behavior (Crucial for routing and synthesis)
SYSTEM_PROMPT = (
    "You are a Hybrid Financial Analyst specialized in Private Equity and alternative assets. "
    "Your primary goal is to answer questions using two distinct sources: "
    "1. The 'vector_document_tool' (for definitions, methodology, and unstructured PDF content). "
    "2. The 'sql_table_tool' (for quantitative financial facts, projections, and numerical data). "
    "You MUST use the appropriate tool before synthesizing an answer. "
    "Always reference the source (the specific document or the table data/query used) when possible. "
    "Be concise and professional."
)

# --------------------------------------------------------------------------
# 1. SETUP: LLM, EMBEDDING, & TOOLS
# --------------------------------------------------------------------------

def setup_environment_and_tools():
    """Initializes LLM, embedding model, and both query engines."""
    
    # 1. Initialize LLM and Embedding Model (Running locally via Ollama)
    logger = logging.getLogger(__name__)
    logger.info(f"Initializing LLM ({OLLAMA_MODEL}) and Embedding Model ({EMBEDDING_MODEL})...")
    
    # Set global LlamaIndex settings
    try:
        # INCREASED TIMEOUT to 120.0 seconds for stability on remote hosts (Vast.ai)
        Settings.llm = Ollama(model=OLLAMA_MODEL, base_url=OLLAMA_HOST, system_prompt=SYSTEM_PROMPT, request_timeout=120.0)
        # Using a fixed dimension for the embedding model if necessary, but letting LlamaIndex infer is usually best
        Settings.embed_model = OllamaEmbedding(model_name=EMBEDDING_MODEL, base_url=OLLAMA_HOST)
    except Exception as e:
        logger.error(f"Failed to initialize Ollama LLM or Embedding model. Ensure Ollama service is running and accessible at {OLLAMA_HOST}. Error: {e}")
        sys.exit(1)

    # 2. Get the two specialized tools
    # Structured Data Tool (SQL RAG)
    _, sql_tool = get_sql_query_engine()
    
    # Unstructured Data Tool (PDF RAG)
    vector_query_engine = get_vector_query_engine(CONNECTION_STRING)
    
    # Define the final vector tool using the engine initialized in the separate module
    vector_tool = QueryEngineTool.from_defaults(
        query_engine=vector_query_engine,
        name="vector_document_tool",
        description=(
            "Use this tool for conceptual questions, definitions, rationale, methodology, "
            "or information contained within the external PDF documents (e.g., 'Explain the J-Curve', 'What is the goal of the Yale Model?')."
        )
    )
    
    return sql_tool, vector_tool

def create_hybrid_router(sql_tool: QueryEngineTool, vector_tool: QueryEngineTool) -> RouterQueryEngine:
    """Creates the router to choose between the SQL (structured) and Vector (unstructured) tools."""
    
    # Combine tools into the Router Query Engine
    router_query_engine = RouterQueryEngine(
        selector=LLMSingleSelector.from_defaults(),
        query_engine_tools=[sql_tool, vector_tool]
    )
    
    logging.info("Hybrid Router Query Engine is ready.")
    return router_query_engine

# --------------------------------------------------------------------------
# 2. MAIN CHAT LOOP
# --------------------------------------------------------------------------

if __name__ == "__main__":
    
    # 1. Setup environment and tools
    sql_tool, vector_tool = setup_environment_and_tools()
    
    # 2. Create the Hybrid Router
    query_engine = create_hybrid_router(sql_tool, vector_tool)

    print("\n" + "=" * 50)
    print("--- Hybrid RAG Financial Analyst Ready ---")
    print(f"PostgreSQL DB: {DB_NAME} | LLM: {OLLAMA_MODEL}")
    print("Ask a financial (SQL) or conceptual (PDF) question. Type 'exit' to quit.")
    print("=" * 50)

    while True:
        try:
            question = input("Your Question: ")
            if question.lower() in ["quit", "exit"]:
                print("Goodbye! Shutting down LLM connection.")
                break
            
            print("\nThinking...")
            # Execute the query through the router
            response = query_engine.query(question)
            
            # --- DEBUGGING OUTPUT (To show the routing decision and context used) ---
            print("\n" + "=" * 50)
            print(f"ROUTING DECISION: {response.metadata.get('selector_result', 'N/A')}")
            
            # Show retrieved context 
            if response.source_nodes:
                print("RETRIEVED CONTEXT (VERIFICATION):")
                for i, node in enumerate(response.source_nodes):
                    # Check if the node is a standard VDB node or a SQL result node
                    if node.metadata.get('tool_name') == 'sql_table_tool':
                        print(f"--- Source (SQL Result) ---")
                        print(f"Query Run: {node.metadata.get('sql_query', 'N/A')}")
                        print(f"Result Data: {node.text[:400]}")
                    else:
                        print(f"--- Source (PDF Chunk) ---")
                        print(f"Source File: {node.metadata.get('file_name', 'N/A')}")
                        print(f"Text Snippet:\n{node.text[:400]}...")
                    print("-" * 15)
            else:
                  print("No specific context nodes returned (Synthesis was direct).")
            print("=" * 50)
            
            # --- LLM ANSWER (Final Synthesis) ---
            print(f"💡 LLM Answer: {str(response)}")
            print("-" * 50)
            
        except Exception as e:
            logging.error(f"An error occurred during query: {e}")
            break