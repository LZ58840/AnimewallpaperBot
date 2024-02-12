import asyncio
import logging
import random
import re
from typing import Any

import cv2
import imutils
import numpy as np
from aiohttp import ClientSession
from aiohttp_retry import RetryClient
from asyncpraw import Reddit
from asyncpraw.models import Submission
from asyncprawcore.exceptions import RequestException, ResponseException
from aio_pika import connect
from aio_pika.abc import AbstractIncomingMessage

from utils import (
    async_database_ctx,
    get_mysql_auth,
    get_rabbitmq_auth,
    get_reddit_auth,
    get_imgur_auth,
    THUMBNAIL_SIZE
)
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
        self.sift_detector = cv2.SIFT_create()
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
            await asyncio.sleep(random.randint(30, 60))
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
            images_values = [(submission_id, url, width, height, descriptors) for url, width, height, descriptors in images]
            async with async_database_ctx(self.mysql_auth) as db:
                await db.execute('INSERT IGNORE INTO submissions(id,subreddit,created_utc,author,removed,deleted,approved) VALUES(%s,%s,%s,%s,%s,%s,%s)', submission_values)
                await db.executemany('INSERT IGNORE INTO images(submission_id,url,width,height,sift) VALUES (%s,%s,%s,%s,%s)', images_values)
            self.log.info(f"Processed submission {submission_id}")

    async def _process_images(self, submission: Submission) -> list[tuple[str, int, int, str] | Any]:
        urls = await self.extract_image_urls(submission)
        tasks = [asyncio.create_task(self.download_image_to_values(url)) for url in urls]
        results = await asyncio.gather(*tasks)
        return [values for values in results if values is not None]

    async def extract_image_urls(self, submission: Submission) -> list[str]:
        url = submission.url_overridden_by_dest if hasattr(submission, "url_overridden_by_dest") else submission.url
        if (match := re.match(IMGUR_REGEX_STR, url)) is not None:
            return await extract_from_imgur_url(
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

    async def download_image_to_values(self, url) -> tuple[str, int, int, str] | None:
        if re.match(r"(https?://.*\.(?:png|jpg|jpeg))", url) is None:
            return None
        async with RetryClient(raise_for_status=False) as client:
            try:
                async with client.request(method='GET', allow_redirects=False, url=url, headers=self.headers) as resp:
                    if resp.status != 200:
                        return None
                    image_bytes = await resp.content.read()
                    return self._get_image_values(url, image_bytes)
            except Exception as e:
                self.log.error(f"Unable to process {url}, got: %s", e)
                return None

    def _get_image_values(self, url, image_bytes) -> tuple[str, int, int, str]:
        image = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), 1)
        height, width = image.shape[:2]
        resized_image = imutils.resize(image, **{('width' if height >= width else 'height'): THUMBNAIL_SIZE})
        _, descriptors = self.sift_detector.detectAndCompute(resized_image, None)
        descriptors_blob = np.ndarray.dumps(descriptors)
        return url, width, height, descriptors_blob

    async def make_all_sessions(self):
        # DEPRECATED FUNCTION
        self.image_session = ClientSession(auto_decompress=False)
        self.extract_session = ClientSession()

    async def close_all_sessions(self):
        # DEPRECATED FUNCTION
        await self.image_session.close()
        await self.extract_session.close()
