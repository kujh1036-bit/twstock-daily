from app.http import get_json


DAILY_URL = 'https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL'
INSTRUMENTS_URL = 'https://openapi.twse.com.tw/v1/opendata/t187ap03_L'


def fetch_daily():
    data = get_json(DAILY_URL)
    if not isinstance(data, list):
        raise ValueError('TWSE daily response is not a list')
    return data


def fetch_instruments():
    data = get_json(INSTRUMENTS_URL)
    if not isinstance(data, list):
        raise ValueError('TWSE instrument response is not a list')
    return data
