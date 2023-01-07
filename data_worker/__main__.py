import argparse
import asyncio
import logging
import time

from . import DataWorker

parser = argparse.ArgumentParser(prog='data_worker')
parser.add_argument('-v', '--verbose', action='store_true', help="enable verbose/debugging mode")
parser.add_argument('-d', '--docker', action='store_true', help="run in Docker container")

args = parser.parse_args()
verbose = args.verbose
docker = args.docker

logging.basicConfig(
    level=logging.DEBUG if verbose else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s [%(name)s]"
)

# Wait for RabbitMQ to be ready
time.sleep(20)

dw = DataWorker(docker)

if __name__ == "__main__":
    asyncio.run(dw.run())
