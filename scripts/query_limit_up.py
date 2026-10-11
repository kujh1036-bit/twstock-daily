import argparse
import json
import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import connect
from app.queries import find_limit_up_stocks


def json_default(value):
    return str(value)


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')

    parser = argparse.ArgumentParser(description='Query stocks that closed limit-up on a date.')
    parser.add_argument('--date', required=True, help='Trading date in YYYY-MM-DD format')
    parser.add_argument(
        '--database-url',
        default=f"sqlite:///{(ROOT / 'data' / 'twstock.sqlite3').as_posix()}",
        help='SQLAlchemy database URL',
    )
    args = parser.parse_args()

    engine = connect(args.database_url)
    try:
        with engine.connect() as connection:
            rows = find_limit_up_stocks(connection, args.date)
    finally:
        engine.dispose()

    print(json.dumps({
        'question': f'{args.date} 漲停板有哪些公司？',
        'count': len(rows),
        'results': rows,
    }, ensure_ascii=False, indent=2, default=json_default))


if __name__ == '__main__':
    main()
