import logging
import pymysql.cursors

from curator import CuratorManager
from database import database_ctx
from extractor import ExtractorManager


class DataManager:
    def __init__(self, config_reddit, config_db):
        self.config_reddit = config_reddit
        self.config_db = config_db

        self.cm = self._get_curator_manager()
        self.em = self._get_extractor_manager()

        # TODO: move refresher to moderatormanager
        # TODO: downloader here

        self.select_subreddit_sql = 'select * from subreddit'
        self.select_submission_sql = 'select submission.id,submission.url,'  # TODO
        self.insert_submission_sql = 'replace into submission(id,url,subreddit,author,created) values (%s,%s,%s,%s,%s)'
        self.insert_image_sql = 'replace into image(url,submission_id) values (%s,%s)'
        self.update_submission_sql = 'update submission set submission.downloaded=if(downloaded.status!=0,1,submission.downloaded-1) from (select submission.id as id, count(image.id) as status from submission left join image on submission.id=image.submission_id where submission.downloaded between %s and 0) as downloaded where submission.id = downloaded.id'
        self.latest_submission_sql = 'select subreddit, max(created) as updated from submission group by subreddit'
        self.update_subreddit_sql = 'update subreddit set updated=%s where name=%s'

        logging.debug("Aggregator created.")

    def update(self):
        self._get_submissions()
        self._get_images()
        self._encode_images()

    def _get_submissions(self):
        subreddit_ctx = self._get_subreddit_ctx()
        new_submissions = self.cm.get_new_submissions(subreddit_ctx)
        # new_images = self._get_new_images(new_submissions)

        logging.info(f"Collected {len(new_submissions)} new submissions. Adding...")
        with database_ctx(self.config_db) as db:
            db.executemany(self.insert_submission_sql, new_submissions)
            # db.executemany(self.insert_image_sql, new_images)
            # db.execute(self.update_submission_sql)
        self._update_subreddit_ctx()

    def _get_images(self):
        submission_ctx = None  # TODO: get all un-extracted links via self._get_submission_ctx()
        new_images = self.em.get_new_images(submission_ctx)
        logging.info(f"Extracted {len(new_images)} new images. Adding...")
        with database_ctx(self.config_db) as db:
            db.executemany(self.insert_submission_sql, new_images)
            db.execute(self.update_submission_sql)

    def _encode_images(self):
        images_ctx = None  # TODO: get all un-downloaded images

    def _get_subreddit_ctx(self):
        logging.debug("Getting subreddit list...")
        with database_ctx(self.config_db) as db:
            db.execute(self.select_subreddit_sql)
            rows = db.fetchall()
        logging.debug(f"Detected {len(rows)} subreddits.")
        return rows

    def _get_submission_ctx(self):
        pass

    def _update_subreddit_ctx(self):
        logging.debug("Updating subreddit list...")
        with database_ctx(self.config_db, pymysql.cursors.Cursor) as db:
            db.execute(self.latest_submission_sql)
            rows = [(row[1], row[0]) for row in db.fetchall()]
            db.executemany(self.update_subreddit_sql, rows)
            # TODO: simplify to one SQL statement and merge with self._get_submissions()

    def _get_curator_manager(self):
        return CuratorManager.get_default_manager(self.config_reddit)

    def _get_extractor_manager(self):
        return ExtractorManager.get_default_manager(self.config_reddit)
