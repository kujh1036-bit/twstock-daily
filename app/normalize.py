import datetime as dt
import decimal
import re


EMPTY_VALUES = {'', '-', '--', '---', 'N/A', 'null', 'None', '除權息'}


def clean(value):
    return re.sub(r'<[^>]*>', '', str(value if value is not None else '')).strip()


def parse_date(value):
    text = clean(value)
    if not text:
        return None
    digits = re.sub(r'\D', '', text)
    if len(digits) == 7:
        year, month, day = int(digits[:3]) + 1911, int(digits[3:5]), int(digits[5:])
    elif len(digits) == 8:
        year, month, day = int(digits[:4]), int(digits[4:6]), int(digits[6:])
    else:
        parts = [int(part) for part in re.findall(r'\d+', text)]
        if len(parts) != 3:
            raise ValueError(f'unsupported date: {value!r}')
        year, month, day = parts
        if year < 1911:
            year += 1911
    return dt.date(year, month, day)


def number(value):
    text = clean(value).replace(',', '').replace('＋', '+').replace('−', '-').replace('－', '-')
    if text in EMPTY_VALUES:
        return None
    try:
        return decimal.Decimal(text)
    except decimal.InvalidOperation as exc:
        raise ValueError(f'invalid number: {value!r}') from exc


def integer(value):
    parsed = number(value)
    return int(parsed) if parsed is not None else None


def normalize_instruments(rows, market):
    result = []
    for row in rows:
        if market == 'TWSE':
            code = clean(row.get('公司代號'))
            name = clean(row.get('公司簡稱') or row.get('公司名稱'))
            industry = clean(row.get('產業別'))
            listed = row.get('上市日期')
        else:
            # TPEx OpenAPI uses English property names for this dataset.
            code = clean(row.get('SecuritiesCompanyCode') or row.get('公司代號'))
            name = clean(row.get('CompanyAbbreviation') or row.get('CompanyName') or row.get('公司簡稱'))
            industry = clean(row.get('SecuritiesIndustryCode') or row.get('產業別'))
            listed = row.get('DateOfListing') or row.get('上櫃日期')
        if not code:
            continue
        result.append({
            'market': market,
            'stock_id': code,
            'name': name,
            'industry': industry or None,
            'listed_date': parse_date(listed) if clean(listed) else None,
            'active': True,
        })
    return result


def normalize_twse(rows, allowed_codes):
    result = []
    for row in rows:
        code = clean(row.get('Code'))
        if code not in allowed_codes:
            continue
        close = number(row.get('ClosingPrice'))
        if close is None:
            continue
        result.append({
            'trade_date': parse_date(row.get('Date')),
            'market': 'TWSE', 'stock_id': code,
            'name': clean(row.get('Name')), 'open': number(row.get('OpeningPrice')),
            'high': number(row.get('HighestPrice')), 'low': number(row.get('LowestPrice')),
            'close': close, 'change': number(row.get('Change')),
            'volume': integer(row.get('TradeVolume')), 'turnover': integer(row.get('TradeValue')),
            'transactions': integer(row.get('Transaction')), 'source': 'TWSE_STOCK_DAY_ALL',
        })
    return result


def normalize_tpex(rows, allowed_codes):
    result = []
    for row in rows:
        code = clean(row.get('SecuritiesCompanyCode'))
        if code not in allowed_codes:
            continue
        close = number(row.get('Close'))
        if close is None:
            continue
        result.append({
            'trade_date': parse_date(row.get('Date')),
            'market': 'TPEX', 'stock_id': code,
            'name': clean(row.get('CompanyName')), 'open': number(row.get('Open')),
            'high': number(row.get('High')), 'low': number(row.get('Low')),
            'close': close, 'change': number(row.get('Change')),
            'volume': integer(row.get('TradingShares')), 'turnover': integer(row.get('TransactionAmount')),
            'transactions': integer(row.get('TransactionNumber')), 'source': 'TPEX_DAILY_CLOSE_QUOTES',
        })
    return result


def validate_prices(rows, market, minimum_rows=100):
    if len(rows) < minimum_rows:
        raise ValueError(f'{market} suspiciously few ordinary stocks: {len(rows)}')
    dates = {row['trade_date'] for row in rows}
    if None in dates or len(dates) != 1:
        raise ValueError(f'{market} contains inconsistent dates: {sorted(str(x) for x in dates)}')
    for row in rows:
        if row['high'] is not None and row['low'] is not None and row['high'] < row['low']:
            raise ValueError(f"{market} invalid high/low for {row['stock_id']}")
        if row['volume'] is not None and row['volume'] < 0:
            raise ValueError(f"{market} negative volume for {row['stock_id']}")
    return next(iter(dates))
