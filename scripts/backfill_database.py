import argparse
import datetime as dt
import json
import pathlib
import sys
import time
import uuid
from zoneinfo import ZoneInfo


ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import database
from app.historical import normalize_historical_rows, stored_markets
from app.normalize import normalize_instruments
from app.sources import tpex, twse
from backfill import (iter_weekdays, load_no_session_dates,
                      looks_like_no_session, save_no_session_dates)
from download import download_market, write_csv


MARKETS = ('TWSE', 'TPEX')


def parse_args():
    today = dt.datetime.now(ZoneInfo('Asia/Taipei')).date()
    default_end = today - dt.timedelta(days=1)
    default_start = default_end - dt.timedelta(days=365 * 5)
    parser = argparse.ArgumentParser(description='Backfill all-market history into daily_prices')
    parser.add_argument('--start', default=default_start.isoformat(), help='YYYY-MM-DD')
    parser.add_argument('--end', default=default_end.isoformat(), help='YYYY-MM-DD')
    parser.add_argument('--database-url', default=f"sqlite:///{(ROOT / 'data' / 'twstock.sqlite3').as_posix()}")
    parser.add_argument('--max-days', type=int, default=20, help='missing weekdays to attempt; 0 is unlimited')
    parser.add_argument('--delay', type=float, default=0.5, help='seconds between official requests')
    parser.add_argument('--overwrite', action='store_true')
    parser.add_argument('--save-snapshots', action='store_true', help='also save gzip CSV source snapshots')
    return parser.parse_args()


def save_report(report):
    path = ROOT / 'data' / 'database_backfill_state.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(path)


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    args = parse_args()
    start, end = dt.date.fromisoformat(args.start), dt.date.fromisoformat(args.end)
    today = dt.datetime.now(ZoneInfo('Asia/Taipei')).date()
    if start > end:
        raise SystemExit('--start must not be after --end')
    if end >= today:
        raise SystemExit('--end must be earlier than today')
    if args.max_days < 0 or args.delay < 0:
        raise SystemExit('--max-days and --delay must be non-negative')

    run_id = str(uuid.uuid4())
    started_at = dt.datetime.now(dt.timezone.utc)
    engine = database.connect(args.database_url)
    known_no_sessions = load_no_session_dates()
    report = {
        'run_id': run_id,
        'range': {'start': start.isoformat(), 'end': end.isoformat()},
        'attempted_dates': 0,
        'stored': {},
        'skipped_existing': [],
        'no_session_dates': [],
        'errors': {},
        'complete': False,
    }
    try:
        raw_instruments = {'TWSE': twse.fetch_instruments(), 'TPEX': tpex.fetch_instruments()}
        instruments = {
            market: normalize_instruments(rows, market)
            for market, rows in raw_instruments.items()
        }
        allowed = {
            market: {row['stock_id'] for row in rows}
            for market, rows in instruments.items()
        }
        now = dt.datetime.now(dt.timezone.utc)
        with engine.begin() as connection:
            for market in MARKETS:
                database.sync_instruments(connection, instruments[market], market, now)

        truncated = False
        for day in iter_weekdays(start, end):
            if day.isoformat() in known_no_sessions and not args.overwrite:
                report['no_session_dates'].append(day.isoformat())
                continue
            with engine.connect() as connection:
                existing = stored_markets(connection, day)
            missing = list(MARKETS) if args.overwrite else [m for m in MARKETS if m not in existing]
            if not missing:
                report['skipped_existing'].append(day.isoformat())
                continue
            if args.max_days and report['attempted_dates'] >= args.max_days:
                truncated = True
                break

            report['attempted_dates'] += 1
            downloaded, errors = {}, {}
            for market in missing:
                try:
                    raw_rows = download_market(day, market)
                    rows = normalize_historical_rows(raw_rows, market, allowed[market])
                    if args.save_snapshots:
                        path = ROOT / 'data' / market.lower() / f'{day.isoformat()}.csv.gz'
                        write_csv(path, raw_rows)
                    downloaded[market] = rows
                except Exception as exc:
                    errors[market] = str(exc)
                if args.delay:
                    time.sleep(args.delay)

            if not downloaded and set(errors) == set(missing) and len(missing) == 2 and looks_like_no_session(errors):
                known_no_sessions.add(day.isoformat())
                save_no_session_dates(known_no_sessions)
                report['no_session_dates'].append(day.isoformat())
                print(f'{day}: no trading session')
            else:
                fetched_at = dt.datetime.now(dt.timezone.utc)
                with engine.begin() as connection:
                    for market, rows in downloaded.items():
                        database.replace_daily_prices(connection, rows, market, day, fetched_at)
                if downloaded:
                    report['stored'][day.isoformat()] = {m: len(rows) for m, rows in downloaded.items()}
                    print(f"{day}: " + ', '.join(f'{m} {len(rows)}' for m, rows in downloaded.items()))
                if errors:
                    report['errors'][day.isoformat()] = errors
                    print(f'{day}: errors {errors}', file=sys.stderr)
            save_report(report)

        report['truncated'] = truncated
        report['complete'] = not report['errors'] and not truncated
        status = 'success' if report['complete'] else ('partial' if report['stored'] else 'failed')
        total = sum(sum(counts.values()) for counts in report['stored'].values())
        with engine.begin() as connection:
            database.record_run(connection, run_id, end, status, total, started_at, json.dumps({
                'range': report['range'], 'attempted_dates': report['attempted_dates'],
                'truncated': truncated, 'error_dates': len(report['errors']),
            }))
        save_report(report)
        print(json.dumps(report, ensure_ascii=False))
        return 1 if report['errors'] else 0
    finally:
        engine.dispose()


if __name__ == '__main__':
    sys.exit(main())
