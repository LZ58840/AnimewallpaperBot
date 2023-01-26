import asyncio
import json
from dataclasses import dataclass
from enum import Enum

from aio_pika import connect
from aio_pika.abc import AbstractIncomingMessage
from asyncpraw.models import Submission
from asyncpraw import Reddit
from asyncprawcore.exceptions import RequestException, ResponseException

from utils import async_database_ctx, get_rabbitmq_auth, get_mysql_auth, get_reddit_auth, get_logger
from .rules import RuleBook


class ModeratorWorkerStatus(Enum):
    REFRESHED = 0
    SKIPPED = 1
    MODERATED = 2


# https://stackoverflow.com/a/45426493
@dataclass
class ModeratorWorkerResponse:
    removed: bool
    status: ModeratorWorkerStatus = None
    comment_id: str = None
    comment_body: str = None


class ModeratorWorker:
    exchange_name = "awb-exchange"
    queue_name = "moderator-queue"

    def __init__(self, docker: bool = False):
        self.mysql_auth = get_mysql_auth(docker)
        self.rabbitmq_auth = get_rabbitmq_auth(docker)
        self.reddit_auth = get_reddit_auth()
        self.log = get_logger(self.__class__.__name__)

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
                self.log.info("Moderator queue loaded, ready to receive moderation requests!")
                await asyncio.Future()

    async def on_message(self, message: AbstractIncomingMessage) -> None:
        try:
            async with message.process(requeue=True):
                msg_json = json.loads(str(message.body.decode()))
                submission_id = msg_json.get('id')
                filtered = msg_json.get('filtered')
                await self.moderate_submission(submission_id, filtered)
        except (RequestException, ResponseException) as e:
            self.log.error("Failed to moderate submission %s: %s", submission_id, e)
        except Exception as e:
            self.log.exception("Unknown error: %s", e)

    async def moderate_submission(self, submission_id: str, filtered: bool = False) -> ModeratorWorkerResponse:
        response = ModeratorWorkerResponse(removed=False)
        async with Reddit(**self.reddit_auth, timeout=30) as reddit:
            submission: Submission = await reddit.submission(submission_id)
            async with async_database_ctx(self.mysql_auth) as db:
                removed = submission.banned_by is not None
                deleted = submission.removed_by_category == "deleted"
                approved = submission.approved_by is not None
                if any((removed, deleted, approved)) and not filtered:
                    await db.execute('UPDATE submissions SET removed=%s,deleted=%s,approved=%s WHERE id=%s', (removed, deleted, approved, submission_id))
                    response.status = ModeratorWorkerStatus.REFRESHED
                    return response
                await db.execute('SELECT moderated FROM submissions WHERE id=%s', submission_id)
                result = await db.fetchone()
                if result['moderated']:
                    response.status = ModeratorWorkerStatus.SKIPPED
                    return response
                await db.execute('SELECT settings FROM subreddits WHERE name=%s', submission.subreddit.display_name)
                subreddit = await db.fetchone()
                subreddit_settings = json.loads(subreddit['settings'])
                if not subreddit_settings["enabled"]:
                    response.status = ModeratorWorkerStatus.SKIPPED
                    return response
                # https://stackoverflow.com/a/67695802
                rulebook = RuleBook(submission, subreddit_settings, self.mysql_auth)
                await rulebook.evaluate_flair()
                if rulebook.should_skip():
                    response.status = ModeratorWorkerStatus.SKIPPED
                    return response
                await rulebook.evaluate()
                if rulebook.should_remove():
                    removal_comment_str = rulebook.get_removal_comment()
                    comment = await submission.reply(removal_comment_str)
                    await comment.mod.distinguish(sticky=True)
                    await submission.mod.lock()
                    await submission.mod.remove()
                    response.removed = True
                    response.comment_id = comment.id
                    self.log.info(
                        f"Removed submission {submission_id} from r/{submission.subreddit.display_name}",
                        extra={"context": {
                            "url": f"https://redd.it/{submission_id}",
                            "subreddit": f"r/{submission.subreddit.display_name}",
                        }}
                    )
                await db.execute('UPDATE submissions SET moderated=TRUE WHERE id=%s', submission_id)
        response.status = ModeratorWorkerStatus.MODERATED
        return response
