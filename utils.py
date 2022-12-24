import errno
import os
import sys
from contextlib import asynccontextmanager, contextmanager

import aiomysql
import pymysql
import pymysql.cursors

from dotenv import load_dotenv
from pathlib import Path

dotenv_path = Path(os.path.join(os.path.dirname(os.path.realpath(__file__)), ".env"))
if not load_dotenv(dotenv_path=dotenv_path):
    print("Couldn't load the configuration file. "
          "Please ensure the file `.env` is in the same directory as the executable. "
          "You may need to complete and rename the example file `.env-example`.",
          file=sys.stderr)
    sys.exit(errno.ENOENT)


def get_reddit_auth():
    try:
        return {
            "client_id": os.environ['AWB_CLIENT_ID'],
            "client_secret": os.environ['AWB_CLIENT_SECRET'],
            "user_agent": f"python:awb:v2.0b (by u/AnimewallpaperBot)",
            "refresh_token": os.environ['AWB_TOKEN'],
        }

    except KeyError as e:
        _raise_env_missing(e)


def get_test_reddit_auth():
    try:
        return {
            "client_id": os.environ['TEST_CLIENT_ID'],
            "client_secret": os.environ['TEST_CLIENT_SECRET'],
            "user_agent": f"python:awb:test (by u/{os.environ['TEST_USERNAME']})",
            "username": os.environ['TEST_USERNAME'],
            "password": os.environ['TEST_PASSWORD']
        }

    except KeyError as e:
        _raise_env_missing(e)


def get_imgur_auth():
    try:
        return {
            "Authorization": f"Client-ID {os.environ['IMGUR_AUTH']}"
        }

    except KeyError as e:
        _raise_env_missing(e)


def get_mysql_auth(docker=False):
    try:
        return {
            "host": "awb_mysql" if docker else "localhost",
            "user": "animewallpaperbot",
            "password": os.environ['MYSQL_PASS'],
            "db": "awb",
        }

    except KeyError as e:
        _raise_env_missing(e)


def get_rabbitmq_auth(docker=False):
    try:
        return {
            "host": "awb_rabbitmq" if docker else "localhost",
            "login": "animewallpaperbot",
            "password": os.environ['RABBITMQ_PASS'],
        }

    except KeyError as e:
        _raise_env_missing(e)


def get_default_settings():
    return {
        'enabled': False,
        'flairs': {},
        'ResolutionAny': {'enabled': False},
        'ResolutionMismatch': {'enabled': False},
        'ResolutionBad': {
            'enabled': False,
            'horizontal': None,
            'vertical': None,
            'square': None
        },
        'AspectRatioBad': {
            'enabled': False,
            'horizontal': None,
            'vertical': None
        }
    }


# https://stackoverflow.com/a/54847238
# https://rednafi.github.io/digressions/python/2020/03/26/python-contextmanager.html
@asynccontextmanager
async def async_database_ctx(auth):
    # TODO: logging + error handling
    con = await aiomysql.connect(**auth)
    cur = await con.cursor(aiomysql.cursors.DictCursor)
    try:
        yield cur
    finally:
        await con.commit()
        await cur.close()
        con.close()


@contextmanager
def database_ctx(auth):
    # TODO: logging + error handling
    con = pymysql.connect(**auth)
    cur = con.cursor(pymysql.cursors.DictCursor)
    try:
        yield cur
    finally:
        con.commit()
        cur.close()
        con.close()


def _raise_env_missing(e: KeyError):
    print(f"Value {e.args[0]} is not set. "
          "Please ensure all values are set in the file `.env`. "
          "You may need to complete and rename the example file `.env-example`.",
          file=sys.stderr)
    sys.exit(errno.ENOENT)


# https://medium.com/thefloatingpoint/pythons-round-function-doesn-t-do-what-you-think-71765cfa86a8
def normal_round(num, ndigits=0):
    """
    Rounds a float to the specified number of decimal places.
    num: the value to round
    ndigits: the number of digits to round to
    """
    if ndigits == 0:
        return int(num + 0.5)
    else:
        digit_value = 10 ** ndigits
        return int(num * digit_value + 0.5) / digit_value
