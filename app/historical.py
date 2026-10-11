import datetime as dt

from sqlalchemy import func, select

from app import database
from app.normalize import integer, number, validate_prices


def normalize_historical_rows(rows, market, allowed_codes, minimum_rows=100):
    normalized = []
    for row in rows:
        code = str(row.get('stock_id') or '').strip()
        if code not in allowed_codes:
            continue
        close = number(row.get('close'))
        if close is None:
            continue
        normalized.append({
            'trade_date': dt.date.fromisoformat(row['date']),
            'market': market,
            'stock_id': code,
            'name': str(row.get('name') or '').strip(),
            'open': number(row.get('open')),
            'high': number(row.get('high')),
            'low': number(row.get('low')),
            'close': close,
            'change': number(row.get('change')),
            'volume': integer(row.get('volume')),
            'turnover': integer(row.get('turnover')),
            'transactions': integer(row.get('transactions')),
            'source': 'TWSE_MI_INDEX' if market == 'TWSE' else 'TPEX_DAILY_QUOTES',
        })
    validate_prices(normalized, market, minimum_rows=minimum_rows)
    return normalized


def stored_markets(connection, trade_date, minimum_rows=100):
    statement = (
        select(database.daily_prices.c.market)
        .where(database.daily_prices.c.trade_date == trade_date)
        .group_by(database.daily_prices.c.market)
        .having(func.count(database.daily_prices.c.stock_id) >= minimum_rows)
    )
    return set(connection.scalars(statement))
