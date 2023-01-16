import errno
import logging
import os
import sys
from contextlib import asynccontextmanager, contextmanager
from traceback import format_tb

import aiomysql
import pymysql
import pymysql.cursors
import oyaml as yaml

from dotenv import load_dotenv
from pathlib import Path

from asyncio import AbstractEventLoop, get_running_loop
from logging import Handler, NOTSET, LogRecord
from discord_webhook import DiscordWebhook, AsyncDiscordWebhook, DiscordEmbed

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
        },
        'RateLimitAny': {
            'enabled': False,
            'interval_hours': None,
            'frequency': None,
            'incl_deleted': False
        },
        'SourceCommentAny': {
            'enabled': False,
            'timeout_hrs': None,
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


# Borrowed from https://github.com/chinnichaitanya/python-discord-logger/blob/master/discord_logger/message_logger.py
# Borrowed from https://github.com/regulad/dislog/blob/master/src/dislog/handler.py
class DiscordWebhookHandler(Handler):
    _username = "AnimewallpaperBot"
    _icon = None

    def __init__(self, webhook_url: str, level: int = NOTSET, *, as_async: bool = False) -> None:
        super().__init__(level)
        self.webhook_url = webhook_url
        self._async = as_async

    def emit(self, record: LogRecord) -> None:
        self.format(record)
        content = record.message
        embed_color = self._get_color_by_level(record.levelno)
        embed_icon = self._get_icon_by_level(record.levelno)
        embed_title = self._get_title_by_level(record.levelno)
        embed = DiscordEmbed(title=embed_icon + ' ' + embed_title, description=content, color=embed_color)
        embed.set_author(name=record.name)

        # Context is passed in as dict
        ctx = record.__dict__.get("context")
        if ctx is not None and isinstance(ctx, dict):
            meta_yml = yaml.dump(ctx, indent=4, default_flow_style=False, sort_keys=False)
            embed.add_embed_field(name="Context", value=f"```{str(meta_yml)}```", inline=False)

        if record.levelno == logging.ERROR and record.exc_text is not None:
            exc_stack = self.format_traceback(record.exc_info)
            embed.add_embed_field(name="Traceback (most recent call last):", value=f"```{exc_stack}```", inline=False)

        embed.set_footer(text=record.asctime)

        if self._async:
            async_webhook = AsyncDiscordWebhook(
                url=self.webhook_url,
                username=self._username,
                avatar_url=self._icon
            )
            # TODO: Current caveat is that this task will not be related to the (async) thread that calls emit()
            # TODO: The logs will be sent only once the calling thread sleeps
            async_webhook.add_embed(embed)
            loop: AbstractEventLoop = get_running_loop()
            loop.create_task(async_webhook.execute())
        else:
            webhook = DiscordWebhook(url=self.webhook_url, username=self._username, avatar_url=self._icon)
            webhook.add_embed(embed)
            webhook.execute()

    @staticmethod
    def _get_color_by_level(levelno: int) -> str:
        match levelno:
            case logging.DEBUG:
                return '36B37E'
            case logging.INFO:
                return '00B8D9'
            case logging.WARNING:
                return 'FFAB00'
            case logging.ERROR:
                return 'FF5630'
            case logging.CRITICAL:
                return '6554C0'
            case _:
                return '172B4D'

    @staticmethod
    def _get_icon_by_level(levelno: int) -> str:
        match levelno:
            case logging.DEBUG:
                return ':beetle:'
            case logging.INFO:
                return ':bell:'
            case logging.WARNING:
                return ':warning:'
            case logging.ERROR:
                return ':x:'
            case logging.CRITICAL:
                return ':bangbang:'
            case _:
                return ':question:'

    @staticmethod
    def _get_title_by_level(levelno: int) -> str:
        match levelno:
            case logging.DEBUG:
                return 'Debug'
            case logging.INFO:
                return 'Info'
            case logging.WARNING:
                return 'Warning'
            case logging.ERROR:
                return 'Error'
            case logging.CRITICAL:
                return 'Critical'
            case _:
                return '???'

    @staticmethod
    def format_traceback(tb):
        tb_list = []
        tb_body = format_tb(tb[2])
        # Discord embed value has 1024-character limit
        if len("".join(tb_body)) > 1024:
            tb_list.append('  .\n  .\n  .\n')
            tb_list += tb_body[-3:]
        else:
            tb_list += tb_body
        return "".join(tb_list)


def get_logger(name):
    """
    Create logger for current module, and if available attach a Discord Webhook Handler
    for output to Discord logging channel

    :param name: module name
    :return: Logger obj
    """
    try:
        webhook_url = os.environ['DISCORD_WEBHOOK']
        lg = logging.getLogger(name)
        handler = DiscordWebhookHandler(webhook_url=webhook_url, as_async=True)
        handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s [%(name)s]"))
        lg.addHandler(handler)
        return lg
    except KeyError:
        return logging.getLogger(name)
