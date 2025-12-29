import pandas as pd
import numpy as np
from pyxirr import xirr
from typing import Dict, List, Optional

class PrivateEquityEngine:
    """
    Core calculation engine for Private Equity metrics.
    Handles 4 Levels: Fund, Portfolio Company, Deal, LP.
    """

    @staticmethod
    def calculate_performance(cashflows: pd.DataFrame, level_id_col: str) -> pd.DataFrame:
        """
        Calculates IRR, TVPI, DPI, RVPI for a given grouping level.
        
        Args:
            cashflows: DataFrame with columns ['date', 'amount', 'type', level_id_col]
                       amount < 0 for contributions, amount > 0 for distributions.
            level_id_col: Column name to group by (e.g., 'fund_id', 'lp_id')
            
        Returns:
            DataFrame with performance metrics per entity.
        """
        results = []
        
        # Ensure date is datetime
        cashflows['date'] = pd.to_datetime(cashflows['date'])
        
        grouped = cashflows.groupby(level_id_col)
        
        for entity_id, group in grouped:
            group = group.sort_values('date')
            
            dates = group['date'].values
            amounts = group['amount'].values
            
            # 1. Cashflow Aggregation
            contributions = -amounts[amounts < 0].sum()
            distributions = amounts[amounts > 0].sum()
            
            # Handle NAV (Net Asset Value)
            # Assuming NAV is passed as a specific transaction type 'nav' at the end
            nav_rows = group[group['type'] == 'nav']
            nav = nav_rows['amount'].sum() if not nav_rows.empty else 0.0
            
            # If NAV is not in cashflows, it implies the investment is realized or NAV is 0
            # In a real system, NAV might be fetched from a separate valuation table.
            
            total_value = distributions + nav
            
            # 2. Multiples
            tvpi = total_value / contributions if contributions != 0 else 0.0
            dpi = distributions / contributions if contributions != 0 else 0.0
            rvpi = nav / contributions if contributions != 0 else 0.0
            
            # 3. IRR (Internal Rate of Return)
            try:
                # pyxirr is much faster than numpy.financial
                irr_val = xirr(dates, amounts)
            except Exception:
                irr_val = None

            results.append({
                level_id_col: entity_id,
                'contributions': contributions,
                'distributions': distributions,
                'nav': nav,
                'tvpi': round(tvpi, 4),
                'dpi': round(dpi, 4),
                'rvpi': round(rvpi, 4),
                'irr': round(irr_val, 6) if irr_val else None
            })
            
        return pd.DataFrame(results)

    @staticmethod
    def net_gross_adjustment(metrics_df: pd.DataFrame, fee_load: float = 0.0) -> pd.DataFrame:
        """
        Simple adjuster to estimate Net from Gross if raw data is Gross.
        """
        # This is a placeholder for complex waterfall logic
        df = metrics_df.copy()
        if 'irr' in df.columns:
            df['net_irr'] = df['irr'] - fee_load
        return df

    def run_full_analysis(self, all_cashflows: pd.DataFrame):
        """
        Runs analysis for all 4 levels and returns a dictionary of DataFrames.
        """
        levels = {
            'fund_level': 'fund_id',
            'portfolio_level': 'company_id',
            'deal_level': 'deal_id',
            'lp_level': 'lp_id'
        }
        
        outputs = {}
        for level_name, col in levels.items():
            if col in all_cashflows.columns:
                print(f"Calculating metrics for {level_name}...")
                outputs[level_name] = self.calculate_performance(all_cashflows, col)
        
        return outputs