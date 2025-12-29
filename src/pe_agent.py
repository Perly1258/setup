import os
import pandas as pd
from sqlalchemy import create_engine, text
try:
    from engines.pe_calculations import PECalculator
except ImportError:
    # Handle case where run from root
    from src.engines.pe_calculations import PECalculator

class PEAgent:
    """
    Private Equity Intelligence Agent.
    
    Capabilities:
    1. Retrieve Performance Metrics (IRR, TVPI, etc.) from the Database.
    2. Refresh Calculations on demand.
    """
    def __init__(self, db_url=None):
        self.db_url = db_url or os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/private_markets_db")
        self.engine = create_engine(self.db_url)
        self.calculator = PECalculator(self.db_url)

    def refresh_data(self):
        """
        Triggers the calculation engine to update metrics in the DB.
        """
        print("Refeshing PE Metrics...")
        self.calculator.run_all()
        return "Metrics updated successfully."

    def get_fund_performance(self, fund_id=None):
        """
        Retrieves performance metrics for a specific fund or all funds.
        """
        return self._query_metrics("fund", fund_id)

    def get_portfolio_performance(self, company_id=None):
        """
        Retrieves performance metrics for portfolio companies.
        """
        return self._query_metrics("company", company_id)

    def get_deal_performance(self, deal_id=None):
        """
        Retrieves performance metrics for specific deals.
        """
        return self._query_metrics("deal", deal_id)

    def get_lp_performance(self, lp_id=None):
        """
        Retrieves performance metrics for Limited Partners.
        """
        return self._query_metrics("lp", lp_id)

    def _query_metrics(self, entity_type, entity_id=None):
        sql = """
        SELECT 
            entity_id, 
            irr, 
            tvpi, 
            dpi, 
            rvpi, 
            moic,
            total_invested,
            total_distributed,
            nav,
            calculation_date
        FROM computed_metrics 
        WHERE entity_type = :etype
        """
        params = {"etype": entity_type}
        
        if entity_id:
            sql += " AND entity_id = :eid"
            params["eid"] = entity_id
            
        try:
            with self.engine.connect() as conn:
                df = pd.read_sql(text(sql), conn, params=params)
            
            if df.empty:
                return f"No data found for {entity_type} {entity_id if entity_id else ''}"
            
            return df.to_markdown(index=False)
        except Exception as e:
            return f"Error querying database: {e}"

if __name__ == "__main__":
    # Test Run
    agent = PEAgent()
    # print(agent.refresh_data())
    print(agent.get_fund_performance())
