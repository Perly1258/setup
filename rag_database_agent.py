import requests
import json
import time
from typing import List, Dict, Any

# NOTE: You will need to install the PostgreSQL adapter locally: pip install psycopg2-binary
# import psycopg2 

# --- CONFIGURATION (Adjust these for your local PostgreSQL instance) ---
LLM_ENDPOINT = "http://localhost:8080/v1/completions" 
DB_CONFIG = {
    "host": "localhost",
    "database": "private_markets_db", # Replace with your actual database name
    "user": "postgres",               # Replace with your PostgreSQL user
    "password": "your_db_password",   # Replace with your PostgreSQL password
    "port": "5432"
}

# --- QUANTITATIVE MAPPING DICTIONARY ---
# This dictionary translates the qualitative input (NAV_Valuation_Initial_Impact)
# from the SQL table into the actual numeric parameters for a simulation engine.
NAV_PARAMETER_MAP = {
    'Deep Initial Drop': {'nav_impact_pct': -0.015, 'duration_quarters': 8, 'comment': 'Severe J-Curve due to high fees and early write-offs (typical VC).'}, # -1.5% per quarter
    'Moderate Drop':     {'nav_impact_pct': -0.005, 'duration_quarters': 6, 'comment': 'Standard J-Curve dip due to fees and transaction costs (typical PE LBO).'}, # -0.5% per quarter
    'Shallow Initial Drop': {'nav_impact_pct': -0.001, 'duration_quarters': 4, 'comment': 'Minimal J-Curve, offset by early income/yield (typical Real Estate/Secondaries).'}, # -0.1% per quarter
    'Negligible Drop':   {'nav_impact_pct': -0.0001, 'duration_quarters': 2, 'comment': 'Almost no J-Curve effect (typical Infrastructure/Core assets).'}, # ~0% per quarter
    'No J-Curve (Flat)': {'nav_impact_pct': 0.000, 'duration_quarters': 0, 'comment': 'Debt instruments or high yield funds; NAV remains flat/positive immediately.'}
}


# --- UTILITY: CONNECT TO DB (Conceptual Psycopg2 Integration) ---
def get_db_connection():
    """
    Establishes connection to the persistent PostgreSQL database.
    NOTE: In your local environment, you would use 'psycopg2.connect(**DB_CONFIG)'.
    """
    print(f"Attempting to connect to PostgreSQL at {DB_CONFIG['host']}:{DB_CONFIG['port']}...")
    try:
        # --- MOCK CONNECTION START ---
        # Mocking the connection for demonstration since psycopg2 is not installed
        import sqlite3
        conn = sqlite3.connect(":memory:") 
        conn.close() # Close immediately to simulate connection test
        # --- MOCK CONNECTION END ---
        
        # You would use the real connection here:
        # conn = psycopg2.connect(**DB_CONFIG) 
        
        # Returning a functional mock database connection for demonstration purposes
        return MockPostgresConnection() 
        
    except Exception as e:
        print(f"Error connecting to PostgreSQL. Ensure the service is running and credentials are correct.")
        print(f"PostgreSQL Connection Error: {e}")
        return None

# --- MOCK CLASSES (To enable the script to run without psycopg2) ---
class MockPostgresCursor:
    """Mocks the PostgreSQL cursor."""
    def execute(self, query):
        print(f"[DB MOCK] Executing: {query[:80]}...")
        # Simple query parsing to determine mock result
        if "LIMIT 1" in query and "PE_Portfolio" in query:
            self._data = [('Global Buyout Capital X', 32.50)]
            self.description = [('Fund_Name',), ('Total_Commitment_MM_USD',)]
        elif "SUM" in query:
            self._data = [(-0.08,)]
            self.description = [('sum',)]
        elif "Vintage_Year = 2024" in query:
            self._data = [('Frontier HealthTech II',), ('Innovation Seed Fund I',), ('CyberSec Accelerator I',)]
            self.description = [('Fund_Name',)]
        elif "NAV_Valuation_Initial_Impact" in query and "Private Equity" in query:
             self._data = [('Private Equity', 'Moderate Drop')]
             self.description = [('Primary_Strategy',), ('NAV_Valuation_Initial_Impact',)]
        else:
            self._data = [('Mock Result',)]
            self.description = [('mock_column',)]

    def fetchall(self):
        return self._data
    
    @property
    def description(self):
        return self._description
    
    @description.setter
    def description(self, value):
        self._description = value

class MockPostgresConnection:
    """Mocks the PostgreSQL connection."""
    def cursor(self):
        return MockPostgresCursor()
    def close(self):
        print("Mock PostgreSQL connection closed.")

# --- LLM INTERACTION (Modified for Local Model API Call) ---

def query_llm(prompt: str) -> str:
    """
    Makes a POST request to the local LLM endpoint (Mistral/Vast.ai).
    """
    headers = {'Content-Type': 'application/json'}
    payload = {
        "prompt": prompt,
        "max_tokens": 500,
        "temperature": 0.0,
        "stop": ["\n\n", ";"]
    }

    try:
        response = requests.post(LLM_ENDPOINT, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        
        result_data = response.json()
        
        if 'choices' in result_data and result_data['choices']:
            return result_data['choices'][0]['text'].strip()
        
        return result_data.get('text', 'Error: LLM returned unexpected format.')

    except requests.exceptions.RequestException as e:
        print(f"\n[LLM Connection FAILED]: Ensure your local model is running at {LLM_ENDPOINT}")
        print(f"Using MOCK response instead of API call. Error: {e}")
        
        # --- MOCK RESPONSE (Fallback for demonstration) ---
        if "largest total commitment" in prompt.lower():
            return "SELECT T1.Fund_Name, T1.Total_Commitment_MM_USD FROM PE_Portfolio AS T1 ORDER BY T1.Total_Commitment_MM_USD DESC LIMIT 1;"
        elif "fees collected" in prompt.lower() and "2021" in prompt.lower():
            return "SELECT SUM(T1.Fees_MM_USD) FROM Fund_Cash_Flows AS T1 WHERE T1.Transaction_Type = 'Capital Call' AND EXTRACT(YEAR FROM T1.Transaction_Date) = 2021;"
        elif "List the names" in prompt.lower():
             return "SELECT Fund_Name FROM PE_Portfolio WHERE Vintage_Year = 2024;"
        elif "quantify the initial NAV impact" in prompt.lower():
             return "SELECT NAV_Valuation_Initial_Impact FROM FUND_MODEL_ASSUMPTIONS WHERE Primary_Strategy = 'Private Equity';"
        
        # Default mock for final answer generation
        return "Based on the data retrieved, the answer is generated from mock data."
    
# --- THE RAG AGENT FRAMEWORK ---

def run_database_agent(conn: MockPostgresConnection, user_query: str):
    """
    The main RAG workflow:
    1. LLM generates SQL from the user query (PostgreSQL dialect).
    2. SQL is executed against the database.
    3. Python looks up the quantitative equivalent if necessary.
    4. LLM generates a final answer using the query result and context.
    """
    cursor = conn.cursor()

    # 1. Generate SQL Prompt (Modified for PostgreSQL date functions)
    sql_system_prompt = (
        "You are an expert PostgreSQL SQL generator. Your task is to translate the user's question "
        "into a single, valid PostgreSQL SQL query using tables PE_Portfolio (T1), Fund_Cash_Flows (T2), and FUND_MODEL_ASSUMPTIONS (T3). Only output the SQL query, no explanations."
        "The schema is: "
        "PE_Portfolio(...). "
        "Fund_Cash_Flows(...). "
        "FUND_MODEL_ASSUMPTIONS(Primary_Strategy, NAV_Valuation_Initial_Impact, ...)."
        "Use EXTRACT(YEAR FROM Transaction_Date) for date filtering."
    )
    
    # 2. Call LLM to generate SQL
    generated_sql = query_llm(f"{sql_system_prompt}\n\nUser Question: {user_query}")
    
    generated_sql = generated_sql.replace("```sql", "").replace("```", "").strip().split(';')[0].strip()
    
    print(f"\n[Generated SQL]: {generated_sql}")
    
    # 3. Execute SQL Query
    try:
        cursor.execute(generated_sql)
        sql_result = cursor.fetchall()
        
        column_names = [description[0] for description in cursor.description]
        result_string = f"Columns: {column_names}\nData: {sql_result}"
        
        print(f"\n[SQL Execution Success]: Retrieved {len(sql_result)} rows.")
        
    except Exception as e:
        result_string = f"SQL Execution Error: {e} | Query attempted: {generated_sql}"
        print(f"\n[SQL Execution FAILED]: {e}")
        
    # --- 4. Python-Side Lookup and Augmentation (New Step) ---
    quantitative_context = ""
    # Check if the query retrieved the qualitative NAV impact label
    if 'NAV_Valuation_Initial_Impact' in column_names and sql_result:
        qualitative_label = sql_result[0][column_names.index('NAV_Valuation_Initial_Impact')]
        params = NAV_PARAMETER_MAP.get(qualitative_label)
        
        if params:
            # Augment the context sent back to the LLM with the numeric data
            quantitative_context = (
                f"The qualitative label '{qualitative_label}' maps to the following quantitative model parameters: "
                f"Initial Quarterly Depreciation: {params['nav_impact_pct'] * 100:.2f}%, "
                f"Duration: {params['duration_quarters']} quarters. "
                f"Modeling Rationale: {params['comment']}"
            )
            print(f"\n[Python Augmentation]: Found quantitative mapping for '{qualitative_label}'.")


    # 5. Result-to-Text (Final RAG step)
    rag_system_prompt = (
        "You are a financial analyst. Using the original user question and the provided SQL result (plus any quantitative context), "
        "formulate a concise, professional, natural language answer. If quantitative data is provided, use it to fully explain the qualitative term."
    )
    
    final_prompt = f"{rag_system_prompt}\n\nOriginal Query: {user_query}\nSQL Result Data: {result_string}\n\nQUANTITATIVE CONTEXT: {quantitative_context}"
    
    final_answer = query_llm(final_prompt)
    
    print("\n--- FINAL ANSWER ---")
    print(final_answer)
    print("---------------------\n")


# --- EXAMPLE USAGE (Adding a new query to test the new logic) ---

if __name__ == "__main__":
    
    db_connection = get_db_connection()

    if db_connection:
        queries = [
            "Which fund has the largest total commitment in millions of USD?",
            "Quantify the initial NAV impact for the 'Private Equity' strategy." # NEW QUERY
        ]

        for q in queries:
            print(f"--- USER QUERY: {q} ---")
            run_database_agent(db_connection, q)
            time.sleep(1) 

        db_connection.close()

    else:
        print("\nCannot run agent without a successful database connection.")
