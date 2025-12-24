"""
Unit tests for Cash Flow Engine.

Tests cash flow processing, aggregation, and analysis functions.
"""

import unittest
from datetime import datetime, date
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from engines.cash_flow_engine import (
    CashFlow,
    CashFlowType,
    AggregationPeriod,
    aggregate_by_period,
    calculate_cumulative_cash_flows,
    separate_calls_and_distributions,
    calculate_net_cash_flow,
    filter_by_date_range,
    filter_by_fund,
    calculate_j_curve,
    calculate_ytd_metrics,
    generate_cash_flow_summary
)


class TestCashFlowClass(unittest.TestCase):
    """Test CashFlow class functionality."""
    
    def test_create_cash_flow(self):
        """Test creating a CashFlow object."""
        cf = CashFlow(
            transaction_id=1,
            fund_id=100,
            date=datetime(2020, 1, 1),
            cf_type='call_investment',
            amount=-50000
        )
        
        self.assertEqual(cf.fund_id, 100)
        self.assertEqual(cf.amount, -50000)
        self.assertTrue(cf.is_call())
        self.assertFalse(cf.is_distribution())
    
    def test_is_distribution(self):
        """Test distribution identification."""
        cf = CashFlow(
            transaction_id=2,
            fund_id=100,
            date=datetime(2021, 1, 1),
            cf_type='distribution_profit',
            amount=30000
        )
        
        self.assertTrue(cf.is_distribution())
        self.assertFalse(cf.is_call())


class TestAggregation(unittest.TestCase):
    """Test cash flow aggregation functions."""
    
    def setUp(self):
        """Set up test cash flows."""
        self.cash_flows = [
            CashFlow(1, 100, datetime(2020, 1, 15), 'call', -50000),
            CashFlow(2, 100, datetime(2020, 3, 20), 'call', -30000),
            CashFlow(3, 100, datetime(2020, 7, 10), 'dist', 20000),
            CashFlow(4, 100, datetime(2021, 2, 15), 'call', -40000),
            CashFlow(5, 100, datetime(2021, 6, 20), 'dist', 60000),
            CashFlow(6, 100, datetime(2022, 1, 10), 'dist', 80000)
        ]
    
    def test_aggregate_by_year(self):
        """Test yearly aggregation."""
        aggregated = aggregate_by_period(self.cash_flows, AggregationPeriod.YEARLY)
        
        self.assertEqual(aggregated['2020'], -60000)
        self.assertEqual(aggregated['2021'], 20000)
        self.assertEqual(aggregated['2022'], 80000)
    
    def test_aggregate_by_quarter(self):
        """Test quarterly aggregation."""
        aggregated = aggregate_by_period(self.cash_flows, AggregationPeriod.QUARTERLY)
        
        self.assertIn('2020-Q1', aggregated)
        self.assertIn('2020-Q3', aggregated)
        self.assertEqual(aggregated['2020-Q1'], -80000)
        self.assertEqual(aggregated['2020-Q3'], 20000)
    
    def test_aggregate_all_time(self):
        """Test all-time aggregation."""
        aggregated = aggregate_by_period(self.cash_flows, AggregationPeriod.ALL_TIME)
        
        self.assertEqual(len(aggregated), 1)
        self.assertIn('all_time', aggregated)
        self.assertEqual(aggregated['all_time'], 40000)  # Net of all flows


class TestCumulativeCalculations(unittest.TestCase):
    """Test cumulative cash flow calculations."""
    
    def test_calculate_cumulative(self):
        """Test cumulative cash flow calculation."""
        cash_flows = [
            CashFlow(1, 100, datetime(2020, 1, 1), 'call', -100000),
            CashFlow(2, 100, datetime(2020, 6, 1), 'call', -50000),
            CashFlow(3, 100, datetime(2021, 1, 1), 'dist', 30000),
            CashFlow(4, 100, datetime(2022, 1, 1), 'dist', 80000)
        ]
        
        cumulative = calculate_cumulative_cash_flows(cash_flows)
        
        self.assertEqual(len(cumulative), 4)
        self.assertEqual(cumulative[0][1], -100000)
        self.assertEqual(cumulative[1][1], -150000)
        self.assertEqual(cumulative[2][1], -120000)
        self.assertEqual(cumulative[3][1], -40000)


class TestSeparation(unittest.TestCase):
    """Test separation of calls and distributions."""
    
    def test_separate_calls_and_distributions(self):
        """Test separating calls from distributions."""
        cash_flows = [
            CashFlow(1, 100, datetime(2020, 1, 1), 'call_investment', -80000),
            CashFlow(2, 100, datetime(2020, 1, 1), 'call_fees', -2000),
            CashFlow(3, 100, datetime(2021, 1, 1), 'distribution', 50000),
            CashFlow(4, 100, datetime(2022, 1, 1), 'distribution', 60000)
        ]
        
        calls, distributions = separate_calls_and_distributions(cash_flows)
        
        self.assertEqual(len(calls), 2)
        self.assertEqual(len(distributions), 2)
    
    def test_separate_exclude_fees(self):
        """Test separating with fees excluded."""
        cash_flows = [
            CashFlow(1, 100, datetime(2020, 1, 1), 'call_investment', -80000),
            CashFlow(2, 100, datetime(2020, 1, 1), 'call_fees', -2000),
            CashFlow(3, 100, datetime(2021, 1, 1), 'distribution', 50000)
        ]
        
        calls, distributions = separate_calls_and_distributions(
            cash_flows, include_fees=False
        )
        
        self.assertEqual(len(calls), 1)  # Only investment, not fees


class TestNetCashFlow(unittest.TestCase):
    """Test net cash flow calculations."""
    
    def test_calculate_net_positive(self):
        """Test net cash flow when distributions exceed calls."""
        calls = [
            CashFlow(1, 100, datetime(2020, 1, 1), 'call', -100000)
        ]
        distributions = [
            CashFlow(2, 100, datetime(2021, 1, 1), 'dist', 150000)
        ]
        
        net = calculate_net_cash_flow(calls, distributions)
        
        self.assertEqual(net, 50000)
    
    def test_calculate_net_negative(self):
        """Test net cash flow when calls exceed distributions."""
        calls = [
            CashFlow(1, 100, datetime(2020, 1, 1), 'call', -100000),
            CashFlow(2, 100, datetime(2020, 6, 1), 'call', -50000)
        ]
        distributions = [
            CashFlow(3, 100, datetime(2021, 1, 1), 'dist', 80000)
        ]
        
        net = calculate_net_cash_flow(calls, distributions)
        
        self.assertEqual(net, -70000)


class TestFiltering(unittest.TestCase):
    """Test cash flow filtering functions."""
    
    def setUp(self):
        """Set up test cash flows."""
        self.cash_flows = [
            CashFlow(1, 100, datetime(2020, 1, 1), 'call', -50000),
            CashFlow(2, 101, datetime(2020, 6, 1), 'call', -30000),
            CashFlow(3, 100, datetime(2021, 1, 1), 'dist', 40000),
            CashFlow(4, 102, datetime(2021, 6, 1), 'dist', 60000),
            CashFlow(5, 100, datetime(2022, 1, 1), 'dist', 80000)
        ]
    
    def test_filter_by_date_range(self):
        """Test filtering by date range."""
        filtered = filter_by_date_range(
            self.cash_flows,
            start_date=datetime(2020, 6, 1),
            end_date=datetime(2021, 6, 1)
        )
        
        self.assertEqual(len(filtered), 3)
    
    def test_filter_by_fund(self):
        """Test filtering by fund ID."""
        filtered = filter_by_fund(self.cash_flows, fund_ids=[100])
        
        self.assertEqual(len(filtered), 3)
        for cf in filtered:
            self.assertEqual(cf.fund_id, 100)
    
    def test_filter_multiple_funds(self):
        """Test filtering by multiple fund IDs."""
        filtered = filter_by_fund(self.cash_flows, fund_ids=[100, 101])
        
        self.assertEqual(len(filtered), 4)


class TestJCurve(unittest.TestCase):
    """Test J-Curve calculation."""
    
    def test_calculate_j_curve_yearly(self):
        """Test J-Curve calculation with yearly aggregation."""
        cash_flows = [
            CashFlow(1, 100, datetime(2020, 1, 1), 'call', -100000),
            CashFlow(2, 100, datetime(2020, 6, 1), 'call', -50000),
            CashFlow(3, 100, datetime(2021, 1, 1), 'dist', 30000),
            CashFlow(4, 100, datetime(2022, 1, 1), 'dist', 80000),
            CashFlow(5, 100, datetime(2023, 1, 1), 'dist', 100000)
        ]
        
        j_curve = calculate_j_curve(cash_flows, AggregationPeriod.YEARLY)
        
        # Verify structure
        self.assertEqual(len(j_curve), 4)  # 2020-2023
        
        # Verify first period (2020) is negative
        self.assertEqual(j_curve[0]['period'], '2020')
        self.assertEqual(j_curve[0]['net_flow'], -150000)
        self.assertEqual(j_curve[0]['cumulative_flow'], -150000)
        
        # Verify cumulative progression
        self.assertEqual(j_curve[1]['cumulative_flow'], -120000)
        self.assertEqual(j_curve[2]['cumulative_flow'], -40000)
        self.assertEqual(j_curve[3]['cumulative_flow'], 60000)


class TestYTDMetrics(unittest.TestCase):
    """Test year-to-date metrics calculation."""
    
    def test_calculate_ytd(self):
        """Test YTD metrics calculation."""
        cash_flows = [
            CashFlow(1, 100, datetime(2023, 1, 15), 'call', -50000),
            CashFlow(2, 100, datetime(2023, 3, 20), 'call', -30000),
            CashFlow(3, 100, datetime(2023, 6, 10), 'dist', 60000),
            CashFlow(4, 100, datetime(2022, 12, 31), 'dist', 40000)
        ]
        
        ytd = calculate_ytd_metrics(cash_flows, datetime(2023, 7, 1))
        
        self.assertEqual(ytd['ytd_calls'], 80000)
        self.assertEqual(ytd['ytd_distributions'], 60000)
        self.assertEqual(ytd['ytd_net_flow'], -20000)
        self.assertEqual(ytd['reference_year'], 2023)


class TestCashFlowSummary(unittest.TestCase):
    """Test comprehensive cash flow summary generation."""
    
    def test_generate_summary(self):
        """Test generating a complete cash flow summary."""
        cash_flows = [
            CashFlow(1, 100, datetime(2020, 1, 1), 'call', -100000),
            CashFlow(2, 100, datetime(2020, 6, 1), 'call', -50000),
            CashFlow(3, 100, datetime(2021, 1, 1), 'dist', 80000),
            CashFlow(4, 100, datetime(2022, 1, 1), 'dist', 120000)
        ]
        
        summary = generate_cash_flow_summary(cash_flows)
        
        # Verify all expected fields
        self.assertIn('total_calls', summary)
        self.assertIn('total_distributions', summary)
        self.assertIn('net_cash_flow', summary)
        self.assertIn('j_curve', summary)
        self.assertIn('ytd_metrics', summary)
        
        # Verify calculations
        self.assertEqual(summary['total_calls'], 150000)
        self.assertEqual(summary['total_distributions'], 200000)
        self.assertEqual(summary['net_cash_flow'], 50000)


if __name__ == '__main__':
    unittest.main()
