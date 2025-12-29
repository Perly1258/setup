import pandas as pd
import numpy as np
import io
import datetime
import os
import sys
from dateutil.relativedelta import relativedelta

# Configure basic logging
import logging
logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)

# --- 1. Final Data Definitions and Scaling (Matching final PE_Portfolio.csv) ---

DATA_STRING = """
Fund_ID,Fund_Name,Vintage_Year,Commitment (USD),Primary_Strategy
1,Pinnacle Tech Fund VI,2021,6600000.00,Private Equity
2,Apex Venture Partners III,2023,1600000.00,Venture Capital
3,Global Buyout Capital X,2018,32500000.00,Private Equity
4,InfraStructure Builders I,2017,11600000.00,Infrastructure
5,Distress & Recovery Fund V,2020,4300000.00,Private Credit
6,Frontier HealthTech II,2024,2900000.00,Private Equity
7,Emerging Markets PE VII,2019,7300000.00,Private Equity
8,Mid-Market Value Fund IV,2022,8500000.00,Private Equity
9,Innovation Seed Fund I,2024,700000.00,Venture Capital
10,Real Estate Alpha III,2016,20500000.00,Real Estate
11,BioPharma Growth Fund I,2023,3100000.00,Venture Capital
12,Infrastructure Credit Fund II,2022,5900000.00,Private Credit
13,European Mid-Market II,2020,14700000.00,Private Equity
14,Venture Health Fund IV,2019,2800000.00,Venture Capital
15,Commodity Infrastructure III,2018,12500000.00,Infrastructure
16,Consumer Focus PE I,2024,4800000.00,Private Equity
17,Real Estate Income VI,2021,35000000.00,Real Estate
18,PE Secondaries Fund V,2022,18400000.00,Secondaries
19,Impact Infrastructure I,2023,6700000.00,Infrastructure
20,APAC Growth Capital Fund III,2020,9100000.00,Private Equity
21,Special Situations Credit I,2024,3300000.00,Private Credit
22,US Technology Buyout IX,2017,45800000.00,Private Equity
23,Emerging Venture Seed I,2023,1100000.00,Venture Capital
24,European Core Real Estate IV,2020,28900000.00,Real Estate
25,Global Diversified Infra II,2021,15500000.00,Infrastructure
26,Secondary Real Estate Fund II,2023,9300000.00,Secondaries
27,Private Credit Direct Lending III,2022,7700000.00,Private Credit
28,US Value Buyout XI,2019,27100000.00,Private Equity
29,Next-Gen Biotech Ventures,2024,4500000.00,Venture Capital
30,European Credit Opportunities,2020,6200000.00,Private Credit
31,APAC Infrastructure Growth I,2023,8800000.00,Infrastructure
32,RE Value-Add Industrial III,2022,18100000.00,Real Estate
33,Mid-Cap Growth Buyout,2021,12400000.00,Private Equity
33,Mid-Cap Growth Buyout,2021,12400000.00,Private Equity
34,FoF US Mid-Market VI,2020,22800000.00,Fund of Funds (FoF)
35,VC Secondaries Fund V,2023,7600000.00,Secondaries
36,European Logistics Fund V,2021,26300000.00,Real Estate
37,FoF Asia PE Select III,2022,11600000.00,Fund of Funds (FoF)
38,Real Estate Debt & Credit I,2024,5400000.00,Real Estate
39,GP-Led Secondary Fund II,2023,16200000.00,Secondaries
40,Digital Infrastructure REIT,2022,37300000.00,Infrastructure
41,FoF Latin America Strategy II,2021,3500000.00,Fund of Funds (FoF)
42,RE Value-Add Multifamily IV,2024,14700000.00,Real Estate
43,Secondary Real Assets Fund I,2022,8500000.00,Secondaries
44,Thematic FoF Health & Tech,2023,15300000.00,Fund of Funds (FoF)
45,Private Credit CLO Equity I,2024,9800000.00,Private Credit
46,Global Natural Resources PE I,2021,10700000.00,Private Equity
47,Emerging Markets Venture I,2023,2100000.00,Venture Capital
48,Real Estate Development Fund II,2020,13500000.00,Real Estate
49,European Infrastructure Core II,2019,21700000.00,Infrastructure
50,Mid-Market Services Buyout VI,2022,19500000.00,Private Equity
"""

# Read fund data from the internal string
df = pd.read_csv(io.StringIO(DATA_STRING))
df.columns = ['Fund_ID', 'Fund_Name', 'Vintage_Year', 'total_commitment_usd', 'Primary_Strategy']
# Convert commitment back to MM for internal simulation logic based on original design
df['Commitment_MM'] = df['total_commitment_usd'] / 1_000_000

# --- 2. Modeling Assumptions (Aligned with final pe_modeling_rules schema) ---
MODEL_ASSUMPTIONS = {
    'Private Equity': {'MOIC': 1.85, 'Life': 10, 'Fee_Rate': 0.0175, 'Call_Qtrs': 12, 'Dist_Qtrs': 18},
    'Venture Capital': {'MOIC': 2.75, 'Life': 12, 'Fee_Rate': 0.0200, 'Call_Qtrs': 16, 'Dist_Qtrs': 24},
    'Real Estate': {'MOIC': 1.60, 'Life': 10, 'Fee_Rate': 0.0150, 'Call_Qtrs': 8, 'Dist_Qtrs': 16},
    'Infrastructure': {'MOIC': 1.50, 'Life': 15, 'Fee_Rate': 0.0125, 'Call_Qtrs': 10, 'Dist_Qtrs': 20},
    'Private Credit': {'MOIC': 1.35, 'Life': 7, 'Fee_Rate': 0.0090, 'Call_Qtrs': 6, 'Dist_Qtrs': 12},
    'Secondaries': {'MOIC': 1.70, 'Life': 8, 'Fee_Rate': 0.0100, 'Call_Qtrs': 4, 'Dist_Qtrs': 10},
    'Fund of Funds (FoF)': {'MOIC': 1.55, 'Life': 10, 'Fee_Rate': 0.0080, 'Call_Qtrs': 0, 'Dist_Qtrs': 15},
}


# --- 3. Simulation Function (FIXED to generate the correct number of quarters) ---

def simulate_cash_flows(fund_row, quarters_to_simulate):
    """
    Simulates cash flows and NAV for a single fund based on the required 
    number of quarterly periods.
    """
    fund_id = fund_row['Fund_ID']
    strategy = fund_row['Primary_Strategy']
    commitment_mm = fund_row['Commitment_MM']
    
    # Use consistent initial values for simulation ease (MM USD)
    initial_nav_mm = commitment_mm * 0.1 
    target_investment_mm = commitment_mm * 0.5 
    target_fees_mm = commitment_mm * MODEL_ASSUMPTIONS[strategy]['Fee_Rate'] 
    moic_target = MODEL_ASSUMPTIONS[strategy]['MOIC']
    
    # Quarterly transaction amounts (MM USD)
    qtr_call_mm = target_investment_mm / MODEL_ASSUMPTIONS[strategy]['Call_Qtrs'] if MODEL_ASSUMPTIONS[strategy]['Call_Qtrs'] > 0 else 0
    qtr_fee_mm = target_fees_mm / 4 
    
    cash_flows = []
    
    start_date = datetime.datetime(fund_row['Vintage_Year'], 1, 1)
    
    cumulative_paid_in_mm = 0
    cumulative_investment_mm = 0
    
    # --- Simulation Loop (FIXED LOGIC) ---
    # The loop runs for the exact number of quarters calculated outside (e.g., 54 + buffer)
    for q in range(1, quarters_to_simulate + 1):
        date = start_date + relativedelta(months=3 * q)
        quarter_str = f"{q % 4 + 1}"
        
        # Determine transaction type and amounts (in MM USD)
        is_call = q <= MODEL_ASSUMPTIONS[strategy]['Call_Qtrs']
        is_distribution = q > MODEL_ASSUMPTIONS[strategy]['Call_Qtrs'] and q % 5 == 0 
        
        inv_mm = -qtr_call_mm if is_call else 0.0
        fees_mm = -qtr_fee_mm
        
        roc_mm = 0.0
        profit_mm = 0.0
        
        if is_distribution:
            # Simple assumption: return 5% of paid-in as ROC, and 3% as profit (MM USD)
            roc_mm = cumulative_paid_in_mm * 0.05
            profit_mm = cumulative_paid_in_mm * 0.03
            
        
        # Update cumulative metrics (use the actual investment value)
        cumulative_investment_mm += abs(inv_mm)
        if inv_mm < 0:
             cumulative_paid_in_mm += abs(inv_mm)
        
        # Simulate MOIC and NAV growth (simple linear model for NAV)
        nav_mm = initial_nav_mm + (cumulative_investment_mm * (moic_target / 2)) * (q / quarters_to_simulate)
        moic = (cumulative_paid_in_mm + nav_mm) / cumulative_paid_in_mm if cumulative_paid_in_mm > 0 else 1.0

        # Create the cash flow record (NOTE: Final output columns are snake_case and use ABSOLUTE USD)
        cash_flows.append({
            'Fund_ID': fund_id,
            'Transaction_Date': date.strftime('%Y-%m-%d'),
            'Reporting_Quarter': quarter_str,
            'Transaction_Type': 'Capital Call' if inv_mm < 0 else ('Distribution' if is_distribution else 'Fee/NAV Update'),
            
            # --- CRITICAL: SCALE TO ABSOLUTE USD (MULTIPLY BY 1,000,000) ---
            'investment_paid_in_usd': round(inv_mm * 1_000_000, 2),
            'management_fees_usd': round(fees_mm * 1_000_000, 2),
            'return_of_cost_distribution_usd': round(roc_mm * 1_000_000, 2), # Corrected name and scaled
            'profit_distribution_usd': round(profit_mm * 1_000_000, 2),      # Corrected name and scaled
            # --- END CRITICAL SCALING ---
            
            'net_asset_value_usd': round(nav_mm * 1_000_000, 2), # Scaled NAV
            'MOIC': round(moic, 2)
        })

        if len(cash_flows) >= quarters_to_simulate:
            break
            
    return cash_flows


# --- 4. Execution ---

# Define the relative path for the output file
OUTPUT_FILE_PATH_HISTORICAL = "data/Fund_Cash_Flows.csv"
OUTPUT_FILE_PATH_PROJECTED = "data/Fund_Cash_Flows_Projected.csv"

# Ensure directory exists
os.makedirs("data", exist_ok=True)

# Calculate how many rows need to be generated in total
TOTAL_ROWS_TARGET = 3700
# 2700 total rows / 50 funds = 54 quarters per fund (plus a small buffer for safety)
ROWS_PER_FUND = int(np.ceil(TOTAL_ROWS_TARGET / len(df)))

all_cash_flows = []
for index, row in df.iterrows():
    # Pass the required quarters per fund (54) plus 5 buffer quarters
    all_cash_flows.extend(simulate_cash_flows(row, quarters_to_simulate=ROWS_PER_FUND + 5)) 

cf_df = pd.DataFrame(all_cash_flows)

# Trim to exact row count and finalize columns
cf_df = cf_df.head(TOTAL_ROWS_TARGET)

cf_df['Transaction_Date'] = pd.to_datetime(cf_df['Transaction_Date'])
cf_df.sort_values(by=['Fund_ID', 'Transaction_Date'], inplace=True)

final_cf_df = cf_df[[
    'Fund_ID', 
    'Transaction_Date', 
    'Reporting_Quarter', 
    'Transaction_Type', 
    'investment_paid_in_usd', 
    'management_fees_usd', 
    'return_of_cost_distribution_usd', 
    'profit_distribution_usd', 
    'net_asset_value_usd', 
    'MOIC'
]]

# Split into Historical (<= Today) and Projected (> Today)
today = pd.Timestamp(datetime.date.today())
historical_df = final_cf_df[final_cf_df['Transaction_Date'] <= today]
projected_df = final_cf_df[final_cf_df['Transaction_Date'] > today]

# CRITICAL FIX: Write to the file path
try:
    historical_df.to_csv(OUTPUT_FILE_PATH_HISTORICAL, index=False)
    logger.info(f"Successfully generated and saved {len(historical_df)} rows of historical data to: {OUTPUT_FILE_PATH_HISTORICAL}")
    
    projected_df.to_csv(OUTPUT_FILE_PATH_PROJECTED, index=False)
    logger.info(f"Successfully generated and saved {len(projected_df)} rows of projected data to: {OUTPUT_FILE_PATH_PROJECTED}")
except Exception as e:
    logger.error(f"FATAL ERROR: Failed to write CSV file to disk. Check directory permissions or path existence.")
    logger.error(f"Error details: {e}")
    sys.exit(1)

# Print confirmation to console (optional, but confirms execution flow)
print(f"--- File Generation Complete ---")
print(f"Historical content saved to: {OUTPUT_FILE_PATH_HISTORICAL}")
print(f"Projected content saved to: {OUTPUT_FILE_PATH_PROJECTED}")
print(f"Total rows generated (including header): {len(final_cf_df) + 1}")