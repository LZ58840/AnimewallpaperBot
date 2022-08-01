import logging
import time

from pmaw import PushshiftAPI

from data.curator.curator import Curator


class PushshiftCurator(Curator):
    def __init__(self, limit=None, max_expiry=15778800):
        self.ps = PushshiftAPI()
        self.submission_queries = None
        self.limit = limit
        self.max_expiry = max_expiry

        self.log = logging.getLogger(__name__)
        self.log.debug("PushshiftCurator created.")
        logging.getLogger("pmaw").setLevel(logging.WARNING)

    def update(self, subreddit_ctx):
        self.log.debug("Updating Pushshift results...")
        self.submission_queries = []
        for row in subreddit_ctx:
            subreddit = row["name"]
            after_utc = int(time.time()) - self.max_expiry if row["updated"] is None else row["updated"]
            submission_query = list(self.ps.search_submissions(after=after_utc, subreddit=subreddit, limit=self.limit))
            self.submission_queries.extend(submission_query)
        self.log.debug(f"Detected {len(self.submission_queries)} new results.")

    def get_submissions(self):
        return [
            (
                submission_obj["id"],
                submission_obj["url"],
                submission_obj["subreddit"],
                submission_obj["author"],
                submission_obj["created_utc"]
            )
            for submission_obj in self.submission_queries
        ]

    @classmethod
    def get_default_curator(cls):
        return cls()
