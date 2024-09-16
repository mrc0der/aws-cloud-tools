"""aws pricing"""
import json
import logging
from datetime import datetime

import requests

logging.basicConfig(level = logging.INFO)
logger = logging.getLogger(__name__)

TODAY = datetime.now().strftime("%Y-%m-%d")
API = 'https://pricing.us-east-1.amazonaws.com'


def grab_pricing_data():
    """Get pricing data."""
    data = get_data()

    logger.info('Preparing to grab %s offers', len(data['offers'].items()))
    for key, val in data['offers'].items():
        logger.info("Getting offer %s data", key)
        url = f'{API}{val['versionIndexUrl']}'
        r = requests.get(url, timeout=15).json()
        logger.info(url)

        json_str = json.dumps(r)
        filename = f'data/pricing_{key}.json'
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(json_str)

        price_key = list(r['versions'].keys())[0]
        price_key_url = f'{API}{r['versions'][price_key]['offerVersionUrl']}'
        price_key_filename = f'data/pricing_{key}_{price_key}.json'
        current_r = r = requests.get(price_key_url, timeout=15).json()
        with open(price_key_filename, 'w', encoding='utf-8') as f:
            f.write(json.dumps(current_r))
        logger.info('Wrote: %s', price_key_filename)


def get_data():
    """Get data."""
    resp_svc_index = requests.get(f'{API}/offers/v1.0/aws/index.json', timeout=15)
    filename = 'data/service_index.json'
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(json.dumps(resp_svc_index.json()))
    logger.info('Wrote svc index... %s', filename)
    return resp_svc_index.json()

def main():
    """main entrypoint."""
    grab_pricing_data()

if __name__ == '__main__':
    main()
