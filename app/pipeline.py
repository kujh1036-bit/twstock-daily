import datetime as dt
import gzip
import json
import pathlib
import uuid

from sqlalchemy.engine import make_url

from app import database
from app.normalize import (normalize_instruments, normalize_tpex, normalize_twse,
                           validate_prices)
from app.sources import tpex, twse


def write_raw(root, market, trade_date, payload):
    path = pathlib.Path(root) / 'data' / 'raw' / market.lower() / f'{trade_date}.json.gz'
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    with gzip.open(tmp, 'wt', encoding='utf-8') as handle:
        json.dump(payload, handle, ensure_ascii=False, separators=(',', ':'))
    tmp.replace(path)
    return path


def write_report(root, report):
    path = pathlib.Path(root) / 'data' / 'database_last_run.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(path)


def run_update(database_url, root, expected_date=None, allow_latest=False, save_raw=True):
    run_id = str(uuid.uuid4())
    started_at = dt.datetime.now(dt.timezone.utc)
    engine = database.connect(database_url)
    try:
        raw_instruments = {'TWSE': twse.fetch_instruments(), 'TPEX': tpex.fetch_instruments()}
        raw_prices = {'TWSE': twse.fetch_daily(), 'TPEX': tpex.fetch_daily()}
        normalized_instruments = {
            market: normalize_instruments(rows, market)
            for market, rows in raw_instruments.items()
        }
        allowed = {
            market: {row['stock_id'] for row in rows}
            for market, rows in normalized_instruments.items()
        }
        normalized_prices = {
            'TWSE': normalize_twse(raw_prices['TWSE'], allowed['TWSE']),
            'TPEX': normalize_tpex(raw_prices['TPEX'], allowed['TPEX']),
        }
        dates = {
            market: validate_prices(rows, market)
            for market, rows in normalized_prices.items()
        }
        if len(set(dates.values())) != 1:
            raise ValueError(f'market dates do not match: {dates}')
        trade_date = dates['TWSE']
        if expected_date and trade_date != expected_date and not allow_latest:
            report = {
                'run_id': run_id, 'status': 'skipped', 'trade_date': trade_date.isoformat(),
                'expected_date': expected_date.isoformat(),
                'reason': 'official APIs still report a different trading day',
            }
            with engine.begin() as connection:
                database.record_run(connection, run_id, trade_date, 'skipped', 0, started_at, report['reason'])
            write_report(root, report)
            return report

        if save_raw:
            for market in ('TWSE', 'TPEX'):
                write_raw(root, market, trade_date, raw_prices[market])

        now = dt.datetime.now(dt.timezone.utc)
        with engine.begin() as connection:
            for market in ('TWSE', 'TPEX'):
                database.sync_instruments(connection, normalized_instruments[market], market, now)
                database.replace_daily_prices(connection, normalized_prices[market], market, trade_date, now)
            total = sum(len(rows) for rows in normalized_prices.values())
            database.record_run(connection, run_id, trade_date, 'success', total, started_at)
        report = {
            'run_id': run_id, 'status': 'success', 'trade_date': trade_date.isoformat(),
            'counts': {market: len(rows) for market, rows in normalized_prices.items()},
            'database': make_url(database_url).render_as_string(hide_password=True),
        }
        write_report(root, report)
        return report
    except Exception as exc:
        report = {'run_id': run_id, 'status': 'failed', 'error': str(exc)}
        try:
            with engine.begin() as connection:
                database.record_run(connection, run_id, None, 'failed', 0, started_at, str(exc))
        finally:
            write_report(root, report)
        raise
    finally:
        engine.dispose()
