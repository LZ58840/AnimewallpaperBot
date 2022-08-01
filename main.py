import argparse
import errno
import json
import logging
import sys
import time

from data import DataManager

parser = argparse.ArgumentParser()
parser.add_argument('-v', '--verbose', action='store_true', help="enable verbose/debugging mode")
parser.add_argument('refresh', help="refresh interval in seconds", type=int)


if __name__ == "__main__":
    args = parser.parse_args()
    verbose = args.verbose
    refresh = args.refresh

    try:
        with open("config/config_reddit.json") as reddit_json:
            config_reddit = json.load(reddit_json)
    except FileNotFoundError:
        print("Couldn't open the reddit configuration file. "
              "Please ensure the file `config_reddit.json` is in the ./config directory. "
              "You may need to complete and rename the example file `config_reddit_example.json`.",
              file=sys.stderr)
        sys.exit(errno.ENOENT)

    try:
        with open("config/config_settings.json") as settings_json:
            config_settings = json.load(settings_json)
    except FileNotFoundError:
        print("Couldn't open the default settings configuration file. "
              "Please ensure the file `config_settings.json` is in the ./config directory. "
              "You may need to complete and rename the example file `config_settings_example.json`.",
              file=sys.stderr)
        sys.exit(errno.ENOENT)

    try:
        with open("config/config_db.json") as db_json:
            config_db = json.load(db_json)
    except FileNotFoundError:
        print("Couldn't open the database configuration file. "
              "Please ensure the file `config_db.json` is in the ./config directory. "
              "You may need to run `init.sh` to set up the configuration.",
              file=sys.stderr)
        sys.exit(errno.ENOENT)

    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s [%(name)s]"
    )

    logging.info(config_reddit["user_agent"])

    dm = DataManager(config_reddit=config_reddit, config_db=config_db)
    # mod = moderator.Moderator(config_reddit=config_reddit, config_settings=config_settings, config_db=config_db)
    # mod.run()

    while True:
        logging.debug("Refreshing...")
        dm.update()
        logging.debug(f"Operations completed. Next refresh in {refresh} seconds.")
        time.sleep(refresh)
