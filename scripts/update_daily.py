#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import os
import pathlib
import sys
from zoneinfo import ZoneInfo

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.pipeline import run_update  # noqa: E402


def main():
    default_db = f"sqlite:///{(ROOT / 'data' / 'twstock.sqlite3').as_posix()}"
    parser = argparse.ArgumentParser(description='Update official TWSE/TPEx daily database')
    parser.add_argument('--database-url', default=os.environ.get('DATABASE_URL') or default_db)
    parser.add_argument('--expected-date', help='YYYY-MM-DD; defaults to Taiwan today')
    parser.add_argument('--allow-latest', action='store_true', help='accept latest official date even if not today')
    parser.add_argument('--no-raw', action='store_true')
    parser.add_argument('--require-external', action='store_true', help='reject SQLite; intended for GitHub Actions')
    args = parser.parse_args()
    if args.require_external and args.database_url.startswith('sqlite:'):
        parser.error('DATABASE_URL must point to a persistent external database')
    expected = (dt.date.fromisoformat(args.expected_date) if args.expected_date
                else dt.datetime.now(ZoneInfo('Asia/Taipei')).date())
    report = run_update(args.database_url, ROOT, expected, args.allow_latest, not args.no_raw)
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
