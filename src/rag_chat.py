import os
import sys

# --- LlamaIndex/PostgreSQL Imports ---
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from llama_index.core import (
    SimpleDirectoryReader, 
    VectorStoreIndex, 
    StorageContext, 
    Settings,
)
from llama_index.core.node_parser import SentenceSplitter 
from llama_index.llms.ollama import Ollama
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.vector_stores.postgres import PGVectorStore 

# --- Configuration ---
PDF_DIR = "/workspace/setup/pdf"             
OLLAMA_MODEL = "mistral"     
EMBEDDING_MODEL = "nomic-embed-text" 
DB_TABLE_NAME = "rag_documents" 

# --- PostgreSQL Configuration ---
DB_USER = os.environ.get("POSTGRES_USER", "postgres")
DB_PASS = os.environ.get("POSTGRES_PASSWORD", "postgres") 
DB_HOST = os.environ.get("POSTGRES_HOST", "localhost")
DB_PORT = os.environ.get("POSTGRES_PORT", "5432")
DB_NAME = os.environ.get("POSTGRES_DB", "rag_db")

CONNECTION_STRING = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# --- Ollama Configuration ---
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434") 

# System prompt to guide the LLM's behavior
SYSTEM_PROMPT = (
    "You are an expert Q&A assistant. Your task is to provide a concise, factual answer to the user's question. "
    "Your answer MUST be derived ONLY from the provided context. If the context does not contain the answer, "
    "you MUST state 'I cannot find a specific answer in the provided documents.' "
    "Do NOT mention files, access, or your training data. Just answer the question based on the text provided below."
)

# --- Text Cleansing Function ---
def clean_text(text_chunk):
    """Removes NUL characters (0x00) that cause database insertion errors."""
    return text_chunk.replace('\x00', '')
# -----------------------------

# --- 1. Setup the LLM and Embedding Model ---
print("--- RAG System Initialization ---")
try:
    llm = Ollama(
        model=OLLAMA_MODEL, 
        request_timeout=180.0,
        system_prompt=SYSTEM_PROMPT,
        base_url=OLLAMA_HOST
    )
    
    embed_model = OllamaEmbedding(
        model_name=EMBEDDING_MODEL,
        base_url=OLLAMA_HOST
    ) 
    
    Settings.llm = llm
    Settings.embed_model = embed_model
    print(f"🧠 Ollama Models Initialized: LLM ({OLLAMA_MODEL}), Embed ({EMBEDDING_MODEL}) at {OLLAMA_HOST}")

except Exception as e:
    print(f"❌ ERROR: Ollama initialization failed. Check server status and models.")
    print(f"Trace: {e}")
    sys.exit(1)

# --- 2. Setup PostgreSQL Vector Store ---
try:
    print(f"\n🔗 Connecting to PostgreSQL at {DB_HOST}:{DB_PORT}/{DB_NAME}...")
    
    vector_store = PGVectorStore.from_params(
        database=DB_NAME,
        host=DB_HOST,
        password=DB_PASS,
        port=DB_PORT,
        user=DB_USER,
        table_name=DB_TABLE_NAME,
        embed_dim=768, 
        hnsw_kwargs={"hnsw_m": 16, "hnsw_ef_construction": 128, "hnsw_ef_search": 64}, 
        perform_setup=True 
    )
    
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    print(f"✅ PostgreSQL Vector Store Initialized with table '{DB_TABLE_NAME}'.")

except Exception as e:
    print(f"❌ ERROR: PostgreSQL connection/setup failed. Ensure the server is running, database exists, and 'vector' extension is enabled.")
    print(f"Trace: {e}")
    sys.exit(1)

# --- 3. Load or Create the Index ---
index = None
try:
    # Use SQLAlchemy to check table emptiness
    engine = create_engine(CONNECTION_STRING)
    with Session(engine) as session:
        
        count_query_text = text(f"SELECT COUNT(*) FROM {DB_TABLE_NAME};") 
        
        try:
            result = session.execute(count_query_text).scalar_one_or_none()
            table_row_count = result if result is not None else 0
        except Exception:
            # If the table doesn't exist yet (UndefinedTable error), treat count as 0
            table_row_count = 0


    # Determine if documents need to be loaded
    if table_row_count == 0:
        print("\n📁 Vector table is empty. Loading and embedding documents...")
        
        # Load the Document
        reader = SimpleDirectoryReader(input_dir=PDF_DIR, required_exts=[".pdf"])
        documents = reader.load_data()
        
        if not documents:
            print(f"❌ ERROR: No PDF documents found in the '{PDF_DIR}' folder.")
            sys.exit(1)

        # 🚨 FIX: Clean the text of the documents using set_content()
        print("🧼 Applying text cleansing to documents...")
        for doc in documents:
            doc.set_content(clean_text(doc.text))
        
        # Define the Node Parser 
        parser = SentenceSplitter(
            chunk_size=1024,
            chunk_overlap=20,
        )
        print("🧹 Cleaning and chunking documents...")
        # Get nodes from the now-cleaned documents
        nodes = parser.get_nodes_from_documents(documents)
        
        # Create Index (inserts data into Postgres)
        print("💾 Creating Vector Index (Embedding cleaned documents and storing in Postgres)...")
        index = VectorStoreIndex(
            nodes, 
            storage_context=storage_context, 
            show_progress=True
        )
        print("✅ Documents indexed and stored successfully in PostgreSQL.")
    
    else:
        print(f"📂 Existing data ({table_row_count} rows) found in PostgreSQL. Index loaded for querying.")
        index = VectorStoreIndex.from_vector_store(vector_store=vector_store)

except Exception as e:
    print(f"❌ ERROR during indexing or loading: {e}")
    sys.exit(1)


# --- 4. Create Query Engine and Interactive Chat Loop ---
if index:
    query_engine = index.as_query_engine(similarity_top_k=5)

    print("\n--- LlamaIndex RAG Chat Ready ---")
    print(f"Querying data stored in PostgreSQL table '{DB_TABLE_NAME}'. Type 'exit' to quit.")

    while True:
        question = input("\nYour Question: ")
        if question.lower() in ["quit", "exit"]:
            print("Goodbye!")
            break
        
        try:
            print("Thinking...")
            response = query_engine.query(question)
            
            # --- DEBUGGING OUTPUT: Show the context used for the answer ---
            print("\n" + "=" * 50)
            print("RETRIEVED CONTEXT CHUNKS (VERIFICATION)")
            print("=" * 50)
            
            if response.source_nodes:
                for i, node in enumerate(response.source_nodes):
                    print(f"--- Chunk {i+1} (Score: {node.score:.2f}) ---")
                    file_name = node.metadata.get('file_name', 'N/A')
                    print(f"Source File: {file_name}")
                    print(f"Text Snippet:\n{node.text[:400]}...")
                    print("-" * 15)
            else:
                  print("No relevant context found.")
            print("=" * 50)
            
            # --- MISTRAL ANSWER ---
            print(f"\n💡 Mistral Answer: {str(response)}")
            print("-" * 50)
            
        except Exception as e:
            print(f"An error occurred during query: {e}")
            break
else:
    print("❌ Critical: Index failed to load or create. Exiting.")
    sys.exit(1)