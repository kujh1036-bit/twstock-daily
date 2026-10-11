import csv
import datetime as dt
import gzip
import pathlib
import tempfile
import unittest
from unittest import mock
import json

import aggregate
import backfill
import download


class DataPipelineTests(unittest.TestCase):
    def test_json_charset_fallback_preserves_chinese(self):
        response = mock.Mock()
        response.content = json.dumps({'name': '台積電'}, ensure_ascii=False).encode('cp950')
        response.raise_for_status.return_value = None
        with mock.patch.object(download.SESSION, 'get', return_value=response):
            self.assertEqual(download.get_json('https://example.test', {})['name'], '台積電')

    def test_weekdays_exclude_weekend(self):
        days = list(backfill.iter_weekdays(dt.date(2026, 10, 9), dt.date(2026, 10, 12)))
        self.assertEqual(days, [dt.date(2026, 10, 9), dt.date(2026, 10, 12)])

    def test_write_compressed_csv(self):
        with tempfile.TemporaryDirectory() as folder:
            path = pathlib.Path(folder) / 'one.csv.gz'
            row = {name: '' for name in download.FIELDS}
            row.update(date='2026-10-08', market='TWSE', stock_id='2330', name='台積電', close='1000')
            download.write_csv(path, [row])
            with gzip.open(path, 'rt', encoding='utf-8-sig', newline='') as handle:
                loaded = list(csv.DictReader(handle))
            self.assertEqual(loaded[0]['stock_id'], '2330')

    def test_existing_path_accepts_plain_or_gzip(self):
        with tempfile.TemporaryDirectory() as folder, mock.patch.object(backfill, 'ROOT', pathlib.Path(folder)):
            target = pathlib.Path(folder) / 'data' / 'twse' / '2026-10-08.csv'
            target.parent.mkdir(parents=True)
            target.write_text('x' * 101, encoding='utf-8')
            self.assertEqual(backfill.existing_path(dt.date(2026, 10, 8), 'TWSE'), target)

    def test_period_keys(self):
        day = dt.date(2026, 10, 8)
        self.assertEqual(aggregate.period_key(day, 'monthly'), '2026-10')
        self.assertEqual(aggregate.period_key(day, 'weekly'), '2026-W41')


if __name__ == '__main__':
    unittest.main()
