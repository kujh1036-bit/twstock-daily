#!/usr/bin/env python3
"""Resumable TWSE/TPEx historical daily OHLCV backfill.

Historical snapshots are gzip-compressed to keep the repository reasonably
small. Existing .csv and .csv.gz files are both recognized.
"""
import argparse
import datetime as dt
import json
import pathlib
import sys
import time
from zoneinfo import ZoneInfo

from download import download_market, write_csv

ROOT = pathlib.Path(__file__).resolve().parent
MARKETS = ('TWSE', 'TPEX')
NO_SESSION_FILE = ROOT / 'data' / 'no_session_dates.json'


def iter_weekdays(start, end):
    day = start
    while day <= end:
        if day.weekday() < 5:
            yield day
        day += dt.timedelta(days=1)


def existing_path(day, market):
    folder = ROOT / 'data' / market.lower()
    for suffix in ('.csv.gz', '.csv'):
        path = folder / f'{day.isoformat()}{suffix}'
        if path.exists() and path.stat().st_size > 100:
            return path
    return None


def save_state(state):
    path = ROOT / 'data' / 'backfill_state.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(path)


def load_no_session_dates():
    if not NO_SESSION_FILE.exists():
        return set()
    try:
        return set(json.loads(NO_SESSION_FILE.read_text(encoding='utf-8')))
    except (OSError, ValueError, TypeError):
        return set()


def save_no_session_dates(dates):
    NO_SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = NO_SESSION_FILE.with_suffix('.tmp')
    tmp.write_text(json.dumps(sorted(dates), ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(NO_SESSION_FILE)


def looks_like_no_session(errors):
    hints = ('unavailable', 'tables missing', 'missing/empty', 'no valid stock table')
    return bool(errors) and all(any(hint in message.lower() for hint in hints) for message in errors.values())


def parse_args():
    today = dt.datetime.now(ZoneInfo('Asia/Taipei')).date()
    parser = argparse.ArgumentParser(description='Backfill historical TWSE/TPEx daily data')
    parser.add_argument('--start', default='2021-01-01', help='YYYY-MM-DD')
    parser.add_argument('--end', default=today.isoformat(), help='YYYY-MM-DD')
    parser.add_argument('--max-days', type=int, default=20,
                        help='maximum missing weekdays attempted in this run; 0 means unlimited')
    parser.add_argument('--delay', type=float, default=1.0, help='seconds between official API calls')
    parser.add_argument('--overwrite', action='store_true')
    return parser.parse_args()


def main():
    args = parse_args()
    start, end = dt.date.fromisoformat(args.start), dt.date.fromisoformat(args.end)
    today = dt.datetime.now(ZoneInfo('Asia/Taipei')).date()
    if start > end:
        raise SystemExit('--start must not be after --end')
    if end > today:
        raise SystemExit('--end cannot be in the future')
    if args.max_days < 0 or args.delay < 0:
        raise SystemExit('--max-days and --delay must be non-negative')

    known_no_sessions = load_no_session_dates()
    state = {
        'range': {'start': start.isoformat(), 'end': end.isoformat()},
        'updated_at': dt.datetime.now(ZoneInfo('Asia/Taipei')).isoformat(),
        'attempted_dates': 0,
        'downloaded': {},
        'skipped_existing': {},
        'no_session_dates': [],
        'errors': {},
    }

    truncated = False
    for day in iter_weekdays(start, end):
        if day.isoformat() in known_no_sessions and not args.overwrite:
            state['no_session_dates'].append(day.isoformat())
            continue
        missing = [m for m in MARKETS if args.overwrite or not existing_path(day, m)]
        if not missing:
            state['skipped_existing'][day.isoformat()] = list(MARKETS)
            continue
        if args.max_days and state['attempted_dates'] >= args.max_days:
            truncated = True
            break

        state['attempted_dates'] += 1
        day_counts, day_errors = {}, {}
        for market in missing:
            try:
                rows = download_market(day, market)
                out = ROOT / 'data' / market.lower() / f'{day.isoformat()}.csv.gz'
                write_csv(out, rows)
                day_counts[market] = len(rows)
                print(f'{day} {market}: saved {len(rows)} rows')
            except Exception as exc:
                day_errors[market] = str(exc)
                print(f'ERROR {day} {market}: {exc}', file=sys.stderr)
            if args.delay:
                time.sleep(args.delay)

        if day_counts:
            state['downloaded'][day.isoformat()] = day_counts
        if (not day_counts and set(day_errors) == set(missing) and len(missing) == 2
                and looks_like_no_session(day_errors)):
            state['no_session_dates'].append(day.isoformat())
            known_no_sessions.add(day.isoformat())
            save_no_session_dates(known_no_sessions)
        elif day_errors:
            state['errors'][day.isoformat()] = day_errors
        save_state(state)

    state['updated_at'] = dt.datetime.now(ZoneInfo('Asia/Taipei')).isoformat()
    state['truncated'] = truncated
    state['complete'] = not state['errors'] and not truncated
    save_state(state)
    print(json.dumps(state, ensure_ascii=False))
    return 1 if state['errors'] else 0


if __name__ == '__main__':
    sys.exit(main())
