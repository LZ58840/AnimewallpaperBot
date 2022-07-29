import logging
import time

import praw

from data.database import database_ctx


class Refresher:
    def __init__(self, config_reddit, config_db, max_expiry=86400):
        self.reddit = praw.Reddit(**config_reddit)
        self.config_reddit = config_reddit
        self.config_db = config_db
        self.max_expiry = max_expiry

        self.select_submission_sql = 'select id from submission where created>%s'
        self.update_submission_sql = 'update submission set removed=%s where id=%s'

        logging.debug("Refresher created.")

    def update(self):
        submission_ctx = self._get_submission_ctx()
        submission_names = self._get_submission_names(submission_ctx)
        submissions = self.reddit.info(submission_names)
        updated_attributes = [(self._get_submission_status(s), s.id) for s in submissions]
        with database_ctx(self.config_db) as db:
            logging.debug(f"Updating {len(updated_attributes)} submissions...")
            db.executemany(self.update_submission_sql, updated_attributes)

    def _get_submission_ctx(self):
        logging.debug(f"Getting submissions from the last {self.max_expiry} seconds...")
        after_utc = int(time.time()) - self.max_expiry
        with database_ctx(self.config_db) as db:
            db.execute(self.select_submission_sql, after_utc)
            rows = db.fetchall()
        logging.debug(f"Detected {len(rows)} submissions.")
        return rows

    @staticmethod
    def _get_submission_names(submission_ctx):
        return [f't3_{submission_obj["id"]}' for submission_obj in submission_ctx]

    def _get_submission_status(self, submission_obj):
        if submission_obj.approved_by is not None:
            return -1
        elif submission_obj.removed_by_category not in ["author", "moderator", "deleted"]:
            return 0
        elif submission_obj.banned_by == self.config_reddit["username"]:
            return 1
        elif submission_obj.banned_by is not None and submission_obj.banned_by != "AutoModerator":
            return 2
        elif submission_obj.removed_by_category == "deleted":
            return 3
        else:
            return 0

    @classmethod
    def get_default_refresher(cls, config_reddit, config_db):
        return cls(config_reddit, config_db)
