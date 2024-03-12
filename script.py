"""app.py"""
import time
from datetime import datetime

APP_NAME = "Example Python App v1.0"
LOOP_WAIT = 10

print(f"{APP_NAME} Starting...")

while True:
    print(f"{APP_NAME} loop running {datetime.now()}...")
    print(f"Sleeping for {LOOP_WAIT}")
    time.sleep(LOOP_WAIT)
