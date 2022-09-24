import logging
import time

import praw
from pmaw import PushshiftAPI

from utils import load_configs


class Curator:
    def get_submissions(self, subreddit_ctx):
        raise NotImplementedError

    @classmethod
    def new_default_curator(cls, **kwargs):
        raise NotImplementedError


class PushshiftCurator(Curator):
    def __init__(self, limit=None, delta_utc=15778800):
        self.ps = PushshiftAPI()
        self.limit = limit
        self.delta_utc = delta_utc
        self.submission_keys = ("id", "url", "subreddit", "author", "created_utc")
        self.log = logging.getLogger(__name__)

        self.log.debug("PushshiftCurator created.")
        logging.getLogger("pmaw").setLevel(logging.WARNING)

    def get_submissions(self, subreddit_ctx):
        self.log.debug("Updating Pushshift results...")
        query_results = [submission_obj for row in subreddit_ctx for submission_obj in
                         self._get_submission_query(**row)]
        self.log.debug(f"Detected {len(query_results)} new results.")
        return [
            (
                submission_obj["id"],
                submission_obj["url"],
                submission_obj["subreddit"],
                submission_obj["author"],
                submission_obj["created_utc"]
            ) for submission_obj in query_results if all(key in submission_obj for key in self.submission_keys)
        ]

    def _get_submission_query(self, name, updated):
        after_utc = int(time.time()) - self.delta_utc if updated is None else updated
        return self.ps.search_submissions(after=after_utc, subreddit=name, limit=self.limit)

    @classmethod
    def new_default_curator(cls):
        return cls()


class RedditUnmoderatedCurator(Curator):
    def __init__(self, reddit_config, limit=10):
        self.reddit = praw.Reddit(**reddit_config)
        self.limit = limit
        self.log = logging.getLogger(__name__)

        self.log.debug("RedditUnmoderatedCurator created.")

    def get_submissions(self, subreddit_ctx):
        self.log.debug("Updating Reddit unmoderated results...")
        query_results = [submission_obj for row in subreddit_ctx for submission_obj in
                         self._get_submission_query(**row)]
        self.log.debug(f"Detected {len(query_results)} new results.")
        return [
            (
                submission_obj.id,
                submission_obj.url,
                submission_obj.subreddit.display_name,
                submission_obj.author.name,
                int(submission_obj.created_utc)
            ) for submission_obj in query_results
        ]

    def _get_submission_query(self, name, updated):
        after_utc = 0 if updated is None else updated
        return filter(lambda obj: int(obj.created_utc) > after_utc,
                      self.reddit.subreddit(name).mod.unmoderated(limit=self.limit))

    @classmethod
    def new_default_curator(cls, reddit_config):
        return cls(reddit_config)


class CuratorManager:
    def __init__(self, configs, curator_map=None):
        self.configs = configs
        self.curator_map = {} if curator_map is None else curator_map
        self.log = logging.getLogger(__name__)

        self.log.debug("CuratorManager created.")

    def get_submissions(self, subreddit_ctx):
        self.log.debug("Collecting submissions...")
        return [submission for curator in self.curator_map for submission in
                self.curator_map[curator].get_submissions(subreddit_ctx)]

    @staticmethod
    def _new_pushshift_curator():
        return PushshiftCurator.new_default_curator()

    def _new_unmoderated_curator(self):
        return RedditUnmoderatedCurator.new_default_curator(self.configs["reddit"])

    def _load_all_curators(self):
        self.curator_map["pushshift"] = self._new_pushshift_curator()
        self.curator_map["unmoderated"] = self._new_unmoderated_curator()

    @classmethod
    def new_default_manager(cls, configs):
        default_manager = cls(configs)
        default_manager._load_all_curators()
        return default_manager


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(message)s [%(name)s]"
    )

    test_configs = load_configs()

    logging.info(test_configs["reddit"]["user_agent"])

    test_subreddit_ctx = [{'name': 'Animewallpaper', 'updated': int(time.time()) - 86400}]

    cm = CuratorManager.new_default_manager(test_configs)

    start_time = time.time()
    test_new_submissions = cm.get_submissions(test_subreddit_ctx)
    logging.info("Test run completed in %s seconds." % (time.time() - start_time))
