"""
Database Adapter Layer.

This module provides a clean interface between the computation engines and the database.
It handles all database queries and converts results into formats suitable for computation engines.
"""

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
import json

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from config import DB_CONFIG
from engines.cash_flow_engine import CashFlow
from engines.pe_metrics_engine import calculate_all_metrics, aggregate_metrics

logger = logging.getLogger(__name__)


# ==============================================================================
# DATABASE CONNECTION
# ==============================================================================

class DatabaseConnection:
    """Manages database connection lifecycle."""
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize database connection.
        
        Args:
            config: Database configuration dict (defaults to DB_CONFIG from config.py)
        """
        self.config = config or DB_CONFIG
        self.conn = None
        self._connect()
    
    def _connect(self):
        """Establish database connection."""
        try:
            self.conn = psycopg2.connect(**self.config)
            logger.info("✅ Connected to PostgreSQL database")
        except Exception as e:
            logger.error(f"❌ Database connection failed: {e}")
            self.conn = None
    
    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")
    
    def execute_query(
        self,
        query: str,
        params: Tuple = None,
        fetch: str = "all"
    ) -> Any:
        """
        Execute a SQL query.
        
        Args:
            query: SQL query string
            params: Query parameters
            fetch: 'all', 'one', or 'none'
            
        Returns:
            Query results based on fetch parameter
        """
        if not self.conn:
            logger.error("No database connection available")
            return None
        
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                logger.debug(f"Executing query: {query[:100]}...")
                cur.execute(query, params or ())
                
                if fetch == "all":
                    return cur.fetchall()
                elif fetch == "one":
                    return cur.fetchone()
                else:  # none
                    self.conn.commit()
                    return None
        except Exception as e:
            logger.error(f"Query execution error: {e}")
            self.conn.rollback()
            return None


# ==============================================================================
# DATA RETRIEVAL FUNCTIONS
# ==============================================================================

def get_fund_list(
    db: DatabaseConnection,
    strategy: Optional[str] = None,
    sub_strategy: Optional[str] = None,
    is_active: bool = True
) -> List[Dict[str, Any]]:
    """
    Get list of funds with optional filtering.
    
    Args:
        db: Database connection
        strategy: Filter by primary strategy
        sub_strategy: Filter by sub-strategy
        is_active: Include only active funds
        
    Returns:
        List of fund dictionaries
    """
    query = """
        SELECT 
            fund_id,
            fund_name,
            vintage_year,
            primary_strategy,
            sub_strategy,
            total_commitment_usd as total_commitment,
            is_active
        FROM pe_portfolio
        WHERE 1=1
    """
    params = []
    
    if is_active:
        query += " AND is_active = %s"
        params.append(True)
    
    if strategy:
        query += " AND primary_strategy = %s"
        params.append(strategy)
    
    if sub_strategy:
        query += " AND sub_strategy = %s"
        params.append(sub_strategy)
    
    query += " ORDER BY fund_name"
    
    results = db.execute_query(query, tuple(params))
    return [dict(row) for row in results] if results else []


def get_cash_flows(
    db: DatabaseConnection,
    fund_id: Optional[int] = None,
    strategy: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> List[CashFlow]:
    """
    Get cash flows from database.
    
    Args:
        db: Database connection
        fund_id: Filter by fund ID
        strategy: Filter by strategy
        start_date: Filter by start date
        end_date: Filter by end date
        
    Returns:
        List of CashFlow objects
    """
    query = """
        SELECT 
            cf.transaction_id,
            cf.fund_id,
            cf.transaction_date,
            cf.transaction_type,
            cf.investment_paid_in_usd,
            cf.management_fees_usd,
            cf.return_of_cost_distribution_usd,
            cf.profit_distribution_usd,
            cf.net_asset_value_usd
        FROM pe_historical_cash_flows cf
        LEFT JOIN pe_portfolio p ON cf.fund_id = p.fund_id
        WHERE 1=1
    """
    params = []
    
    if fund_id:
        query += " AND cf.fund_id = %s"
        params.append(fund_id)
    
    if strategy:
        query += " AND p.primary_strategy = %s"
        params.append(strategy)
    
    if start_date:
        query += " AND cf.transaction_date >= %s"
        params.append(start_date)
    
    if end_date:
        query += " AND cf.transaction_date <= %s"
        params.append(end_date)
    
    query += " ORDER BY cf.transaction_date"
    
    results = db.execute_query(query, tuple(params))
    
    if not results:
        return []
    
    cash_flows = []
    for row in results:
        # Create separate CashFlow objects for each transaction component
        
        # Investment (negative)
        if row['investment_paid_in_usd']:
            cash_flows.append(CashFlow(
                transaction_id=row['transaction_id'],
                fund_id=row['fund_id'],
                date=row['transaction_date'],
                cf_type='call_investment',
                amount=row['investment_paid_in_usd']  # Already negative in DB
            ))
        
        # Fees (negative)
        if row['management_fees_usd']:
            cash_flows.append(CashFlow(
                transaction_id=row['transaction_id'],
                fund_id=row['fund_id'],
                date=row['transaction_date'],
                cf_type='call_fees',
                amount=row['management_fees_usd']  # Already negative in DB
            ))
        
        # Return of capital distribution (positive)
        if row['return_of_cost_distribution_usd']:
            cash_flows.append(CashFlow(
                transaction_id=row['transaction_id'],
                fund_id=row['fund_id'],
                date=row['transaction_date'],
                cf_type='distribution_return_of_capital',
                amount=row['return_of_cost_distribution_usd']
            ))
        
        # Profit distribution (positive)
        if row['profit_distribution_usd']:
            cash_flows.append(CashFlow(
                transaction_id=row['transaction_id'],
                fund_id=row['fund_id'],
                date=row['transaction_date'],
                cf_type='distribution_profit',
                amount=row['profit_distribution_usd']
            ))
    
    logger.info(f"Retrieved {len(cash_flows)} cash flow transactions")
    return cash_flows


def get_latest_nav(
    db: DatabaseConnection,
    fund_id: int
) -> Optional[float]:
    """
    Get the latest NAV for a fund.
    
    Args:
        db: Database connection
        fund_id: Fund ID
        
    Returns:
        Latest NAV value or None
    """
    query = """
        SELECT net_asset_value_usd
        FROM pe_historical_cash_flows
        WHERE fund_id = %s
        AND net_asset_value_usd IS NOT NULL
        ORDER BY transaction_date DESC
        LIMIT 1
    """
    
    result = db.execute_query(query, (fund_id,), fetch="one")
    return float(result['net_asset_value_usd']) if result else None


def get_modeling_assumptions(
    db: DatabaseConnection,
    strategy: str
) -> Optional[Dict[str, Any]]:
    """
    Get modeling assumptions for a strategy.
    
    Args:
        db: Database connection
        strategy: Primary strategy name
        
    Returns:
        Dictionary with modeling assumptions or None
    """
    query = """
        SELECT 
            primary_strategy,
            expected_moic_gross_multiple as expected_moic,
            target_irr_net_percentage as target_irr,
            investment_period_years,
            fund_life_years,
            nav_initial_qtr_depreciation,
            nav_initial_depreciation_qtrs,
            j_curve_model_description,
            modeling_rationale
        FROM pe_modeling_rules
        WHERE primary_strategy = %s
    """
    
    result = db.execute_query(query, (strategy,), fetch="one")
    return dict(result) if result else None


# ==============================================================================
# METRIC CALCULATION WITH DATABASE
# ==============================================================================

def calculate_fund_metrics(
    db: DatabaseConnection,
    fund_id: int
) -> Optional[Dict[str, Any]]:
    """
    Calculate all metrics for a specific fund.
    
    Args:
        db: Database connection
        fund_id: Fund ID
        
    Returns:
        Dictionary with all calculated metrics
    """
    # Get fund info
    fund_query = """
        SELECT fund_name, vintage_year, primary_strategy, total_commitment_usd
        FROM pe_portfolio WHERE fund_id = %s
    """
    fund_info = db.execute_query(fund_query, (fund_id,), fetch="one")
    if not fund_info:
        logger.warning(f"Fund {fund_id} not found")
        return None
    
    # Get cash flows
    cash_flows = get_cash_flows(db, fund_id=fund_id)
    
    # Get latest NAV
    current_nav = get_latest_nav(db, fund_id) or 0
    
    # Convert CashFlow objects to lists for calculation
    cf_amounts = [cf.amount for cf in cash_flows]
    cf_dates = [cf.date for cf in cash_flows]
    
    # Calculate metrics
    metrics = calculate_all_metrics(
        cash_flows=cf_amounts,
        dates=cf_dates,
        total_commitment=float(fund_info['total_commitment_usd']),
        current_nav=current_nav
    )
    
    # Add fund metadata
    metrics.update({
        "fund_id": fund_id,
        "fund_name": fund_info['fund_name'],
        "vintage_year": fund_info['vintage_year'],
        "primary_strategy": fund_info['primary_strategy']
    })
    
    logger.info(f"Calculated metrics for fund {fund_id}: {fund_info['fund_name']}")
    return metrics


def calculate_strategy_metrics(
    db: DatabaseConnection,
    strategy: str,
    sub_strategy: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Calculate aggregated metrics for a strategy or sub-strategy.
    
    Args:
        db: Database connection
        strategy: Primary strategy name
        sub_strategy: Optional sub-strategy name
        
    Returns:
        Dictionary with aggregated metrics
    """
    # Get all funds in the strategy
    funds = get_fund_list(db, strategy=strategy, sub_strategy=sub_strategy)
    
    if not funds:
        logger.warning(f"No funds found for strategy: {strategy}")
        return None
    
    # Calculate metrics for each fund
    fund_metrics = []
    for fund in funds:
        metrics = calculate_fund_metrics(db, fund['fund_id'])
        if metrics:
            fund_metrics.append(metrics)
    
    # Aggregate metrics
    aggregated = aggregate_metrics(fund_metrics)
    aggregated.update({
        "hierarchy_level": "SUB_STRATEGY" if sub_strategy else "STRATEGY",
        "primary_strategy": strategy,
        "sub_strategy": sub_strategy
    })
    
    logger.info(f"Calculated aggregated metrics for {strategy}" + 
                (f" / {sub_strategy}" if sub_strategy else ""))
    return aggregated


def calculate_portfolio_metrics(db: DatabaseConnection) -> Optional[Dict[str, Any]]:
    """
    Calculate metrics for entire portfolio.
    
    Args:
        db: Database connection
        
    Returns:
        Dictionary with portfolio-level metrics
    """
    # Get all active funds
    funds = get_fund_list(db, is_active=True)
    
    if not funds:
        logger.warning("No active funds found in portfolio")
        return None
    
    # Calculate metrics for each fund
    fund_metrics = []
    for fund in funds:
        metrics = calculate_fund_metrics(db, fund['fund_id'])
        if metrics:
            fund_metrics.append(metrics)
    
    # Aggregate metrics
    aggregated = aggregate_metrics(fund_metrics)
    aggregated.update({
        "hierarchy_level": "PORTFOLIO"
    })
    
    logger.info(f"Calculated portfolio metrics for {len(fund_metrics)} funds")
    return aggregated


# ==============================================================================
# DATA CACHING
# ==============================================================================

def cache_metrics(
    db: DatabaseConnection,
    hierarchy_level: str,
    identifier: str,
    metrics: Dict[str, Any]
) -> bool:
    """
    Cache calculated metrics in database.
    
    Args:
        db: Database connection
        hierarchy_level: 'PORTFOLIO', 'STRATEGY', 'SUB_STRATEGY', or 'FUND'
        identifier: Identifier (fund_id, strategy name, etc.)
        metrics: Metrics dictionary to cache
        
    Returns:
        True if successful, False otherwise
    """
    # This would insert/update a cache table
    # For now, just log it
    logger.info(f"Would cache metrics for {hierarchy_level}: {identifier}")
    return True
