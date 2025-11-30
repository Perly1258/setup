import sys
import os

# Add current directory to path so we can import modules
sys.path.append(os.getcwd())

try:
    print("⏳ Importing PDF RAG Module...")
    from pdf_rag_module import setup_environment_and_engine
    
    print("⚙️ Initializing Engine...")
    query_engine = setup_environment_and_engine()
    
    print("✅ Engine Ready! Asking test question...")
    response = query_engine.query("What is the investment strategy?")
    
    print("\n" + "="*30)
    print(f"🤖 ANSWER:\n{response}")
    print("="*30 + "\n")



except Exception as e:
    print(f"❌ TEST FAILED: {e}")
    import traceback
    traceback.print_exc()