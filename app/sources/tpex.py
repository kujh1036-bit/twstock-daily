from app.http import get_json


DAILY_URL = 'https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes'
INSTRUMENTS_URL = 'https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O'


def fetch_daily():
    data = get_json(DAILY_URL)
    if not isinstance(data, list):
        raise ValueError('TPEx daily response is not a list')
    return data


def fetch_instruments():
    data = get_json(INSTRUMENTS_URL)
    if not isinstance(data, list):
        raise ValueError('TPEx instrument response is not a list')
    return data
