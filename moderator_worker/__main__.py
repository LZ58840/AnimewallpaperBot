import argparse
import asyncio
import logging
import time

from . import ModeratorWorker

parser = argparse.ArgumentParser(prog='moderator_worker')
parser.add_argument('-v', '--verbose', action='store_true', help="enable verbose/debugging mode")
parser.add_argument('-d', '--docker', action='store_true', help="run in Docker container")

args = parser.parse_args()
verbose = args.verbose
docker = args.docker
rabbit_delay = 20

logging.basicConfig(
    level=logging.DEBUG if verbose else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s [%(name)s]"
)

logging.debug(f"Waiting for RabbitMQ to start up, sleeping for {rabbit_delay} seconds...")
time.sleep(rabbit_delay)

mw = ModeratorWorker(docker)

if __name__ == "__main__":
    asyncio.run(mw.run())
