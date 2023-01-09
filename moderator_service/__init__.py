import asyncio
import json
import time
from copy import deepcopy
from hashlib import md5

from asyncpraw import Reddit
from asyncprawcore.exceptions import NotFound, RequestException, ResponseException
from aio_pika import DeliveryMode, Message, connect
import oyaml as yaml
from yaml.scanner import ScannerError

from utils import (
    async_database_ctx,
    get_mysql_auth,
    get_rabbitmq_auth,
    get_reddit_auth,
    get_default_settings,
    get_logger
)


class ModeratorService:
    settings_page_name = "awb"
    exchange_name = "awb-exchange"
    queue_name = "moderator-queue"

    def __init__(self, docker: bool = False):
        self.mysql_auth = get_mysql_auth(docker)
        self.rabbitmq_auth = get_rabbitmq_auth(docker)
        self.reddit_auth = get_reddit_auth()
        self.default_settings = get_default_settings()
        self.log = get_logger(self.__class__.__name__)

    async def run(self):
        connection = await connect(**self.rabbitmq_auth)
        async with connection:
            async with connection.channel() as channel:
                exchange = await channel.get_exchange(name=self.exchange_name)
                while True:
                    try:
                        await self.update_settings()
                        await self._enqueue_submissions_to_moderate(exchange)
                    except (RequestException, ResponseException) as e:
                        self.log.error("Failed to update settings from reddit: %s", e)
                    except Exception as e:
                        self.log.exception("Unknown error: %s", e)
                    finally:
                        await asyncio.sleep(60)

    async def update_settings(self):
        async with async_database_ctx(self.mysql_auth) as db:
            await db.execute('SELECT name, revision_utc FROM subreddits')
            subreddits = await db.fetchall()
            async with Reddit(**self.reddit_auth, timeout=30) as reddit:
                tasks = [
                    asyncio.create_task(
                        self._update_settings_by_subreddit(reddit, subreddit["name"], subreddit["revision_utc"])
                    )
                    for subreddit in subreddits
                ]
                results = await asyncio.gather(*tasks)
            subreddits_values = [values for values in results if values is not None]
            await db.executemany('UPDATE subreddits SET revision_utc=%s,settings=%s WHERE name=%s', subreddits_values)

    async def _update_settings_by_subreddit(self, reddit, name, revision_utc):
        subreddit = await reddit.subreddit(name)
        try:
            settings_page = await subreddit.wiki.get_page(self.settings_page_name)
        except NotFound:
            self.log.info(f"Settings page not created for r/{name}, creating new page")
            settings_page = await subreddit.wiki.create(
                name=self.settings_page_name,
                content=yaml.safe_dump(self.default_settings),
                reason="Initial AnimewallpaperBot config."
            )
            await settings_page.mod.update(listed=True, permlevel=2)
            await settings_page.load()
        if revision_utc is None or settings_page.revision_date > revision_utc:
            self.log.info(f"Detected update in settings page for r/{name}, reading")
            current_settings = deepcopy(self.default_settings)
            try:
                current_settings.update(yaml.safe_load(settings_page.content_md))
            except (ValueError, ScannerError):
                self.log.info(f"Couldn't parse the settings page, restoring previous settings")
                await settings_page.edit(
                    content=yaml.safe_dump(deepcopy(self.default_settings)),
                    reason="Initial AnimewallpaperBot config (restored)."
                )
            finally:
                return int(settings_page.revision_date), json.dumps(current_settings), name
        return None

    async def _enqueue_submissions_to_moderate(self, exchange):
        # TODO: fix window to 48 hours for now until posting frequency increases
        after_utc = int(time.time()) - 172800
        async with async_database_ctx(self.mysql_auth) as db:
            await db.execute('SELECT id FROM submissions WHERE created_utc>%s AND NOT deleted', after_utc)
            submissions = await db.fetchall()
        enqueue_tasks = []
        for submission in submissions:
            msg_body = submission['id'].encode()
            dedup_header = md5(msg_body).hexdigest()
            msg = Message(
                msg_body,
                delivery_mode=DeliveryMode.PERSISTENT,
                headers={'x-deduplication-header': dedup_header}
            )
            enqueue_task = asyncio.create_task(exchange.publish(msg, routing_key=self.queue_name))
            enqueue_tasks.append(enqueue_task)
        await asyncio.gather(*enqueue_tasks)
