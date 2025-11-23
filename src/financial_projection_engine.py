import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import requests
import json
from typing import List, Dict, Any
# NOTE: You will need to install the PostgreSQL adapter locally: pip install psycopg2-binary
# IMPORTANT: Uncomment the line below in your actual setup
# import psycopg2 

# --- CONFIGURATION (Match settings in rag_database_agent.py) ---
DB_CONFIG = {
    "host": "localhost",
    "database": "private_markets_db",
    "user": "postgres",           # Updated User
    "password": "postgres",       # Updated Password
    "port": "5432"
}
# The current simulation date (end of last quarter for historical data)
SIMULATION_DATE = datetime(2025, 12, 31) 
PROJECTION_HORIZON_QUARTERS = 20 # 5 years * 4 quarters

# --- DB CONNECTION (Replace the mock with actual psycopg2 connection) ---

def get_db_connection():
    """
    Establishes and returns an actual psycopg2 connection to PostgreSQL.
    """
    print(f"Attempting to connect to PostgreSQL at {DB_CONFIG['host']}:{DB_CONFIG['port']}...")
    try:
        # ---------------------------------------------------------------------
        # !!! UNCOMMENT AND USE THIS BLOCK IN YOUR LOCAL SETUP !!!
        # import psycopg2
        # conn = psycopg2.connect(**DB_CONFIG)
        # return conn
        # ---------------------------------------------------------------------

        # --- MOCK CONNECTION (Fallback for demonstration) ---
        class MockConnection:
            def cursor(self):
                class MockCursor:
                    def __init__(self):
                        self.query = None
                        self._data = []
                        self.description = None

                    def execute(self, query):
                        # FIX: Set query and ensure description is populated here
                        self.query = query 
                        self._data = []
                        self.description = None
                        
                        # Mock logic based on query structure (simulating DB response)
                        if "PE_Portfolio" in self.query:
                            # fund_id, fund_name, vintage_year, primary_strategy, total_commitment_mm_usd
                            self._data = [
                                (1, 'Pinnacle Tech Fund VI', 2021, 'Private Equity', 6.60), (2, 'Apex Venture Partners III', 2023, 'Venture Capital', 1.60),
                                (3, 'Global Buyout Capital X', 2018, 'Private Equity', 32.50), (4, 'InfraStructure Builders I', 2017, 'Infrastructure', 11.60),
                                (10, 'Real Estate Alpha III', 2016, 'Real Estate', 20.90)
                            ]
                            self.description = [('fund_id',), ('fund_name',), ('vintage_year',), ('primary_strategy',), ('total_commitment_mm_usd',)]
                        elif "FUND_MODEL_ASSUMPTIONS" in self.query:
                            # primary_strategy, expected_moic_gross, nav_initial_qtr_depreciation, nav_initial_depreciation_qtrs, target_irr_net
                            self._data = [
                                ('Venture Capital', 2.75, -0.0150, 8, 0.22),
                                ('Private Equity', 1.85, -0.0050, 6, 0.16),
                                ('Real Estate', 1.60, -0.0010, 4, 0.13),
                                ('Infrastructure', 1.50, -0.0001, 2, 0.10),
                            ]
                            self.description = [
                                ('primary_strategy',), ('expected_moic_gross',), 
                                ('nav_initial_qtr_depreciation',), ('nav_initial_depreciation_qtrs',), 
                                ('target_irr_net',)
                            ]
                        else:
                            # Catch-all: Ensure description is set even for unrecognized queries
                            self._data = [('Query not recognized by mock.',)]
                            self.description = [('mock_error',)]
                        
                        # End of execute method
                        
                    def fetchall(self):
                        # Fetchall simply returns the data set during execution
                        return self._data
                    
                    def close(self): pass

                return MockCursor()
            def close(self): print("MOCK: Connection closed.")
        return MockConnection()
        # --- END OF MOCK CONNECTION ---

    except Exception as e:
        print(f"Error connecting to PostgreSQL. Ensure service is running and DB_CONFIG is correct: {e}")
        return None


def load_historical_data(conn):
    """
    Mocks loading historical Fund_Cash_Flows data from the database.
    
    IMPORTANT: The keys here must match the final merged keys (Fund_ID, Cumulative_Calls, etc.).
    """
    print("MOCK: Loading historical cash flows...")
    
    # Simulate the critical input state for each fund at SIMULATION_DATE
    historical_state = pd.DataFrame({
        # NOTE: Keys are set to match the target PascalCase used in merging
        'Fund_ID': [1, 2, 3, 4, 10], 
        'Cumulative_Calls': [4.0, 0.8, 25.0, 5.0, 15.0],  
        'Cumulative_Dists': [2.5, 0.1, 15.0, 3.0, 10.0],  
        'Current_NAV': [4.5, 0.9, 18.0, 7.0, 12.0],      
        'Unfunded_Commitment': [2.6, 0.8, 7.5, 6.6, 5.9] 
    })
    
    # No renaming needed if keys are already correct PascalCase
    return historical_state

# --- 1. CORE UTILITY FUNCTIONS ---

def generate_quarterly_dates(start_date, num_quarters):
    """Generates a list of quarter-end dates for the projection horizon."""
    dates = []
    current_date = start_date
    for _ in range(num_quarters):
        # Advance by 3 months, handle month wrap-around
        if current_date.month in [1, 2, 3]: current_date = datetime(current_date.year, 3, 31)
        elif current_date.month in [4, 5, 6]: current_date = datetime(current_date.year, 6, 30)
        elif current_date.month in [7, 8, 9]: current_date = datetime(current_date.year, 9, 30)
        else: current_date = datetime(current_date.year + 1, 12, 31)
        
        # Advance exactly 3 months for the next quarter end
        current_date += timedelta(days=90) # Approximate 90 days for next quarter start
        if current_date.month in [1, 2, 3]: current_date = datetime(current_date.year, 3, 31)
        elif current_date.month in [4, 5, 6]: current_date = datetime(current_date.year, 6, 30)
        elif current_date.month in [7, 8, 9]: current_date = datetime(current_date.year, 9, 30)
        else: current_date = datetime(current_date.year, 12, 31)
        
        dates.append(current_date)
    return dates

def get_cash_flow_shape(strategy, num_quarters):
    """
    Mocks generating a normalized S-Curve or J-Curve shape array (summing to 1.0)
    based on the Primary_Strategy for contributions and distributions.
    """
    # Simplified S-Curve (Contributions): Front-loaded drawdown
    cont_shape = np.zeros(num_quarters)
    if strategy == 'Venture Capital': cont_shape[:8] = np.linspace(0.01, 0.05, 8) # Fast start
    elif strategy == 'Private Equity': cont_shape[:12] = np.linspace(0.01, 0.03, 12) # Steady start
    elif strategy == 'Infrastructure': cont_shape[:20] = np.linspace(0.01, 0.02, 20) # Slow, long start
    else: cont_shape[:10] = np.linspace(0.02, 0.04, 10) # Default fast
    
    # Simplified J-Curve (Distributions): Back-loaded return
    dist_shape = np.zeros(num_quarters)
    if strategy == 'Venture Capital': dist_shape[12:20] = np.linspace(0.01, 0.1, 8) # Late start, steep rise
    elif strategy == 'Private Equity': dist_shape[8:18] = np.linspace(0.02, 0.08, 10) # Mid start
    elif strategy == 'Infrastructure': dist_shape[:] = 1 / num_quarters # Steady, immediate yield
    else: dist_shape[6:16] = np.linspace(0.03, 0.07, 10) # Default mid-term
    
    # Normalize to ensure arrays sum to 1 (if used for 100% of remaining flow)
    cont_shape = cont_shape / np.sum(cont_shape) if np.sum(cont_shape) > 0 else np.zeros(num_quarters)
    dist_shape = dist_shape / np.sum(dist_shape) if np.sum(dist_shape) > 0 else np.zeros(num_quarters)
    
    return cont_shape, dist_shape


# --- 2. THE PROJECTION ENGINE ---

def calculate_projection(fund_metadata_df, historical_state_df, assumption_df):
    """
    Runs the Yale Model-style cash flow projection for the next 5 years (20 quarters).
    
    Returns: DataFrame with projected quarterly cash flows (Calls, Dists, NAV).
    """
    
    # Combine all data sources
    # NOTE: The merge keys are ('Fund_ID' and 'Primary_Strategy')
    df_combined = fund_metadata_df.merge(historical_state_df, on='Fund_ID').merge(assumption_df, on='Primary_Strategy')
    
    projection_data = []
    quarterly_dates = generate_quarterly_dates(SIMULATION_DATE, PROJECTION_HORIZON_QUARTERS)
    
    for index, fund in df_combined.iterrows():
        
        # Determine remaining flow amounts
        unfunded_commitment_total = fund['Unfunded_Commitment']
        
        # Calculate remaining distributions needed to hit the MOIC target
        total_investment = fund['Cumulative_Calls'] + unfunded_commitment_total
        target_total_distributions = total_investment * fund['Expected_MOIC_Gross']
        
        # Distributions needed = Target Total Dists - Cumulative Dists
        distributions_remaining = max(0, target_total_distributions - fund['Cumulative_Dists'])
        
        # 1. Get Strategy-Specific Shapes
        cont_shape, dist_shape = get_cash_flow_shape(fund['Primary_Strategy'], PROJECTION_HORIZON_QUARTERS)
        
        current_nav = fund['Current_NAV']
        
        for q_idx in range(PROJECTION_HORIZON_QUARTERS):
            q_date = quarterly_dates[q_idx]
            
            # --- A. Capital Call Projection ---
            
            # Use the shape to determine the CALL amount from the UNFUNDED commitment
            # We assume fees are called alongside investment, proportional to Total Commitment (2% of commitment annually for the first 5 years)
            
            fee_rate_q = 0.02 / 4 if fund['Vintage_Year'] >= q_date.year - 5 else 0.01 / 4
            
            # Normalize shape by remaining unfunded capital *needed* for investment
            projected_call_investment = unfunded_commitment_total * cont_shape[q_idx]
            
            projected_fees = fund['Total_Commitment_MM_USD'] * fee_rate_q
            
            if projected_call_investment > 0.001 or projected_fees > 0.001:
                # Add to projection list (Calls are negative)
                projection_data.append({
                    'Fund_ID': fund['Fund_ID'], 'Fund_Name': fund['Fund_Name'], 'Date': q_date, 
                    'Type': 'Call (Investment)', 'Amount_MM_USD': round(-projected_call_investment, 4)
                })
                projection_data.append({
                    'Fund_ID': fund['Fund_ID'], 'Fund_Name': fund['Fund_Name'], 'Date': q_date, 
                    'Type': 'Call (Fees)', 'Amount_MM_USD': round(-projected_fees, 4)
                })
                # Update total investment metric for NAV and remaining unfunded commitment
                unfunded_commitment_total = max(0, unfunded_commitment_total - projected_call_investment)
            
            # --- B. Distribution Projection ---
            
            # Use the shape to determine the distribution amount from the REMAINING distributions target
            projected_distribution = distributions_remaining * dist_shape[q_idx]
            
            if projected_distribution > 0.001:
                # Add to projection list (Distributions are positive)
                projection_data.append({
                    'Fund_ID': fund['Fund_ID'], 'Fund_Name': fund['Fund_Name'], 'Date': q_date, 
                    'Type': 'Distribution', 'Amount_MM_USD': round(projected_distribution, 4)
                })
                distributions_remaining -= projected_distribution

            # --- C. NAV Projection ---
            
            # NAV = NAV_prev * (1 + Qtr_Return) + New_Investment - Distributions - Fees
            
            # 1. Quarterly Return Rate (Value Appreciation/Depreciation)
            qtr_return = 0.0
            
            # Implement initial J-Curve drop logic (using the quantitative assumptions)
            qtrs_since_sim = (q_date.year - SIMULATION_DATE.year) * 4 + (q_date.month // 3)
            
            if qtrs_since_sim <= fund['NAV_Initial_Depreciation_Qtrs']:
                # Initial J-Curve Period: Apply depreciation
                qtr_return = fund['NAV_Initial_Qtr_Depreciation'] # e.g., -0.0150
            else:
                # Later Growth Period: Apply standardized expected growth (based on Target IRR)
                # Simplified growth factor derived from Target IRR * 0.5 (compounded quarterly)
                annual_growth_rate = fund['Target_IRR_Net'] * 0.5 
                qtr_return = (1 + annual_growth_rate)**0.25 - 1
            
            # 2. Update NAV
            nav_change_value = current_nav * qtr_return
            
            nav_change_cash = 0.0
            if 'Call (Investment)' in [d['Type'] for d in projection_data if d['Date'] == q_date]:
                nav_change_cash += projected_call_investment # Investment is asset increase
            if 'Call (Fees)' in [d['Type'] for d in projection_data if d['Date'] == q_date]:
                nav_change_cash -= projected_fees # Fees are expense decrease
            if 'Distribution' in [d['Type'] for d in projection_data if d['Date'] == q_date]:
                nav_change_cash -= projected_distribution # Distributions are asset decrease

            current_nav = current_nav + nav_change_value + nav_change_cash
            current_nav = max(0.001, current_nav) # NAV floor at zero

            # Record final NAV for the quarter
            projection_data.append({
                'Fund_ID': fund['Fund_ID'], 'Fund_Name': fund['Fund_Name'], 'Date': q_date, 
                'Type': 'NAV (Projected)', 'Amount_MM_USD': round(current_nav, 4)
            })

    # Convert to DataFrame
    df_projection = pd.DataFrame(projection_data)
    
    # Aggregate and return the final projection (Calls and Dists aggregated per quarter)
    df_projection_summary = df_projection.groupby(['Fund_ID', 'Fund_Name', 'Date', 'Type'])['Amount_MM_USD'].sum().reset_index()
    
    print(f"Projection complete for {len(df_combined)} funds.")
    
    return df_projection_summary.pivot_table(
        index=['Fund_ID', 'Fund_Name', 'Date'],
        columns='Type',
        values='Amount_MM_USD'
    ).reset_index().fillna(0)


# --- 3. MAIN EXECUTION ---

if __name__ == "__main__":
    
    conn = get_db_connection()
    
    # 1. Load Data from DB
    # In reality, these queries pull from PE_Portfolio, Fund_Cash_Flows, and FUND_MODEL_ASSUMPTIONS
    print("\n--- Starting Data Retrieval ---")
    
    # SQL Queries to retrieve required metadata and assumptions
    fund_metadata_sql = "SELECT fund_id, fund_name, vintage_year, primary_strategy, total_commitment_mm_usd FROM PE_Portfolio;" 
    assumption_sql = "SELECT primary_strategy, expected_moic_gross, nav_initial_qtr_depreciation, nav_initial_depreciation_qtrs, target_irr_net FROM FUND_MODEL_ASSUMPTIONS;" 
    
    # Mocks return data from the database
    cursor_meta = conn.cursor()
    cursor_meta.execute(fund_metadata_sql)
    meta_cols = [desc[0] for desc in cursor_meta.description]
    fund_metadata_df = pd.DataFrame(cursor_meta.fetchall(), columns=meta_cols) 

    cursor_assump = conn.cursor()
    cursor_assump.execute(assumption_sql)
    assump_cols = [desc[0] for desc in cursor_assump.description]
    assumption_df = pd.DataFrame(cursor_assump.fetchall(), columns=assump_cols)
    
    # --- RENAME STEP (Ensure PascalCase for Merge Keys) ---
    
    # 1. Rename fund_metadata_df columns for consistency
    fund_metadata_df.rename(columns={
        'fund_id': 'Fund_ID',
        'fund_name': 'Fund_Name',
        'vintage_year': 'Vintage_Year', 
        'primary_strategy': 'Primary_Strategy', 
        'total_commitment_mm_usd': 'Total_Commitment_MM_USD'
    }, inplace=True)
    
    # 2. Rename assumption_df columns for consistency
    assumption_df.rename(columns={
        'primary_strategy': 'Primary_Strategy',
        'expected_moic_gross': 'Expected_MOIC_Gross',
        'nav_initial_qtr_depreciation': 'NAV_Initial_Qtr_Depreciation',
        'nav_initial_depreciation_qtrs': 'NAV_Initial_Depreciation_Qtrs',
        'target_irr_net': 'Target_IRR_Net'
    }, inplace=True)
    
    # Load the synthetic historical state (which is already in PascalCase)
    historical_state_df = load_historical_data(conn)
    
    # 2. Run Projection Engine
    print("\n--- Running Financial Projection Engine ---")
    # Merge keys are now consistent: 'Fund_ID' and 'Primary_Strategy'
    projection_results = calculate_projection(fund_metadata_df, historical_state_df, assumption_df)
    
    # 3. Output and Storage (Ready for VDB Indexing)
    print("\n--- 5-Year Projection Forecast (MM USD) ---")
    print(projection_results.head(15).to_markdown(index=False, floatfmt=".4f"))
    
    # Save the projection to a CSV file (This file is the input for the VDB indexing script)
    projection_results.to_csv("Projected_Cash_Flows_5Y.csv", index=False)
    print("\nProjection saved to Projected_Cash_Flows_5Y.csv")
    
    conn.close()