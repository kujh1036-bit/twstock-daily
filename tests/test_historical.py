import unittest

from app.historical import normalize_historical_rows


class HistoricalDatabaseTests(unittest.TestCase):
    def test_normalizes_and_filters_history(self):
        rows = [{
            'date': '2023-10-11', 'market': 'TWSE', 'stock_id': '2330', 'name': '台積電',
            'open': '550', 'high': '555', 'low': '548', 'close': '552', 'change': '2',
            'volume': '123456', 'turnover': '68000000', 'transactions': '999',
        }, {
            'date': '2023-10-11', 'market': 'TWSE', 'stock_id': '0050', 'name': 'ETF',
            'open': '100', 'high': '101', 'low': '99', 'close': '100', 'change': '0',
            'volume': '1', 'turnover': '100', 'transactions': '1',
        }]
        result = normalize_historical_rows(rows, 'TWSE', {'2330'}, minimum_rows=1)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['stock_id'], '2330')
        self.assertEqual(result[0]['turnover'], 68000000)
        self.assertEqual(result[0]['source'], 'TWSE_MI_INDEX')


if __name__ == '__main__':
    unittest.main()
