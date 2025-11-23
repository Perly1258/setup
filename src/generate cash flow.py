import pandas as pd
import numpy as np
import io

# --- 1. Data Definitions and Scaling (Re-run of previous logic to get commitments) ---

# Data string used for simulation
data = """
Fund_ID,Fund_Name,Vintage_Year,Commitment (MM USD),Primary_Strategy,Sub_Strategy,Comment
1,Pinnacle Tech Fund VI,2021,850,Private Equity,Growth Equity,"Focused on B2B SaaS in North America."
2,Apex Venture Partners III,2023,210,Venture Capital,Early-Stage VC,"High-conviction bets on AI/ML startups."
3,Global Buyout Capital X,2018,4200,Private Equity,Leveraged Buyout (LBO),"Targets mature, industrial companies for operational improvement."
4,InfraStructure Builders I,2017,1500,Infrastructure,Core/Value-Add,"Investment in renewable energy and transport assets."
5,Distress & Recovery Fund V,2020,550,Private Credit,Distressed Debt,"Special situations in cyclical industries."
6,Frontier HealthTech II,2024,380,Private Equity,Growth Equity,"Minority stakes in profitable European HealthTech firms."
7,Emerging Markets PE VII,2019,950,Private Equity,Buyout (EM),"Focused on consumer goods in Southeast Asia."
8,Mid-Market Value Fund IV,2022,1100,Private Equity,LBO (Mid-Market),"Targets stable, regional service businesses."
9,Innovation Seed Fund I,2024,90,Venture Capital,Seed/Early-Stage VC,"Pre-seed funding for university spin-outs."
10,Real Estate Alpha III,2016,2700,Real Estate,Core-Plus,"Investments in US logistics and multi-family."
11,Sustainable Impact Fund,2023,620,Private Equity,Impact Investing,"Focused on achieving measurable ESG goals alongside financial returns."
12,Secondaries Solution 8,2021,1800,Secondaries,LP-Led,"Acquiring LP stakes in older, diversified PE funds."
13,European Turnaround Fund,2019,450,Private Equity,Distressed Buyout,"Acquiring and restructuring financially troubled European SMEs."
14,Quantum Ventures II,2022,160,Venture Capital,Deep Tech VC,"Focus on quantum computing and advanced materials."
15,Credit Opportunities VI,2020,750,Private Credit,Direct Lending,"Unitranche loans to middle-market companies."
16,Asia Growth Capital V,2023,1300,Private Equity,Growth Equity,"Technology and internet sectors in China and India."
17,Harvest Fund 2015,2015,3100,Private Equity,LBO (Exiting),"Nearing end of investment period; focused on exits."
18,Special Situations Fund IV,2022,320,Private Credit,Mezzanine,"Subordinated debt with equity upside."
19,CyberSec Accelerator I,2024,120,Venture Capital,Sector Specialist,"Focused exclusively on cybersecurity and defense technology."
20,Agri-Fund Europe II,2020,410,Real Assets,Agriculture/Farmland,"Farmland and agricultural supply chain investments."
21,Global Consumer Partners,2018,2200,Private Equity,LBO (Consumer),"Acquiring majoritarian stakes in established consumer brands."
22,FinTech Innovators III,2023,580,Private Equity,Growth Equity,"Investments in late-stage payments and lending platforms."
23,Horizon Co-Investment,2021,600,Co-Investment,Multi-Strategy,"Allocating capital alongside various GP partners."
24,Bio-Discovery Fund X,2022,1900,Venture Capital,Biotech/Life Sciences,"R&D and clinical trials for pharmaceutical companies."
25,LatAm Infra Fund II,2019,800,Infrastructure,Emerging Markets,"Toll roads and port development in Latin America."
26,Core Buyout Fund XI,2017,5500,Private Equity,LBO (Large Cap),"Diversified portfolio across several global industries."
27,New Horizons VC IV,2024,150,Venture Capital,Seed/Series A VC,"Focus on companies with decentralized business models."
28,Fund-of-Funds Global V,2023,1400,Fund of Funds (FoF),Global Diversified,"Investing across a portfolio of 15+ underlying PE funds."
29,Clean Energy Partners III,2021,920,Infrastructure,Renewable Energy,"Primarily investing in solar and wind power projects."
30,Retail Restructuring Fund,2020,280,Private Equity,Distressed Buyout,"Focused on acquiring and revitalizing bankrupt retail chains."
31,Global FoF Diversified IV,2024,2800,Fund of Funds (FoF),Multi-Strategy,"Target allocation: 60% Buyout, 30% Growth, 10% VC."
32,Secondary Market Opportunities VII,2023,6500,Secondaries,Multi-Strategy,"Mixture of traditional LP sales and continuation funds."
33,US Office & Retail Re-Cap Fund,2022,1200,Real Estate,Opportunistic,"Focused on converting or modernizing distressed urban assets."
34,FoF Emerging Manager I,2024,350,Fund of Funds (FoF),Emerging Manager,"Seeks out high-potential, first-time and smaller-manager funds."
35,Venture Secondaries IV,2023,980,Secondaries,VC Secondaries,"Acquiring older VC fund interests at a discount; focus on fund tail-ends."
36,European Logistics Fund V,2021,3400,Real Estate,Core/Core-Plus,"Stabilized income-generating warehouse and distribution centers."
37,FoF Asia PE Select III,2022,1500,Fund of Funds (FoF),Asia Focus,"Dedicated to primary commitments in top-quartile Asian GPs."
38,Real Estate Debt & Credit I,2024,700,Real Estate,Real Estate Debt,"Origination of mezzanine and bridge financing for commercial properties."
39,GP-Led Secondary Fund II,2023,2100,Secondaries,GP-Led/Continuation,"Focus on single-asset continuation funds and multi-asset restructurings."
40,Digital Infrastructure REIT,2022,4800,Infrastructure,Digital Assets,"Towers, data centers, and fiber optic cable assets."
41,FoF Latin America Strategy II,2021,450,Fund of Funds (FoF),Regional Focus,"Investment in PE funds with a deep focus on Brazil and Mexico."
42,RE Value-Add Multifamily IV,2024,1900,Real Estate,Value-Add,"Acquiring apartment complexes for renovation in high-growth US metros."
43,Secondary Real Assets Fund I,2022,1100,Secondaries,Real Assets,"Secondary transactions for Infrastructure and Real Estate funds."
44,Thematic FoF Health & Tech,2023,650,Fund of Funds (FoF),Thematic Specialist,"Investing solely in specialist healthcare and technology funds."
45,Residential Land Development I,2024,300,Real Estate,Development,"Capital for the entitlement and development of master-planned communities."
"""

lines = data.strip().split('\n')
header = lines[0].split(',')
data_rows = []

for line in lines[1:]:
    parts = line.split(',', 6) # Split by 6 commas to handle the 7 columns, keeping comment intact
    if len(parts) == 7:
        data_rows.append(parts)

df = pd.DataFrame(data_rows, columns=header)
df['Commitment (MM USD)'] = pd.to_numeric(df['Commitment (MM USD)'])

# --- Re-apply Scaling Logic ---
TARGET_TOTAL_COMMITMENT = 500
current_total_commitment = df['Commitment (MM USD)'].sum()
scaling_factor = TARGET_TOTAL_COMMITMENT / current_total_commitment
df['Commitment (MM USD)'] = (df['Commitment (MM USD)'] * scaling_factor).round(1)
# -----------------------------

# --- 2. Simulation Logic (Re-run to generate full data) ---

FUND_LIFE = 15 # years
np.random.seed(42) # for reproducibility

def get_moic(strategy):
    if strategy in ['Venture Capital', 'Private Equity']:
        return np.random.uniform(2.2, 2.8) if strategy == 'Venture Capital' else np.random.uniform(1.7, 2.0)
    elif strategy in ['Real Estate', 'Infrastructure', 'Real Assets']:
        return np.random.uniform(1.4, 1.7)
    elif strategy in ['Fund of Funds (FoF)', 'Secondaries', 'Co-Investment']:
        return np.random.uniform(1.6, 1.9)
    elif strategy in ['Private Credit']:
        return np.random.uniform(1.2, 1.5)
    else:
        return np.random.uniform(1.5, 2.0)

def simulate_cash_flows_and_nav(row):
    fund_id = row['Fund_ID']
    vintage = int(row['Vintage_Year'])
    commitment = row['Commitment (MM USD)']
    strategy = row['Primary_Strategy']
    
    FEE_RATE_1 = 0.02 / 4 # 2% annual / 4 for first 5 years
    FEE_RATE_2 = 0.01 / 4 # 1% annual / 4 thereafter
    
    q_len = FUND_LIFE * 4 # 60 quarters
    
    # Contributions (Total 100% over 32 quarters)
    q_cont_shape = np.zeros(q_len)
    q_cont_shape[:32] = 1 / 32 
    
    # Distributions (Total 100% over quarters 16-48)
    q_dist_shape = np.zeros(q_len)
    x = np.linspace(-3, 3, 32)
    pdf = np.exp(-0.5 * x**2)
    pdf /= np.sum(pdf)
    q_dist_shape[16:48] = pdf
    
    cash_flows = []
    nav = 0.0
    total_investment_called = 0.0
    total_roc_returned = 0.0
    moic = get_moic(strategy)
    total_distribution_target = commitment * moic
    
    for q_idx in range(q_len):
        year = vintage + (q_idx // 4) + 1
        quarter = (q_idx % 4) + 1
        date = pd.to_datetime(f'{year}-{quarter * 3}-30')
        
        # --- 1. Capital Calls & Fees ---
        cont_amount = commitment * q_cont_shape[q_idx] * np.random.uniform(0.9, 1.1)
        
        investment_call, fees_called = 0.0, 0.0
        if cont_amount > (commitment * 0.0005): # Min threshold for a call
            fee_rate = FEE_RATE_1 if q_idx < 20 else FEE_RATE_2
            fees = commitment * fee_rate
            
            fees_called = -fees
            investment_call = -(cont_amount - fees) # Net investment
            total_investment_called += abs(investment_call)
            
            cash_flows.append({
                'Fund_ID': fund_id,
                'Transaction_Date': date,
                'Reporting_Quarter': quarter,
                'Transaction_Type': 'Capital Call',
                'Investment_MM_USD': round(investment_call, 4), 
                'Fees_MM_USD': round(fees_called, 4),
                'Return_of_Cost_MM_USD': 0.0,
                'Profit_MM_USD': 0.0,
                'MOIC': round(moic, 2)
            })
            
        # --- 2. Distributions (ROC & Profit) ---
        dist_amount = total_distribution_target * q_dist_shape[q_idx] * np.random.uniform(0.9, 1.1)
        
        roc, profit = 0.0, 0.0
        if dist_amount > (commitment * 0.0005):
            
            # Simple waterfall: Return of Cost (ROC) first, then Profit
            roc_remaining = commitment - total_roc_returned
            roc = min(dist_amount, roc_remaining)
            profit = dist_amount - roc
            
            total_roc_returned += roc
            
            cash_flows.append({
                'Fund_ID': fund_id,
                'Transaction_Date': date,
                'Reporting_Quarter': quarter,
                'Transaction_Type': 'Distribution',
                'Investment_MM_USD': 0.0,
                'Fees_MM_USD': 0.0,
                'Return_of_Cost_MM_USD': round(roc, 4),
                'Profit_MM_USD': round(profit, 4),
                'MOIC': round(moic, 2)
            })

        # --- 3. NAV Calculation ---
        
        # Estimate quarterly value change (ΔValue)
        q_return = 0.0
        if q_idx < 8: q_return = np.random.uniform(-0.02, -0.005)
        elif 8 <= q_idx < 20: q_return = np.random.uniform(0.0, 0.03)
        elif 20 <= q_idx < 40: q_return = np.random.uniform(0.03, 0.08)
        else: q_return = np.random.uniform(-0.01, 0.01)

        # Apply value change to current NAV
        nav = nav * (1 + q_return)
        
        # Update NAV for the quarter's cash flows
        if investment_call != 0.0: nav += abs(investment_call) # Investment adds to NAV
        if fees_called != 0.0: nav += fees_called # Fees reduce NAV
        if dist_amount != 0.0: nav -= dist_amount # Distributions reduce NAV
        
        # Final NAV floor
        nav = max(0.001, nav) 
        
        # Record NAV at the end of the quarter (explicit 'NAV Update' event)
        # If a transaction occurred this quarter, find it, update its NAV, and move on.
        if investment_call != 0.0 or dist_amount != 0.0:
            last_cf_entry = cash_flows[-1]
            last_cf_entry['Quarterly_NAV_USD'] = round(nav * 1_000_000, 2)
        else:
            # If no cash flow event, add an explicit NAV Update entry
            cash_flows.append({
                'Fund_ID': fund_id,
                'Transaction_Date': date,
                'Reporting_Quarter': quarter,
                'Transaction_Type': 'NAV Update',
                'Investment_MM_USD': 0.0,
                'Fees_MM_USD': 0.0,
                'Return_of_Cost_MM_USD': 0.0,
                'Profit_MM_USD': 0.0,
                'MOIC': round(moic, 2),
                'Quarterly_NAV_USD': round(nav * 1_000_000, 2)
            })

    return cash_flows

# Generate cash flows and NAV for all funds
all_cash_flows = []
for index, row in df.iterrows():
    all_cash_flows.extend(simulate_cash_flows_and_nav(row))

cf_df = pd.DataFrame(all_cash_flows)

# Sort and finalize columns
cf_df['Transaction_Date'] = pd.to_datetime(cf_df['Transaction_Date'])
cf_df.sort_values(by=['Fund_ID', 'Transaction_Date'], inplace=True)

final_cf_df = cf_df[['Fund_ID', 'Transaction_Date', 'Reporting_Quarter', 'Transaction_Type', 
                     'Investment_MM_USD', 'Fees_MM_USD', 'Return_of_Cost_MM_USD', 
                     'Profit_MM_USD', 'Quarterly_NAV_USD', 'MOIC']]

# Save to CSV (This will generate the full file in the execution environment)
output_filename = "Fund_Cash_Flows_FULL.csv"
final_cf_df.to_csv(output_filename, index=False)

print(f"Successfully generated the full cash flow file: {output_filename}")
print(f"Total rows in the full file: {len(final_cf_df)}")

# --- End of generation script ---