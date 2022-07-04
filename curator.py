import logging
import time

import praw
from pmaw import PushshiftAPI

from link import get_link_type


class Curator:
    def update(self, subreddit_ctx):
        raise NotImplementedError

    def get_submissions(self):
        raise NotImplementedError

    def get_links(self):
        raise NotImplementedError


class PushshiftCurator(Curator):
    def __init__(self, limit=None, max_expiry=15778800):
        self.ps = PushshiftAPI()
        self.submission_queries = None
        self.limit = limit
        self.max_expiry = max_expiry
        logging.getLogger("pmaw").setLevel(logging.WARNING)
        logging.debug("PushshiftCurator created.")

    def update(self, subreddit_ctx):
        logging.debug("Updating Pushshift results...")
        self.submission_queries = []
        for row in subreddit_ctx:
            subreddit = row["name"]
            after_utc = int(time.time()) - self.max_expiry if row["updated"] is None else row["updated"]
            submission_query = list(self.ps.search_submissions(after=after_utc, subreddit=subreddit, limit=self.limit))
            self.submission_queries.extend(submission_query)
        logging.debug(f"Detected {len(self.submission_queries)} new results.")

    def get_submissions(self):
        return [
            (
                submission_obj["id"],
                submission_obj["subreddit"],
                submission_obj["author"],
                submission_obj["created_utc"]
            )
            for submission_obj in self.submission_queries
        ]

    def get_links(self):
        return [
            (
                submission_obj["id"],
                submission_obj["url"],
                get_link_type(submission_obj["url"]),
                submission_obj["created_utc"]
            )
            for submission_obj in self.submission_queries
        ]


class UnmoderatedCurator(Curator):
    def __init__(self, config_reddit, limit=10):
        self.reddit = praw.Reddit(**config_reddit)
        self.submission_queries = None
        self.limit = limit
        logging.debug("UnmoderatedCurator created.")

    def update(self, subreddit_ctx):
        logging.debug("Updating Reddit unmoderated results...")
        self.submission_queries = []
        for row in subreddit_ctx:
            subreddit = row["name"]
            submission_query = list(self.reddit.subreddit(subreddit).mod.unmoderated(limit=self.limit))
            self.submission_queries.extend(submission_query)
        logging.debug(f"Detected {len(self.submission_queries)} new results.")

    def get_submissions(self):
        return [
            (
                submission_obj.id,
                submission_obj.subreddit.display_name,
                submission_obj.author.name,
                int(submission_obj.created_utc)
            )
            for submission_obj in self.submission_queries
        ]

    def get_links(self):
        return [
            (
                submission_obj.id,
                submission_obj.url,
                get_link_type(submission_obj.url),
                int(submission_obj.created_utc)
            )
            for submission_obj in self.submission_queries
        ]
