
import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from market_simulation.financial_datasets_provider import FinancialDatasetsProvider
from market_simulation.data_feed import DataFeed

class TestFinancialDatasetsExtended(unittest.TestCase):

    def setUp(self):
        self.api_key = "test_key"
        self.provider = FinancialDatasetsProvider(api_key=self.api_key)
        self.provider._make_request = MagicMock()

    def test_get_segmented_financials(self):
        # Mock response
        mock_response = {
            "business_segments": [{"name": "Gaming", "revenue": 100}],
            "geographic_segments": [{"name": "USA", "revenue": 200}]
        }
        self.provider._make_request.return_value = mock_response

        data = self.provider.get_segmented_financials('NVDA')
        
        self.provider._make_request.assert_called_with('/financials/segmented', {
            'ticker': 'NVDA', 'period': 'annual', 'limit': 5
        })
        self.assertEqual(data, mock_response)

    def test_get_sec_filings(self):
        # Mock response
        mock_response = {
            "filings": [
                {"type": "10-K", "filed_date": "2024-02-21"},
                {"type": "8-K", "filed_date": "2024-03-01"}
            ]
        }
        self.provider._make_request.return_value = mock_response

        data = self.provider.get_sec_filings('NVDA')
        
        self.provider._make_request.assert_called_with('/filings', {
            'ticker': 'NVDA', 'limit': 20
        })
        self.assertEqual(data, mock_response['filings'])

    @patch('market_simulation.data_feed.FinancialDatasetsProvider')
    def test_data_feed_integration(self, MockProvider):
        # Setup mock provider
        mock_instance = MockProvider.return_value
        mock_instance.get_segmented_financials.return_value = {"segments": []}
        mock_instance.get_sec_filings.return_value = [{"type": "8-K"}]
        mock_instance.get_aggregated_sentiment.return_value = 0.5

        # Initialize DataFeed
        feed = DataFeed()
        # Force inject the mock (since __init__ might fail if env var missing)
        feed.fd_provider = mock_instance

        # Test get_fundamental_data
        data = feed.get_fundamental_data('NVDA')

        self.assertIn('segmented_financials', data)
        self.assertIn('sec_filings', data)
        self.assertEqual(data['sec_filings'], [{"type": "8-K"}])

if __name__ == '__main__':
    unittest.main()
