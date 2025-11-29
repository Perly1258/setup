import sys
import logging
# Import your existing RAG module
from sql_rag_module import get_sql_query_engine

# Configure logging to show only errors/results
logging.basicConfig(level=logging.INFO)

# --- THE GOLDEN SET ---
# A list of questions that MUST always generate correct logic.
# We check the SQL output for specific "Required Keywords".
GOLDEN_TEST_CASES = [
    {
        "name": "Identity Check",
        "question": "List all my funds.",
        "required_sql_fragments": ["SELECT", "pe_portfolio", "fund_name"]
    },
    {
        "name": "Strategy Join Check",
        "question": "Show capital calls for Venture Capital funds.",
        "required_sql_fragments": [
            "JOIN", 
            "pe_portfolio", 
            "primary_strategy = 'Venture Capital'",
            "pe_historical_cash_flows"
        ]
    },
    {
        "name": "Math Check (Inv + Fees)",
        "question": "What are the total capital calls for Alpine Ventures?",
        "required_sql_fragments": [
            "investment_paid_in_usd", 
            "+", 
            "management_fees_usd",
            "SUM"
        ]
    },
    {
        "name": "Logic Trap (Latest NAV)",
        "question": "What is the latest NAV for Buyout funds?",
        "required_sql_fragments": [
            "MAX(transaction_date)", 
            "net_asset_value_usd",
            "SELECT" 
        ]
    }
]

def run_tests():
    print("\n" + "="*50)
    print("--- STARTING RAG REGRESSION TEST ---")
    print("="*50 + "\n")
    
    # Initialize the engine
    try:
        query_engine, _ = get_sql_query_engine()
    except Exception as e:
        print(f"FATAL: Could not initialize RAG engine. Error: {e}")
        sys.exit(1)

    passed = 0
    failed = 0

    for test in GOLDEN_TEST_CASES:
        print(f"Testing: {test['name']}...")
        print(f"  Q: '{test['question']}'")
        
        try:
            # Ask the RAG agent
            response = query_engine.query(test['question'])
            
            # Extract the generated SQL from metadata
            # Note: LlamaIndex stores the generated SQL in metadata['sql_query']
            generated_sql = response.metadata.get("sql_query", "").upper()
            
            if not generated_sql:
                print("  ❌ FAIL: No SQL generated.")
                failed += 1
                continue

            # Verify all required logic fragments exist
            missing_fragments = []
            for frag in test['required_sql_fragments']:
                if frag.upper() not in generated_sql:
                    missing_fragments.append(frag)
            
            if missing_fragments:
                print(f"  ❌ FAIL: Missing logic. SQL did not contain: {missing_fragments}")
                print(f"     Generated SQL: {generated_sql}")
                failed += 1
            else:
                print("  ✅ PASS")
                passed += 1
                
        except Exception as e:
            print(f"  ❌ ERROR: Runtime crash. {e}")
            failed += 1
            
        print("-" * 30)

    print("\n" + "="*50)
    print(f"TEST RESULTS: {passed} PASSED, {failed} FAILED")
    print("="*50)

if __name__ == "__main__":
    run_tests()