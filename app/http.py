import json
import time

import requests

try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:  # GitHub runners normally work with certifi alone.
    pass


SESSION = requests.Session()
SESSION.headers.update({
    'User-Agent': 'TWStockDailyResearch/2.0',
    'Accept': 'application/json',
})


def get_json(url, attempts=3, timeout=45):
    """Fetch official JSON while tolerating inconsistent charset headers."""
    for attempt in range(attempts):
        try:
            response = SESSION.get(url, timeout=timeout)
            response.raise_for_status()
            for encoding in ('utf-8-sig', 'cp950', 'big5'):
                try:
                    return json.loads(response.content.decode(encoding))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    continue
            raise ValueError('response is not valid UTF-8/CP950 JSON')
        except (requests.RequestException, ValueError):
            if attempt + 1 == attempts:
                raise
            time.sleep(3 * (attempt + 1))
