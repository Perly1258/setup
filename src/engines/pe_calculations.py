import pandas as pd
import numpy as np
from pyxirr import xirr
from sqlalchemy import create_engine, text
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PECalculator:
    """
    Engine for calculating Private Equity performance metrics.
    Levels: Fund. (Can be extended to Company/Deal/LP if data exists).
    Metrics: IRR, TVPI, DPI, RVPI, MOIC.
    """
    def __init__(self, db_url=None):
        self.db_url = db_url or os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/private_markets_db")
        self.engine = create_engine(self.db_url)

    def run_all(self):
        """Runs calculations for all entity levels."""
        logger.info("Starting PE Metrics Calculation...")
        # Currently only 'fund' level is supported by the schema
        for level in ['fund']:
            self.calculate_metrics(level)
        logger.info("Calculation complete.")

    def calculate_metrics(self, entity_type):
        """
        Calculates metrics for a specific entity type (level).
        """
        logger.info(f"Processing Level: {entity_type}")
        
        if entity_type != 'fund':
            logger.warning(f"Level '{entity_type}' is not yet supported by the current schema.")
            return

        # 1. Fetch Cashflows
        # Schema: pe_historical_cash_flows
        # Columns: fund_id, transaction_date, investment_paid_in_usd, management_fees_usd, 
        # return_of_cost_distribution_usd, profit_distribution_usd, net_asset_value_usd
        
        sql = """
        SELECT 
            fund_id as entity_id,
            transaction_date,
            investment_paid_in_usd,
            management_fees_usd,
            return_of_cost_distribution_usd,
            profit_distribution_usd,
            net_asset_value_usd,
            transaction_type
        FROM pe_historical_cash_flows
        ORDER BY transaction_date ASC
        """
        
        try:
            with self.engine.connect() as conn:
                df = pd.read_sql(text(sql), conn)
        except Exception as e:
            logger.error(f"Error fetching data for {entity_type}: {e}")
            return

        if df.empty:
            logger.warning(f"No data found for {entity_type}")
            return

        # 2. Group by Entity and Calculate
        results = []
        grouped = df.groupby('entity_id')
        
        for entity_id, group in grouped:
            metrics = self._compute_single_entity(group)
            metrics['entity_type'] = entity_type
            metrics['entity_id'] = str(entity_id)
            results.append(metrics)
            
        # 3. Store Results
        if results:
            results_df = pd.DataFrame(results)
            self._save_results(results_df)

    def _compute_single_entity(self, df):
        """
        Computes metrics for a single entity's cashflow stream.
        """
        # Fill NaNs with 0
        df = df.fillna(0)
        
        # Determine Latest NAV
        # We assume the last record with a non-zero NAV or the last record overall is the "latest" state
        # Better approach: Look for explicit 'NAV Update' or take the last known NAV
        nav_rows = df[df['net_asset_value_usd'] != 0]
        latest_nav = 0.0
        nav_date = pd.Timestamp.now().date()
        
        if not nav_rows.empty:
            latest_nav = nav_rows.iloc[-1]['net_asset_value_usd']
            nav_date = nav_rows.iloc[-1]['transaction_date']
        else:
            # Fallback if no NAV column populated, maybe last transaction has it?
            pass
            
        # Calculate Aggregates
        # Outflows (Paid In) = Investment + Fees
        paid_in = df['investment_paid_in_usd'].sum() + df['management_fees_usd'].sum()
        
        # Inflows (Distributed) = Return of Cost + Profit
        distributed = df['return_of_cost_distribution_usd'].sum() + df['profit_distribution_usd'].sum()
        
        # Metrics
        if paid_in == 0:
            return {
                'irr': None, 'tvpi': None, 'dpi': None, 'rvpi': None, 'moic': None,
                'total_invested': 0, 'total_distributed': distributed, 'nav': latest_nav
            }

        tvpi = (distributed + latest_nav) / paid_in
        dpi = distributed / paid_in
        rvpi = latest_nav / paid_in
        moic = tvpi
        
        # IRR Calculation
        # Construct the cashflow stream
        # Net Flow = (Distributions) - (Contributions)
        # Contributions = Investment + Fees
        # Distributions = Return of Cost + Profit
        
        # We need a Series of dates and amounts
        # Vectorized calculation for net amount per transaction
        net_flows = (
            (df['return_of_cost_distribution_usd'] + df['profit_distribution_usd']) - 
            (df['investment_paid_in_usd'] + df['management_fees_usd'])
        )
        
        dates = df['transaction_date'].tolist()
        amounts = net_flows.tolist()
        
        # Add Terminal Value (Latest NAV) as a positive flow at the end
        if latest_nav > 0:
            dates.append(nav_date)
            amounts.append(latest_nav)
            
        try:
            irr = xirr(dates, amounts)
        except Exception:
            irr = None 

        return {
            'irr': irr,
            'tvpi': tvpi,
            'dpi': dpi,
            'rvpi': rvpi,
            'moic': moic,
            'total_invested': paid_in,
            'total_distributed': distributed,
            'nav': latest_nav
        }

    def _save_results(self, df):
        """
        Upserts results into computed_metrics table.
        """
        df['calculation_date'] = pd.Timestamp.now()
        
        with self.engine.begin() as conn:
            for _, row in df.iterrows():
                # Delete existing
                delete_sql = """
                DELETE FROM computed_metrics 
                WHERE entity_type = :etype AND entity_id = :eid 
                """
                conn.execute(text(delete_sql), {"etype": row['entity_type'], "eid": row['entity_id']})
                
                # Insert
                insert_sql = """
                INSERT INTO computed_metrics 
                (entity_type, entity_id, irr, tvpi, dpi, rvpi, moic, total_invested, total_distributed, nav, calculation_date)
                VALUES (:etype, :eid, :irr, :tvpi, :dpi, :rvpi, :moic, :inv, :dist, :nav, :date)
                """
                conn.execute(text(insert_sql), {
                    "etype": row['entity_type'],
                    "eid": row['entity_id'],
                    "irr": row['irr'],
                    "tvpi": row['tvpi'],
                    "dpi": row['dpi'],
                    "rvpi": row['rvpi'],
                    "moic": row['moic'],
                    "inv": row['total_invested'],
                    "dist": row['total_distributed'],
                    "nav": row['nav'],
                    "date": row['calculation_date']
                })
        
        logger.info(f"Saved {len(df)} records to DB.")

if __name__ == "__main__":
    calc = PECalculator()
    calc.run_all()