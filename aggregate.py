#!/usr/bin/env python3
"""Aggregate downloaded daily snapshots into weekly and monthly OHLCV files."""
import argparse
import csv
import datetime as dt
import gzip
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent
OUT_FIELDS = ['date', 'market', 'stock_id', 'name', 'open', 'high', 'low', 'close', 'volume', 'sessions']


def open_text(path):
    if path.suffix == '.gz':
        return gzip.open(path, 'rt', encoding='utf-8-sig', newline='')
    return path.open('r', encoding='utf-8-sig', newline='')


def daily_files(year):
    found = {}
    for market in ('twse', 'tpex'):
        folder = ROOT / 'data' / market
        if not folder.exists():
            continue
        for path in folder.glob(f'{year}-??-??.csv*'):
            if not (path.name.endswith('.csv') or path.name.endswith('.csv.gz')):
                continue
            key = (market, path.name[:10])
            if key not in found or path.suffix == '.gz':
                found[key] = path
    return sorted(found.values(), key=lambda p: (p.name[:10], str(p)))


def period_key(day, frequency):
    if frequency == 'monthly':
        return f'{day.year:04d}-{day.month:02d}'
    iso_year, iso_week, _ = day.isocalendar()
    return f'{iso_year:04d}-W{iso_week:02d}'


def as_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def aggregate_year(year, frequency):
    groups = {}
    for path in daily_files(year):
        with open_text(path) as handle:
            for row in csv.DictReader(handle):
                day = dt.date.fromisoformat(row['date'])
                key = (period_key(day, frequency), row['market'], row['stock_id'])
                prices = {name: as_float(row.get(name)) for name in ('open', 'high', 'low', 'close')}
                if prices['close'] is None:
                    continue
                current = groups.get(key)
                if current is None:
                    groups[key] = {
                        'date': row['date'], 'market': row['market'], 'stock_id': row['stock_id'],
                        'name': row['name'], 'open': prices['open'], 'high': prices['high'],
                        'low': prices['low'], 'close': prices['close'],
                        'volume': int(float(row.get('volume') or 0)), 'sessions': 1,
                    }
                else:
                    current['date'] = row['date']
                    current['name'] = row['name']
                    if current['open'] is None and prices['open'] is not None:
                        current['open'] = prices['open']
                    if prices['high'] is not None:
                        current['high'] = prices['high'] if current['high'] is None else max(current['high'], prices['high'])
                    if prices['low'] is not None:
                        current['low'] = prices['low'] if current['low'] is None else min(current['low'], prices['low'])
                    current['close'] = prices['close']
                    current['volume'] += int(float(row.get('volume') or 0))
                    current['sessions'] += 1
    return [groups[key] for key in sorted(groups)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--start-year', type=int, default=2021)
    parser.add_argument('--end-year', type=int, default=dt.date.today().year)
    args = parser.parse_args()
    if args.start_year > args.end_year:
        parser.error('--start-year must not be after --end-year')
    for year in range(args.start_year, args.end_year + 1):
        for frequency in ('weekly', 'monthly'):
            rows = aggregate_year(year, frequency)
            if not rows:
                continue
            path = ROOT / 'data' / frequency / f'{year}.csv.gz'
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_name(path.name + '.tmp')
            with gzip.open(tmp, 'wt', encoding='utf-8-sig', newline='') as handle:
                writer = csv.DictWriter(handle, fieldnames=OUT_FIELDS)
                writer.writeheader()
                writer.writerows(rows)
            tmp.replace(path)
            print(f'{frequency} {year}: saved {len(rows)} rows')


if __name__ == '__main__':
    main()
