import datetime as dt

from sqlalchemy import (BigInteger, Boolean, Column, Date, DateTime, Integer,
                        MetaData, Numeric, String, Table, Text, and_, create_engine,
                        delete, insert, update)


metadata = MetaData()

instruments = Table(
    'instruments', metadata,
    Column('market', String(8), primary_key=True),
    Column('stock_id', String(16), primary_key=True),
    Column('name', String(128), nullable=False),
    Column('industry', String(128)),
    Column('listed_date', Date),
    Column('active', Boolean, nullable=False, default=True),
    Column('updated_at', DateTime(timezone=True), nullable=False),
)

daily_prices = Table(
    'daily_prices', metadata,
    Column('trade_date', Date, primary_key=True),
    Column('market', String(8), primary_key=True),
    Column('stock_id', String(16), primary_key=True),
    Column('name', String(128), nullable=False),
    Column('open', Numeric(18, 4)), Column('high', Numeric(18, 4)),
    Column('low', Numeric(18, 4)), Column('close', Numeric(18, 4), nullable=False),
    Column('change', Numeric(18, 4)),
    Column('volume', BigInteger), Column('turnover', BigInteger),
    Column('transactions', Integer), Column('source', String(64), nullable=False),
    Column('fetched_at', DateTime(timezone=True), nullable=False),
)

corporate_actions = Table(
    'corporate_actions', metadata,
    Column('market', String(8), primary_key=True),
    Column('stock_id', String(16), primary_key=True),
    Column('action_date', Date, primary_key=True),
    Column('action_type', String(64), primary_key=True),
    Column('details', Text),
)

trading_calendar = Table(
    'trading_calendar', metadata,
    Column('trade_date', Date, primary_key=True),
    Column('is_open', Boolean, nullable=False),
    Column('description', String(255)),
)

ingestion_runs = Table(
    'ingestion_runs', metadata,
    Column('run_id', String(36), primary_key=True),
    Column('trade_date', Date), Column('status', String(16), nullable=False),
    Column('row_count', Integer, nullable=False, default=0),
    Column('started_at', DateTime(timezone=True), nullable=False),
    Column('completed_at', DateTime(timezone=True), nullable=False),
    Column('details', Text),
)


def connect(database_url):
    engine = create_engine(database_url, pool_pre_ping=True)
    metadata.create_all(engine)
    return engine


def sync_instruments(connection, rows, market, now):
    connection.execute(update(instruments).where(instruments.c.market == market).values(active=False, updated_at=now))
    for row in rows:
        values = {**row, 'updated_at': now}
        condition = and_(instruments.c.market == market, instruments.c.stock_id == row['stock_id'])
        updated = connection.execute(update(instruments).where(condition).values(**values))
        if updated.rowcount == 0:
            connection.execute(insert(instruments).values(**values))


def replace_daily_prices(connection, rows, market, trade_date, fetched_at):
    connection.execute(delete(daily_prices).where(and_(
        daily_prices.c.market == market,
        daily_prices.c.trade_date == trade_date,
    )))
    connection.execute(insert(daily_prices), [{**row, 'fetched_at': fetched_at} for row in rows])


def record_run(connection, run_id, trade_date, status, row_count, started_at, details=''):
    connection.execute(insert(ingestion_runs).values(
        run_id=run_id, trade_date=trade_date, status=status, row_count=row_count,
        started_at=started_at, completed_at=dt.datetime.now(dt.timezone.utc), details=details,
    ))
