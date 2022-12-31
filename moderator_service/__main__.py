import argparse
import asyncio
import logging
import time

from . import ModeratorService

parser = argparse.ArgumentParser(prog='moderator_service')
parser.add_argument('-v', '--verbose', action='store_true', help="enable verbose/debugging mode")
parser.add_argument('-d', '--docker', action='store_true', help="run in Docker container")

args = parser.parse_args()
verbose = args.verbose
docker = args.docker

mysql_delay = 40

logging.basicConfig(
    level=logging.DEBUG if verbose else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s [%(name)s]"
)

logging.debug(f"Waiting for MySQL to start up, sleeping for {mysql_delay} seconds...")
time.sleep(mysql_delay)

ms = ModeratorService(docker)

if __name__ == "__main__":
    asyncio.run(ms.run())
