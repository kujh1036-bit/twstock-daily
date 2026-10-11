#!/usr/bin/env python3
"""TWSE + TPEx daily OHLCV downloader. No fabricated rows on failures."""
import argparse
import csv
import datetime as dt
import json
import os
import pathlib
import re
import sys
import time
from zoneinfo import ZoneInfo

import requests

ROOT = pathlib.Path(__file__).resolve().parent
FIELDS = ['date','market','stock_id','name','open','high','low','close','volume','change','change_pct','change_status']
SESSION = requests.Session()
SESSION.headers.update({'User-Agent':'Mozilla/5.0 (compatible; TWStockDailyResearch/1.0)', 'Accept':'application/json,text/plain,*/*'})

def clean(v):
    return re.sub(r'<[^>]*>', '', str(v if v is not None else '')).replace(',','').replace('＋','+').strip()

def num(v):
    s = clean(v).replace('−','-').replace('—','').replace('--','').replace('---','')
    if not s or s in ('-','X','除權息'): return ''
    try: return str(float(s)) if '.' in s else str(int(s))
    except ValueError: return ''

def change_info(close, raw, sign=''):
    """Compute day-over-day percentage from official price change, not open price."""
    raw_text = clean(raw).replace('−', '-').replace('－', '-').replace('—', '')
    sign_text = clean(sign)
    if not raw_text or raw_text in ('--', '---', '-', '除權息', 'X'):
        return '', '', 'missing'
    # TWSE may separate direction as an HTML icon in a preceding column.
    direction = -1 if ('-' in sign_text or '跌' in sign_text or 'green' in sign_text.lower()) else 1
    if '+' in sign_text or '漲' in sign_text or 'red' in sign_text.lower():
        direction = 1
    raw_num = num(raw_text.lstrip('△▲▽▼'))
    if raw_num == '':
        return '', '', 'missing'
    delta = float(raw_num)
    if raw_text.startswith(('+', '-')):
        direction = -1 if raw_text.startswith('-') else 1
    elif raw_text.startswith(('△', '▲')):
        direction = 1
    elif raw_text.startswith(('▽', '▼')):
        direction = -1
    elif raw_text.strip() in ('0', '0.0', '0.00'):
        direction = 0
    delta = abs(delta) * direction
    previous = float(close) - delta
    if previous <= 0:
        return '', '', 'invalid_previous_close'
    return f'{delta:g}', f'{delta / previous * 100:.4f}', 'ok'

def get_json(url, params):
    for attempt in range(3):
        try:
            r=SESSION.get(url,params=params,timeout=40)
            r.raise_for_status()
            return r.json()
        except (requests.RequestException,ValueError):
            if attempt==2: raise
            time.sleep(3*(attempt+1))

def twse(day):
    data=get_json('https://www.twse.com.tw/exchangeReport/MI_INDEX', {'response':'json','date':day.strftime('%Y%m%d'),'type':'ALLBUT0999'})
    print("TWSE DEBUG:", "keys=", list(data.keys()), "stat=", data.get("stat"), "tables=", [(t.get("title"), len(t.get("data", []))) for t in data.get("tables", [])])
    if data.get('stat')!='OK':
        raise RuntimeError('TWSE unavailable: '+str(data.get('stat')))
    fields=data.get('fields9') or []
    rows=data.get('data9') or data.get('data') or []
    if not rows:
        for table in data.get('tables', []):
            title = table.get('title') or ''
            if '每日收盤行情' in title and '全部' in title:
                fields = table.get('fields') or []
                rows = table.get('data') or []
                break
    if not rows: raise RuntimeError('TWSE data9 missing/empty; schema or publication delay')
    # Official MI_INDEX data9 typically: code, name, volume, transactions, value, open, high, low, close, change, last bid, last ask, PE.
    keys=['證券代號','證券名稱','成交股數','成交筆數','成交金額','開盤價','最高價','最低價','收盤價']
    if not all(k in fields for k in keys): raise RuntimeError('TWSE unexpected fields9: '+repr(fields))
    idx={k:fields.index(k) for k in keys}
    change_col = next((fields.index(k) for k in ('漲跌價差','漲跌') if k in fields), None)
    sign_col = next((fields.index(k) for k in ('漲跌(+/-)','漲跌(+/-) ', '漲跌符號') if k in fields), None)
    if change_col is None:
        print('WARNING TWSE: official change column not found; percentages left blank')
    result=[]
    for row in rows:
        code=clean(row[idx['證券代號']])
        if not re.fullmatch(r'\d{4,6}',code): continue
        close=num(row[idx['收盤價']])
        if not close: continue
        change, change_pct, status = change_info(close, row[change_col], row[sign_col] if sign_col is not None else '') if change_col is not None else ('', '', 'missing_column')
        result.append(dict(date=day.isoformat(),market='TWSE',stock_id=code,name=clean(row[idx['證券名稱']]),open=num(row[idx['開盤價']]),high=num(row[idx['最高價']]),low=num(row[idx['最低價']]),close=close,volume=num(row[idx['成交股數']]),change=change,change_pct=change_pct,change_status=status))
    if len(result)<100: raise RuntimeError(f'TWSE suspiciously few stocks: {len(result)}')
    return result

def tpex(day):
    roc=f'{day.year-1911}/{day.month:02d}/{day.day:02d}'
    data=get_json('https://www.tpex.org.tw/www/zh-tw/afterTrading/dailyQuotes', {'date':roc,'id':'','response':'json'})
    tables=data.get('tables') or []
    if not tables: raise RuntimeError('TPEx tables missing; no session or schema changed: '+str(data.get('stat','')))
    result=[]
    for table in tables:
        fields=table.get('fields') or []
        rows=table.get('data') or []
        if not fields or not rows: continue
        def col(*names):
            for name in names:
                for i,f in enumerate(fields):
                    if clean(f).replace(' ','')==name: return i
            return None
        i_code=col('代號','股票代號','證券代號')
        i_name=col('名稱','股票名稱','證券名稱')
        i_close=col('收盤','收盤價')
        i_open=col('開盤','開盤價')
        i_high=col('最高','最高價')
        i_low=col('最低','最低價')
        i_vol=col('成交股數','成交量')
        i_change=col('漲跌','漲跌價差','漲跌金額','漲跌元')
        i_sign=col('漲跌(+/-)','漲跌符號')
        if any(x is None for x in (i_code,i_name,i_close,i_open,i_high,i_low,i_vol)): continue
        for row in rows:
            code=clean(row[i_code])
            if not re.fullmatch(r'\d{4,6}',code): continue
            close=num(row[i_close])
            if not close: continue
            change, change_pct, status = change_info(close, row[i_change], row[i_sign] if i_sign is not None else '') if i_change is not None else ('', '', 'missing_column')
            result.append(dict(date=day.isoformat(),market='TPEX',stock_id=code,name=clean(row[i_name]),open=num(row[i_open]),high=num(row[i_high]),low=num(row[i_low]),close=close,volume=num(row[i_vol]),change=change,change_pct=change_pct,change_status=status))
    if len(result)<100: raise RuntimeError(f'TPEx no valid stock table / suspiciously few stocks: {len(result)}')
    return result

def write_csv(path,rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix('.tmp')
    with tmp.open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=FIELDS)
        writer.writeheader();writer.writerows(rows)
    tmp.replace(path)

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--date',help='YYYY-MM-DD; default Taiwan today')
    args=p.parse_args()
    day=dt.date.fromisoformat(args.date) if args.date else dt.datetime.now(ZoneInfo('Asia/Taipei')).date()
    if day>dt.datetime.now(ZoneInfo('Asia/Taipei')).date(): p.error('future date')
    if day.weekday()>=5:
        day -= dt.timedelta(days=day.weekday()-4)
    results={};errors={}
    for name,func in [('TWSE',twse),('TPEX',tpex)]:
        try:
            rows=func(day)
            write_csv(ROOT/'data'/name.lower()/f'{day}.csv',rows)
            results[name]=len(rows)
            print(f'{name}: saved {len(rows)} rows')
        except Exception as e:
            errors[name]=str(e)
            print(f'ERROR {name}: {e}',file=sys.stderr)
    report={'date':day.isoformat(),'counts':results,'errors':errors,'complete':not errors and len(results)==2}
    (ROOT/'data').mkdir(exist_ok=True)
    (ROOT/'data'/'last_run.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))
    return 1 if errors else 0

if __name__=='__main__':sys.exit(main())
