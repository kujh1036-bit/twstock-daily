import datetime as dt
from decimal import Decimal, ROUND_FLOOR

from sqlalchemy import and_, select

from app.database import daily_prices


def price_tick(price):
    """Return the Taiwan exchange tick size for an order price."""
    price = Decimal(price)
    if price < Decimal('10'):
        return Decimal('0.01')
    if price < Decimal('50'):
        return Decimal('0.05')
    if price < Decimal('100'):
        return Decimal('0.1')
    if price < Decimal('500'):
        return Decimal('0.5')
    if price < Decimal('1000'):
        return Decimal('1')
    return Decimal('5')


def limit_up_price(reference_price):
    """Calculate a regular 10% Taiwan stock limit-up price."""
    raw_price = Decimal(reference_price) * Decimal('1.10')
    tick = price_tick(raw_price)
    return (raw_price / tick).to_integral_value(rounding=ROUND_FLOOR) * tick


def find_limit_up_stocks(connection, trade_date):
    """Find company stocks that closed at their calculated daily upper limit."""
    if isinstance(trade_date, str):
        trade_date = dt.date.fromisoformat(trade_date)

    statement = (
        select(daily_prices)
        .where(and_(
            daily_prices.c.trade_date == trade_date,
            daily_prices.c.change > 0,
            daily_prices.c.close == daily_prices.c.high,
        ))
        .order_by(daily_prices.c.market, daily_prices.c.stock_id)
    )

    results = []
    for row in connection.execute(statement).mappings():
        close = Decimal(row['close'])
        reference_price = close - Decimal(row['change'])
        calculated_limit = limit_up_price(reference_price)
        if close == calculated_limit:
            results.append({
                'trade_date': row['trade_date'],
                'market': row['market'],
                'stock_id': row['stock_id'],
                'name': row['name'],
                'close': close,
                'volume': row['volume'],
                'high': Decimal(row['high']),
                'low': Decimal(row['low']),
                'turnover': row['turnover'],
                'reference_price': reference_price,
                'limit_up_price': calculated_limit,
                'source': row['source'],
            })
    return results
