import logging

import praw

from data.curator.curator import Curator


class UnmoderatedCurator(Curator):
    def __init__(self, config_reddit, limit=10):
        self.reddit = praw.Reddit(**config_reddit)
        self.submission_queries = None
        self.limit = limit
        self.log = logging.getLogger(__name__)
        self.log.debug("UnmoderatedCurator created.")

    def update(self, subreddit_ctx):
        self.log.debug("Updating Reddit unmoderated results...")
        self.submission_queries = []
        for row in subreddit_ctx:
            subreddit = row["name"]
            after_utc = 0 if row["updated"] is None else row["updated"]
            submission_query = list(self.reddit.subreddit(subreddit).mod.unmoderated(limit=self.limit))
            latest_query = list(filter(lambda obj: int(obj.created_utc) > after_utc, submission_query))
            self.submission_queries.extend(latest_query)
        self.log.debug(f"Detected {len(self.submission_queries)} new results.")

    def get_submissions(self):
        return [
            (
                submission_obj.id,
                submission_obj.url,
                submission_obj.subreddit.display_name,
                submission_obj.author.name,
                int(submission_obj.created_utc)
            )
            for submission_obj in self.submission_queries
        ]

    @classmethod
    def get_default_curator(cls, config_reddit):
        return cls(config_reddit)
