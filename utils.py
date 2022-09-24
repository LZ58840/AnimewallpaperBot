import errno
import os
import sys
from contextlib import contextmanager

import pymysql
import pymysql.cursors

from dotenv import load_dotenv
from pathlib import Path

dotenv_path = Path('configs.env')


def load_configs():
    if not load_dotenv(dotenv_path=dotenv_path):
        print("Couldn't load the configuration file. "
              "Please ensure the file `configs.env` is in the same directory as the executable. "
              "You may need to complete and rename the example file `configs_example.env`.",
              file=sys.stderr)
        sys.exit(errno.ENOENT)

    try:
        return {
            "reddit": {
                "client_id": os.environ['REDDIT_CLIENT_ID'],
                "client_secret": os.environ['REDDIT_CLIENT_SECRET'],
                "user_agent": os.environ['REDDIT_USER_AGENT'],
                "username": os.environ['REDDIT_USERNAME'],
                "password": os.environ['REDDIT_PASSWORD']
            },
            "imgur": {
                "auth": os.environ['IMGUR_AUTH']
            },
            "db": {
                "host": os.environ['MYSQL_DOCKER_HOST'],
                "user": os.environ['MYSQL_AWB_USER'],
                "password": os.environ['MYSQL_AWB_PASS'],
                "database": "animewallpaper"
            }
        }

    except KeyError as e:
        print(f"Value {e.args[0]} is not set. "
              "Please ensure all values are set in the file `configs.env`. "
              "You may need to complete and rename the example file `configs_example.env`.",
              file=sys.stderr)
        sys.exit(errno.ENOENT)


# https://stackoverflow.com/a/54847238
# https://rednafi.github.io/digressions/python/2020/03/26/python-contextmanager.html

@contextmanager
def database_ctx(db_config, cur_type=pymysql.cursors.DictCursor):
    con = pymysql.connect(**db_config)
    cur = con.cursor(cur_type)
    try:
        yield cur
    finally:
        con.commit()
        cur.close()
        con.close()
