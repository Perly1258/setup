import sys
import os
import json
import logging

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))

# Configure logging
logging.basicConfig(level=logging.INFO)

from pe_agent_refactored import get_portfolio_overview, get_db

try:
    print("Running get_portfolio_overview()...")
    result = get_portfolio_overview.invoke({})
    print("\n--- Result ---")
    print(result)
    
    # Parse JSON to check values
    data = json.loads(result)
    if "error" in data:
        print(f"\nError in response: {data['error']}")
    else:
        print(f"\nTVPI: {data.get('tvpi')}")
        print(f"DPI: {data.get('dpi')}")
        print(f"Total Value: {data.get('total_value')}")

except Exception as e:
    print(f"\nException occurred: {e}")
