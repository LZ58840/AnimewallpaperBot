import asyncio
import logging
import re
from io import BytesIO
from typing import Any

from aiohttp import ClientSession
from aiohttp_retry import RetryClient
from asyncpraw import Reddit
from asyncpraw.models import Submission
from asyncprawcore.exceptions import RequestException, ResponseException
from aio_pika import connect
from aio_pika.abc import AbstractIncomingMessage
from PIL import UnidentifiedImageError, Image

from utils import async_database_ctx, get_mysql_auth, get_rabbitmq_auth, get_reddit_auth, get_imgur_auth
from .extractors import (
    IMGUR_REGEX_STR,
    REDDIT_REGEX_STR,
    extract_from_imgur_url,
    extract_from_reddit_url
)


class DataWorker:
    exchange_name = "awb-exchange"
    queue_name = "submission-queue"

    def __init__(self, docker: bool = False):
        self.mysql_auth = get_mysql_auth(docker)
        self.rabbitmq_auth = get_rabbitmq_auth(docker)
        self.reddit_auth = get_reddit_auth()
        self.imgur_auth = get_imgur_auth()
        self.image_session = None
        self.extract_session = None
        self.headers = {"User-Agent": self.reddit_auth["user_agent"]}
        self.log = logging.getLogger(self.__class__.__name__)

    async def run(self):
        connection = await connect(**self.rabbitmq_auth)
        async with connection:
            async with connection.channel() as channel:
                await channel.set_qos(prefetch_count=50)
                exchange = await channel.declare_exchange(name=self.exchange_name)
                queue = await channel.declare_queue(
                    name=self.queue_name,
                    durable=True,
                    arguments={'x-message-deduplication': True}
                )
                await queue.bind(exchange)

                await queue.consume(self.on_message)
                self.log.info("Submission queue loaded, ready to receive retrieval requests!")
                await asyncio.Future()

    async def on_message(self, message: AbstractIncomingMessage) -> None:
        try:
            async with message.process(requeue=True):
                submission_id = str(message.body.decode())
                await self.process_submission(submission_id)
        except (RequestException, ResponseException) as e:
            self.log.error("Failed to retrieve submission %s from reddit: %s", submission_id, e)
        except Exception as e:
            self.log.exception("Unknown error: %s", e)

    async def process_submission(self, submission_id: str):
        async with Reddit(**self.reddit_auth, timeout=30) as reddit:
            submission: Submission = await reddit.submission(submission_id)
            subreddit: str = submission.subreddit.display_name
            created_utc: int = submission.created_utc
            removed: bool = submission.banned_by is not None
            deleted: bool = submission.removed_by_category == "deleted"
            approved: bool = submission.approved_by is not None
            author: str = submission.author.name
            images = await self._process_images(submission)
            submission_values = (submission_id, subreddit, created_utc, author, removed, deleted, approved)
            images_values = [(submission_id, url, width, height) for url, width, height in images]
            async with async_database_ctx(self.mysql_auth) as db:
                await db.execute('INSERT IGNORE INTO submissions(id,subreddit,created_utc,author,removed,deleted,approved) VALUES(%s,%s,%s,%s,%s,%s,%s)', submission_values)
                await db.executemany('INSERT IGNORE INTO images(submission_id,url,width,height) VALUES (%s,%s,%s,%s)', images_values)
            self.log.info(
                f"Processed submission {submission_id}",
                extra={"context": {
                    "url": f"https://redd.it/{submission_id}",
                    "subreddit": f"r/{subreddit}",
                    "num_images": len(images_values)
                }}
            )

    async def _process_images(self, submission: Submission) -> list[tuple[str, int, int] | Any]:
        urls = await self.extract_image_urls(submission)
        tasks = [asyncio.create_task(self.download_image_to_values(url)) for url in urls]
        results = await asyncio.gather(*tasks)
        return [values for values in results if values is not None]

    async def extract_image_urls(self, submission: Submission) -> list[str]:
        url = submission.url_overridden_by_dest if hasattr(submission, "url_overridden_by_dest") else submission.url
        if (match := re.match(IMGUR_REGEX_STR, url)) is not None:
            return await extract_from_imgur_url(
                self.extract_session,
                self.imgur_auth,
                match.group('image_id'),
                match.group('album_id'),
                match.group('gallery_id')
            )
        elif (match := re.match(REDDIT_REGEX_STR, url)) is not None:
            # Submission is x-post, load original submission instead
            gallery_id: str | None = match.group('gallery_id')
            if gallery_id is not None and gallery_id != submission.id:
                async with Reddit(**self.reddit_auth, timeout=30) as reddit:
                    submission = await reddit.submission(gallery_id)
            return await extract_from_reddit_url(
                submission,
                match.group('image_id'),
                match.group('gallery_id')
            )
        else:
            return [url]

    async def download_image_to_values(self, url) -> tuple[str, int, int] | None:
        if re.match(r"(https?://.*\.(?:png|jpg|jpeg))", url) is None:
            return None
        client = RetryClient(raise_for_status=False, client_session=self.image_session)
        try:
            async with client.request(method='GET', allow_redirects=False, url=url, headers=self.headers) as response:
                if response.status != 200:
                    return None
                image_bytes = await response.content.read()
                with Image.open(BytesIO(image_bytes)).convert("RGB") as image:
                    width, height = image.size
                    return url, width, height
        except (UnidentifiedImageError, ValueError):
            return None

    async def make_all_sessions(self):
        self.image_session = ClientSession(auto_decompress=False)
        self.extract_session = ClientSession()

    async def close_all_sessions(self):
        await self.image_session.close()
        await self.extract_session.close()
