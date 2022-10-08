import logging

import praw


class Refresher:
    def __init__(self, configs, delta_utc=86400):
        self.reddit = praw.Reddit(**configs["reddit"])
        self.configs = configs
        self.delta_utc = delta_utc
        self.log = logging.getLogger(__name__)

        self.log.debug("Refresher created.")

    def update_submissions(self, submission_ctx):
        submission_names = [f't3_{submission["id"]}' for submission in submission_ctx]
        submissions = self.reddit.info(submission_names)
        return [(self._get_submission_status(submission_obj), submission_obj.id) for submission_obj in submissions]

    def _get_submission_status(self, submission_obj):
        if submission_obj.approved_by is not None:
            self.log.debug(f"Submission {submission_obj.id} was approved")
            return -1  # APPROVED
        elif submission_obj.removed_by_category not in ["author", "moderator", "deleted"]:
            self.log.debug(f"Submission {submission_obj.id} was removed by reddit")
            return 0  # REMOVED BY REDDIT
        elif submission_obj.banned_by == self.configs["reddit"]["username"]:
            self.log.debug(f"Submission {submission_obj.id} was removed by me")
            return 1  # REMOVED BY ME
        elif submission_obj.banned_by is not None and submission_obj.banned_by != "AutoModerator":
            self.log.debug(f"Submission {submission_obj.id} was removed by another moderator")
            return 2  # REMOVED BY ANOTHER MODERATOR
        elif submission_obj.removed_by_category == "deleted":
            self.log.debug(f"Submission {submission_obj.id} was removed by OP")
            return 3  # REMOVED BY OP
        else:
            return 0  # UNMODERATED

    def get_delta_utc(self):
        return self.delta_utc

    @classmethod
    def new_default_refresher(cls, configs):
        return cls(configs)
