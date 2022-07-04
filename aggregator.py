import logging
import pymysql.cursors

from curator import PushshiftCurator, UnmoderatedCurator
from database import database_ctx


class Aggregator:
    def __init__(self, config_reddit, config_db):
        self.config_reddit = config_reddit
        self.config_db = config_db
        self.curators = [PushshiftCurator(), UnmoderatedCurator(config_reddit)]

        self.select_subreddit_sql = 'select * from subreddit'
        self.insert_submission_sql = 'replace into submission(id,subreddit,author,created) values (%s, %s, %s, %s)'
        self.insert_link_sql = 'replace into link(id,url,type,created) values (%s, %s, %s, %s)'
        self.latest_submission_sql = 'select subreddit, max(created) as updated from submission group by subreddit'
        self.update_subreddit_sql = 'update subreddit set updated=%s where name=%s'

        logging.debug("Aggregator created.")

    def update(self):
        subreddit_ctx = self._get_subreddit_ctx()
        new_submissions = []
        new_links = []
        for curator in self.curators:
            curator.update(subreddit_ctx)
            new_submissions.extend(curator.get_submissions())
            new_links.extend(curator.get_links())
        with database_ctx(self.config_db) as db:
            logging.info(f"Collected {len(new_submissions)} new submissions. Adding...")
            db.executemany(self.insert_submission_sql, new_submissions)
            db.executemany(self.insert_link_sql, new_links)
        self._set_subreddit_ctx()

    def _get_subreddit_ctx(self):
        logging.debug("Getting subreddit list...")
        with database_ctx(self.config_db) as db:
            db.execute(self.select_subreddit_sql)
            rows = db.fetchall()
        logging.debug(f"Detected {len(rows)} subreddits.")
        return rows

    def _set_subreddit_ctx(self):
        logging.debug("Updating subreddit list...")
        with database_ctx(self.config_db, pymysql.cursors.Cursor) as db:
            db.execute(self.latest_submission_sql)
            rows = [(row[1], row[0]) for row in db.fetchall()]
            db.executemany(self.update_subreddit_sql, rows)
