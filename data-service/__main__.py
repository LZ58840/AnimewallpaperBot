import argparse
import logging
import time

from . import DataService

from utils import load_configs

parser = argparse.ArgumentParser(prog='data-service')
parser.add_argument('-v', '--verbose', action='store_true', help="enable verbose/debugging mode")
parser.add_argument('refresh', help="refresh interval in seconds", type=int)

args = parser.parse_args()
verbose = args.verbose
refresh = args.refresh

cfg = load_configs()
delay = 20

logging.basicConfig(
    level=logging.DEBUG if verbose else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s [%(name)s]"
)

logging.info(cfg["reddit"]["user_agent"])

logging.debug(f"Waiting for MySQL to start up, sleeping for {delay} seconds...")
time.sleep(delay)

ds = DataService.new_default_service(cfg)

while True:
    logging.debug("Refreshing...")
    ds.run()
    logging.debug(f"Operations completed. Next refresh in {refresh} seconds.")
    time.sleep(refresh)
