import os
import sys

# Core LlamaIndex Imports
from llama_index.core import (
    SimpleDirectoryReader, 
    VectorStoreIndex, 
    StorageContext, 
    load_index_from_storage,
    Settings,
    QueryBundle
)
from llama_index.llms.ollama import Ollama
from llama_index.embeddings.ollama import OllamaEmbedding
# Removed: from llama_index.core.response.notebook_utils import display_source_node 

# --- Configuration ---
PDF_DIR = "data"             # Directory containing your PDF documents
STORAGE_DIR = "storage"      # Directory to save the persistent index
OLLAMA_MODEL = "mistral"     # The LLM model name (ensure it's running via Ollama)
EMBEDDING_MODEL = "nomic-embed-text" # The embedding model name

# --- CRITICAL FIX: Explicitly check for OLLAMA_HOST for remote environments ---
# If OLLAMA_HOST is set as an environment variable, use it. Otherwise, use the default.
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434") 

# System prompt to guide the LLM's behavior and prevent "I can't access files" refusals.
SYSTEM_PROMPT = (
    "You are an expert Q&A assistant. Your task is to provide a concise, factual answer to the user's question. "
    "Your answer MUST be derived ONLY from the provided context. If the context does not contain the answer, "
    "you MUST state 'I cannot find a specific answer in the provided documents.' "
    "Do NOT mention files, access, or your training data. Just answer the question based on the text provided below."
)

# 1. Setup the LLM and Embedding Model
print("--- RAG System Initialization ---")
try:
    # Initialize Ollama LLM with the robust system prompt and explicit host URL
    llm = Ollama(
        model=OLLAMA_MODEL, 
        request_timeout=180.0,
        system_prompt=SYSTEM_PROMPT,
        base_url=OLLAMA_HOST # <--- Added explicit host configuration
    )
    
    # Initialize Ollama Embedding Model with explicit host URL
    embed_model = OllamaEmbedding(
        model_name=EMBEDDING_MODEL,
        base_url=OLLAMA_HOST # <--- Added explicit host configuration
    ) 
    
    # Set the global default LLM and Embedding Model for LlamaIndex
    Settings.llm = llm
    Settings.embed_model = embed_model
    
    print(f"🧠 Ollama Models Initialized: LLM ({OLLAMA_MODEL}), Embed ({EMBEDDING_MODEL}) at {OLLAMA_HOST}")
except Exception as e:
    print(f"❌ ERROR: Initialization failed. Please check Ollama server status and ensure models are pulled.")
    print(f"Trace: {e}")
    sys.exit(1)


# 2. Load or Create the Index
index = None
if not os.path.exists(STORAGE_DIR):
    print(f"\n📁 Index storage not found. Creating and saving index to '{STORAGE_DIR}'...")
    
    # 2a. Load the Document
    print(f"📄 Loading documents from directory: {PDF_DIR}...")
    try:
        reader = SimpleDirectoryReader(input_dir=PDF_DIR, required_exts=[".pdf"])
        documents = reader.load_data()
        
        if not documents:
            print(f"❌ ERROR: No PDF documents found in the '{PDF_DIR}' folder.")
            sys.exit(1)
            
        print(f"✅ Loaded {len(documents)} pages/files.")
    except Exception as e:
        print(f"❌ ERROR during document loading: {e}")
        sys.exit(1)

    # 2b. Create Index and Persist (Save)
    print("💾 Creating Vector Index (Embedding documents)... This may take a while.")
    index = VectorStoreIndex.from_documents(documents)
    
    # Create the storage directory if it doesn't exist
    os.makedirs(STORAGE_DIR, exist_ok=True)
    # Save the index to disk
    index.storage_context.persist(persist_dir=STORAGE_DIR)
    print(f"✅ Index created and saved to '{STORAGE_DIR}'.")
    
else:
    # 2c. Load Existing Index
    print(f"\n📂 Loading existing index from storage: {STORAGE_DIR}...")
    try:
        # Recreate the storage context and load the index
        storage_context = StorageContext.from_defaults(persist_dir=STORAGE_DIR)
        index = load_index_from_storage(storage_context)
        print("✅ Index loaded successfully.")
    except Exception as e:
        print(f"❌ ERROR: Could not load index from '{STORAGE_DIR}'. Delete the folder and try again. Trace: {e}")
        sys.exit(1)


# 3. Create Query Engine
# We use as_query_engine with similarity_top_k=5 to retrieve the 5 most relevant chunks (increased from 3).
if index:
    query_engine = index.as_query_engine(similarity_top_k=5)
else:
    print("❌ Critical: Index failed to load or create. Exiting.")
    sys.exit(1)

# 4. Interactive Chat Loop
print("\n--- LlamaIndex RAG Chat Ready ---")
print(f"Chatting with documents in '{PDF_DIR}'. Type 'exit' to quit.")

while True:
    question = input("\nYour Question: ")
    if question.lower() in ["quit", "exit"]:
        print("Goodbye!")
        break
    
    try:
        print("Thinking...")
        
        # Query the engine
        response = query_engine.query(question)
        
        # --- DEBUGGING OUTPUT: Show the context used for the answer ---
        print("\n" + "=" * 50)
        print("RETRIEVED CONTEXT CHUNKS (VERIFICATION)")
        print("=" * 50)
        
        if response.source_nodes:
            for i, node in enumerate(response.source_nodes):
                print(f"--- Chunk {i+1} (Score: {node.score:.2f}) ---")
                # Print the source file name
                file_name = node.metadata.get('file_name', 'N/A')
                print(f"Source File: {file_name}")
                # Print a snippet of the retrieved text
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