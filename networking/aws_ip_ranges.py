"""aws pricing"""

import json
import logging
import os
from datetime import datetime

import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TODAY = datetime.now().strftime("%Y-%m-%d")
DATA_DIR = os.environ.get("DATA_DIR", f"{os.environ.get("HOME")}/data")


def get_ip_ranges():
    """Get ip data."""
    resp_ip = requests.get("https://ip-ranges.amazonaws.com/ip-ranges.json", timeout=15)
    filename = f"{DATA_DIR}/{TODAY}-aws-ip-ranges.json"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(json.dumps(resp_ip.json()))
    logger.info("Wrote ip ranges index... %s", filename)
    return resp_ip.json()


def main():
    """main."""
    get_ip_ranges()

if __name__ == "__main__":
    main()
