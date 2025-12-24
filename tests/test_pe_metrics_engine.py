"""
Unit tests for PE Metrics Engine.

Tests all PE metric calculation functions including IRR, TVPI, DPI, etc.
"""

import unittest
from datetime import datetime, date
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from engines.pe_metrics_engine import (
    calculate_xirr,
    calculate_tvpi,
    calculate_dpi,
    calculate_rvpi,
    calculate_moic,
    calculate_called_percent,
    calculate_distributed_percent,
    calculate_all_metrics,
    aggregate_metrics
)


class TestIRRCalculation(unittest.TestCase):
    """Test IRR (XIRR) calculation."""
    
    def test_simple_irr(self):
        """Test IRR with simple cash flows."""
        cash_flows = [-100000, 10000, 20000, 30000, 50000]
        dates = [
            datetime(2020, 1, 1),
            datetime(2021, 1, 1),
            datetime(2022, 1, 1),
            datetime(2023, 1, 1),
            datetime(2024, 1, 1)
        ]
        
        irr = calculate_xirr(cash_flows, dates)
        
        self.assertIsNotNone(irr)
        self.assertGreater(irr, 0)
        self.assertLess(irr, 1)  # Should be less than 100%
    
    def test_negative_irr(self):
        """Test IRR with losses."""
        cash_flows = [-100000, 10000, 20000, 30000]
        dates = [
            datetime(2020, 1, 1),
            datetime(2021, 1, 1),
            datetime(2022, 1, 1),
            datetime(2023, 1, 1)
        ]
        
        irr = calculate_xirr(cash_flows, dates)
        
        self.assertIsNotNone(irr)
        self.assertLess(irr, 0)  # Loss scenario
    
    def test_insufficient_cash_flows(self):
        """Test IRR with insufficient data."""
        cash_flows = [-100000]
        dates = [datetime(2020, 1, 1)]
        
        irr = calculate_xirr(cash_flows, dates)
        
        self.assertIsNone(irr)
    
    def test_mismatched_lengths(self):
        """Test IRR with mismatched cash flows and dates."""
        cash_flows = [-100000, 10000]
        dates = [datetime(2020, 1, 1)]
        
        irr = calculate_xirr(cash_flows, dates)
        
        self.assertIsNone(irr)


class TestBasicMetrics(unittest.TestCase):
    """Test basic PE metrics calculations."""
    
    def test_tvpi_calculation(self):
        """Test TVPI calculation."""
        tvpi = calculate_tvpi(total_value=150000, paid_in=100000)
        
        self.assertEqual(tvpi, 1.5)
    
    def test_tvpi_zero_paid_in(self):
        """Test TVPI with zero paid-in."""
        tvpi = calculate_tvpi(total_value=150000, paid_in=0)
        
        self.assertIsNone(tvpi)
    
    def test_dpi_calculation(self):
        """Test DPI calculation."""
        dpi = calculate_dpi(distributions=80000, paid_in=100000)
        
        self.assertEqual(dpi, 0.8)
    
    def test_rvpi_calculation(self):
        """Test RVPI calculation."""
        rvpi = calculate_rvpi(nav=70000, paid_in=100000)
        
        self.assertEqual(rvpi, 0.7)
    
    def test_moic_calculation(self):
        """Test MoIC calculation."""
        moic = calculate_moic(total_value=200000, invested_capital=100000)
        
        self.assertEqual(moic, 2.0)
    
    def test_called_percent(self):
        """Test called percentage calculation."""
        called_pct = calculate_called_percent(paid_in=75000, commitment=100000)
        
        self.assertEqual(called_pct, 75.0)
    
    def test_distributed_percent(self):
        """Test distributed percentage calculation."""
        dist_pct = calculate_distributed_percent(distributions=50000, commitment=100000)
        
        self.assertEqual(dist_pct, 50.0)


class TestComprehensiveMetrics(unittest.TestCase):
    """Test comprehensive metric calculation."""
    
    def test_calculate_all_metrics(self):
        """Test calculating all metrics at once."""
        cash_flows = [-100000, -20000, 30000, 40000]
        dates = [
            datetime(2020, 1, 1),
            datetime(2020, 6, 1),
            datetime(2021, 1, 1),
            datetime(2022, 1, 1)
        ]
        total_commitment = 150000
        current_nav = 60000
        
        metrics = calculate_all_metrics(
            cash_flows=cash_flows,
            dates=dates,
            total_commitment=total_commitment,
            current_nav=current_nav
        )
        
        # Verify all expected keys are present
        expected_keys = [
            'paid_in', 'distributions', 'current_nav', 'total_value',
            'total_commitment', 'unfunded_commitment', 'irr', 'tvpi',
            'dpi', 'rvpi', 'moic', 'called_percent', 'distributed_percent'
        ]
        
        for key in expected_keys:
            self.assertIn(key, metrics)
        
        # Verify calculations
        self.assertEqual(metrics['paid_in'], 120000)
        self.assertEqual(metrics['distributions'], 70000)
        self.assertEqual(metrics['current_nav'], 60000)
        self.assertEqual(metrics['total_value'], 130000)
        self.assertEqual(metrics['unfunded_commitment'], 30000)
        
        # TVPI should be (70000 + 60000) / 120000 = 1.0833...
        self.assertAlmostEqual(metrics['tvpi'], 1.0833, places=2)
        
        # DPI should be 70000 / 120000 = 0.583
        self.assertAlmostEqual(metrics['dpi'], 0.583, places=2)


class TestAggregateMetrics(unittest.TestCase):
    """Test metric aggregation across funds."""
    
    def test_aggregate_multiple_funds(self):
        """Test aggregating metrics from multiple funds."""
        fund1_metrics = {
            'paid_in': 100000,
            'distributions': 50000,
            'current_nav': 60000,
            'total_commitment': 150000
        }
        
        fund2_metrics = {
            'paid_in': 200000,
            'distributions': 100000,
            'current_nav': 120000,
            'total_commitment': 250000
        }
        
        aggregated = aggregate_metrics([fund1_metrics, fund2_metrics])
        
        # Verify aggregated values
        self.assertEqual(aggregated['paid_in'], 300000)
        self.assertEqual(aggregated['distributions'], 150000)
        self.assertEqual(aggregated['current_nav'], 180000)
        self.assertEqual(aggregated['total_value'], 330000)
        self.assertEqual(aggregated['total_commitment'], 400000)
        self.assertEqual(aggregated['fund_count'], 2)
        
        # Verify calculated metrics
        self.assertAlmostEqual(aggregated['tvpi'], 1.1, places=2)
    
    def test_aggregate_empty_list(self):
        """Test aggregating with no funds."""
        aggregated = aggregate_metrics([])
        
        self.assertEqual(aggregated, {})
    
    def test_aggregate_single_fund(self):
        """Test aggregating a single fund."""
        fund_metrics = {
            'paid_in': 100000,
            'distributions': 50000,
            'current_nav': 60000,
            'total_commitment': 150000
        }
        
        aggregated = aggregate_metrics([fund_metrics])
        
        self.assertEqual(aggregated['fund_count'], 1)
        self.assertEqual(aggregated['paid_in'], 100000)


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and boundary conditions."""
    
    def test_zero_distributions(self):
        """Test metrics with no distributions yet."""
        metrics = calculate_all_metrics(
            cash_flows=[-100000],
            dates=[datetime(2020, 1, 1)],
            total_commitment=200000,
            current_nav=105000
        )
        
        self.assertEqual(metrics['distributions'], 0)
        self.assertEqual(metrics['dpi'], 0)
        self.assertGreater(metrics['rvpi'], 1.0)  # NAV appreciation
    
    def test_fully_realized(self):
        """Test metrics for fully exited fund."""
        metrics = calculate_all_metrics(
            cash_flows=[-100000, 150000],
            dates=[datetime(2020, 1, 1), datetime(2023, 1, 1)],
            total_commitment=100000,
            current_nav=0
        )
        
        self.assertEqual(metrics['current_nav'], 0)
        self.assertEqual(metrics['distributions'], 150000)
        self.assertEqual(metrics['rvpi'], 0)
        self.assertEqual(metrics['dpi'], 1.5)
        self.assertEqual(metrics['tvpi'], 1.5)


if __name__ == '__main__':
    unittest.main()
