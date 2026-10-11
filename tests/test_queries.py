import datetime as dt
import pathlib
import tempfile
import unittest

from sqlalchemy import insert

from app import database
from app.queries import find_limit_up_stocks, limit_up_price, price_tick


class LimitUpQueryTests(unittest.TestCase):
    def test_price_ticks_and_limit_rounding(self):
        self.assertEqual(str(price_tick('9.99')), '0.01')
        self.assertEqual(str(price_tick('10')), '0.05')
        self.assertEqual(str(price_tick('100')), '0.5')
        self.assertEqual(str(limit_up_price('5.35')), '5.88')
        self.assertEqual(str(limit_up_price('180.5')), '198.5')
        self.assertEqual(str(limit_up_price('3020')), '3320')

    def test_finds_only_exact_limit_up_close(self):
        with tempfile.TemporaryDirectory() as folder:
            path = pathlib.Path(folder) / 'test.sqlite3'
            engine = database.connect(f'sqlite:///{path.as_posix()}')
            now = dt.datetime.now(dt.timezone.utc)
            common = {
                'trade_date': dt.date(2026, 10, 8), 'market': 'TWSE',
                'open': 180, 'low': 180, 'volume': 1000, 'turnover': 198500,
                'transactions': 10, 'source': 'test', 'fetched_at': now,
            }
            with engine.begin() as connection:
                connection.execute(insert(database.daily_prices), [
                    {**common, 'stock_id': '1001', 'name': '漲停股', 'high': 198.5,
                     'close': 198.5, 'change': 18},
                    {**common, 'stock_id': '1002', 'name': '非漲停股', 'high': 198,
                     'close': 198, 'change': 17.5},
                ])
                rows = find_limit_up_stocks(connection, '2026-10-08')
            engine.dispose()

            self.assertEqual([row['stock_id'] for row in rows], ['1001'])
            self.assertEqual(str(rows[0]['limit_up_price']), '198.5')


if __name__ == '__main__':
    unittest.main()
