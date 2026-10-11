import datetime as dt
import pathlib
import tempfile
import unittest
from unittest import mock

from sqlalchemy import func, select

from app import database
from app.normalize import normalize_tpex, normalize_twse, parse_date
from app.pipeline import run_update


def instrument_rows(market, count=120):
    if market == 'TPEX':
        return [
            {'SecuritiesCompanyCode': str(1000 + i), 'CompanyAbbreviation': f'{market}{i}',
             'SecuritiesIndustryCode': '33', 'DateOfListing': '20200102'}
            for i in range(count)
        ]
    return [
        {'公司代號': str(1000 + i), '公司簡稱': f'{market}{i}', '產業別': '測試業', '上市日期': '2020/01/02'}
        for i in range(count)
    ]


def twse_rows(count=120):
    return [
        {'Date': '20261008', 'Code': str(1000 + i), 'Name': f'TWSE{i}',
         'TradeVolume': '1,000', 'TradeValue': '100,000', 'OpeningPrice': '99',
         'HighestPrice': '102', 'LowestPrice': '98', 'ClosingPrice': '100',
         'Change': '+1', 'Transaction': '10'}
        for i in range(count)
    ]


def tpex_rows(count=120):
    return [
        {'Date': '1151008', 'SecuritiesCompanyCode': str(1000 + i), 'CompanyName': f'TPEX{i}',
         'TradingShares': '2,000', 'TransactionAmount': '200,000', 'Open': '49',
         'High': '52', 'Low': '48', 'Close': '50', 'Change': '+1', 'TransactionNumber': '20'}
        for i in range(count)
    ]


class OfficialDatabaseTests(unittest.TestCase):
    def test_roc_and_gregorian_dates(self):
        self.assertEqual(parse_date('115/10/08'), dt.date(2026, 10, 8))
        self.assertEqual(parse_date('20261008'), dt.date(2026, 10, 8))

    def test_master_list_filters_non_company_products(self):
        allowed = {'2330'}
        twse = twse_rows(1)
        twse[0]['Code'] = '2330'
        twse.append({**twse[0], 'Code': '0050'})
        tpex = tpex_rows(1)
        tpex[0]['SecuritiesCompanyCode'] = '2330'
        tpex.append({**tpex[0], 'SecuritiesCompanyCode': '00679B'})
        self.assertEqual([row['stock_id'] for row in normalize_twse(twse, allowed)], ['2330'])
        self.assertEqual([row['stock_id'] for row in normalize_tpex(tpex, allowed)], ['2330'])

    def test_pipeline_is_idempotent_and_writes_both_markets(self):
        with tempfile.TemporaryDirectory() as folder:
            db_path = pathlib.Path(folder) / 'test.sqlite3'
            url = f'sqlite:///{db_path.as_posix()}'
            patches = (
                mock.patch('app.pipeline.twse.fetch_instruments', return_value=instrument_rows('TWSE')),
                mock.patch('app.pipeline.tpex.fetch_instruments', return_value=instrument_rows('TPEX')),
                mock.patch('app.pipeline.twse.fetch_daily', return_value=twse_rows()),
                mock.patch('app.pipeline.tpex.fetch_daily', return_value=tpex_rows()),
            )
            with patches[0], patches[1], patches[2], patches[3]:
                first = run_update(url, folder, dt.date(2026, 10, 8), save_raw=False)
                second = run_update(url, folder, dt.date(2026, 10, 8), save_raw=False)
            self.assertEqual(first['counts'], {'TWSE': 120, 'TPEX': 120})
            self.assertEqual(second['status'], 'success')
            engine = database.connect(url)
            with engine.connect() as connection:
                prices = connection.scalar(select(func.count()).select_from(database.daily_prices))
                runs = connection.scalar(select(func.count()).select_from(database.ingestion_runs))
            engine.dispose()
            self.assertEqual(prices, 240)
            self.assertEqual(runs, 2)


if __name__ == '__main__':
    unittest.main()
