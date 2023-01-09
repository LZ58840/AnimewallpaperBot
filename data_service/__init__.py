import asyncio
from hashlib import md5

from asyncpraw import Reddit
from asyncprawcore.exceptions import RequestException, ResponseException
from aio_pika import DeliveryMode, Message, connect

from utils import async_database_ctx, get_mysql_auth, get_rabbitmq_auth, get_reddit_auth, get_logger


class DataService:
    backoff_sec = 60
    exchange_name = "awb-exchange"
    queue_name = "submission-queue"

    def __init__(self, docker: bool):
        self.mysql_auth = get_mysql_auth(docker)
        self.rabbitmq_auth = get_rabbitmq_auth(docker)
        self.reddit_auth = get_reddit_auth()
        self.log = get_logger(self.__class__.__name__)

    async def run(self):
        connection = await connect(**self.rabbitmq_auth)
        async with connection:
            async with connection.channel() as channel:
                exchange = await channel.get_exchange(name=self.exchange_name)
                while True:
                    try:
                        new_submissions = await self._get_new_submissions()
                        await self.enqueue_new_submissions(exchange, new_submissions)
                    except (RequestException, ResponseException) as e:
                        self.log.error("Failed to get submissions from reddit: %s", e)
                    except Exception as e:
                        self.log.exception("Unknown error: %s", e)
                    finally:
                        await asyncio.sleep(self.backoff_sec)

    async def _get_new_submissions(self) -> list[str]:
        subs_latest_utc_by_name = await self._refresh_subreddits()
        if len(subs_latest_utc_by_name) == 0:
            return []
        # TODO: combine subreddits for now until submission frequency increases
        # TODO: try using PRAW submission stream
        async with Reddit(**self.reddit_auth, timeout=30) as reddit:
            combined_subreddit_name: str = "+".join(subs_latest_utc_by_name.keys())
            combined_subreddit = await reddit.subreddit(display_name=combined_subreddit_name)
            new_submissions = [
                submission.id
                async for submission in combined_subreddit.new(limit=100)
                if submission.created_utc > subs_latest_utc_by_name[submission.subreddit.display_name]
            ] + [
                submission.id
                async for submission in combined_subreddit.mod.spam(limit=100, only="submissions")
                if submission.created_utc > subs_latest_utc_by_name[submission.subreddit.display_name]
            ]
        return new_submissions

    async def _refresh_subreddits(self) -> dict[str, int]:
        async with async_database_ctx(self.mysql_auth) as db:
            await db.execute('UPDATE subreddits s,'
                             '(SELECT subreddit, MAX(created_utc) AS latest_utc '
                             'FROM submissions GROUP BY subreddit) u '
                             'SET s.latest_utc=u.latest_utc '
                             'WHERE s.name=u.subreddit')
            await db.execute('SELECT name, latest_utc FROM subreddits WHERE latest_utc IS NOT NULL')
            subs = await db.fetchall()
        subs_latest_utc_by_name: dict[str, int] = {sub['name']: sub['latest_utc'] for sub in subs}
        return subs_latest_utc_by_name

    async def enqueue_new_submissions(self, exchange, new_submissions: list[str]):
        enqueue_tasks = []
        for new_submission_id in new_submissions:
            msg_body = new_submission_id.encode()
            dedup_header = md5(msg_body).hexdigest()
            msg = Message(
                msg_body,
                delivery_mode=DeliveryMode.PERSISTENT,
                headers={'x-deduplication-header': dedup_header}
            )
            enqueue_task = asyncio.create_task(exchange.publish(msg, routing_key=self.queue_name))
            enqueue_tasks.append(enqueue_task)
        await asyncio.gather(*enqueue_tasks)
