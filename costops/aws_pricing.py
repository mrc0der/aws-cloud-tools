"""aws pricing"""
import json
import logging
from datetime import datetime
import os
import concurrent.futures
import requests

logging.basicConfig(level = logging.INFO)
logger = logging.getLogger(__name__)

TODAY = datetime.now().strftime("%Y-%m-%d")
API = 'https://pricing.us-east-1.amazonaws.com'
DATA_DIR = f"{os.environ.get("HOME")}/data/AWS_DATA/{TODAY}"
HTTP_TIMEOUT = 20

if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR, exist_ok=True)

WORKERS = (os.cpu_count() -2 ) * 2

def get_offer_data(key, val, url):
    """get offer data."""
    logger.info("Getting offer %s data", key)
    url = f'{API}{val['versionIndexUrl']}'
    r = requests.get(url, timeout=HTTP_TIMEOUT).json()
    logger.info(url)

    json_str = json.dumps(r)
    filename = f'{DATA_DIR}/pricing_{key}.json'

    with open(filename, 'w', encoding='utf-8') as f:
        f.write(json_str)

    logger.info("Wrote: %s", filename)

    price_key = list(r['versions'].keys())[0]
    price_key_url = f'{API}{r['versions'][price_key]['offerVersionUrl']}'
    price_key_filename = f'{DATA_DIR}/pricing_{key}_{price_key}.json'
    current_r = r = requests.get(price_key_url, timeout=HTTP_TIMEOUT).json()

    with open(price_key_filename, 'w', encoding='utf-8') as f:
        f.write(json.dumps(current_r))

    logger.info('Wrote: %s', price_key_filename)

def get_service_index():
    """Get data."""
    resp_svc_index = requests.get(f'{API}/offers/v1.0/aws/index.json', timeout=HTTP_TIMEOUT)
    filename = f'{DATA_DIR}/service_index.json'
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(json.dumps(resp_svc_index.json()))
    logger.info('Wrote svc index... %s', filename)
    return resp_svc_index.json()


def grab_pricing_data():
    """Get pricing data."""
    service_index = get_service_index()

    logger.info('Preparing to grab %s offers', len(service_index['offers'].items()))

    batch = []

    for key, val in service_index['offers'].items():
        logger.info("Getting offer %s data", key)
        url = f'{API}{val['versionIndexUrl']}'
        req = {
            "key": key,
            "val": val,
            "url": url,
        }
        batch.append(req)

    # We can use a with statement to ensure threads are cleaned up promptly
    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as executor:
        future_to_url = {
            executor.submit(
                get_offer_data,
                run["key"],
                run["val"],
                run["url"],
            ): run
            for run in batch
        }
        for future in concurrent.futures.as_completed(future_to_url):
            url = future_to_url[future]
            try:
                data = future.result()
                logger.debug(data)
            except RuntimeWarning as exc:
                logger.error("%r generated an exception: %s", url, exc)

def main():
    """main entrypoint."""
    grab_pricing_data()

if __name__ == '__main__':
    main()
