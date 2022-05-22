import argparse
import json
import logging

import moderator


parser = argparse.ArgumentParser()
parser.add_argument('-v', '--verbose', action='store_true', help="enable verbose/debugging mode")


if __name__ == "__main__":
    args = parser.parse_args()
    verbose = args.verbose

    with open("reddit.json") as reddit_json, open("settings.json") as settings_json:
        reddit, settings_default = json.load(reddit_json), json.load(settings_json)

    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s: %(message)s"
    )

    logging.info(reddit["user_agent"])

    mod = moderator.Moderator(reddit=reddit, settings_default=settings_default)
    mod.run()
