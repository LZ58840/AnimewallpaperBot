from data.curator.pushshift_curator import PushshiftCurator
from data.curator.unmoderated_curator import UnmoderatedCurator


class CuratorManager:
    def __init__(self, config_reddit, curator_map=None):
        self.config_reddit = config_reddit
        self.curator_map = {} if curator_map is None else curator_map

    def get_new_submissions(self, subreddit_ctx):
        new_submissions = []
        for curator in self.curator_map:
            self.curator_map[curator].update(subreddit_ctx)
            new_submissions.extend(self.curator_map[curator].get_submissions())
        return new_submissions

    @staticmethod
    def _get_pushshift_curator():
        return PushshiftCurator.get_default_curator()

    def _get_unmoderated_curator(self):
        return UnmoderatedCurator.get_default_curator(self.config_reddit)

    def _load_all_curators(self):
        self.curator_map["pushshift"] = self._get_pushshift_curator()
        self.curator_map["unmoderated"] = self._get_unmoderated_curator()

    @classmethod
    def get_default_manager(cls, config_reddit):
        default_manager = cls(config_reddit)
        default_manager._load_all_curators()
        return default_manager
