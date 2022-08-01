import logging

from data.curator import CuratorManager
from data.encoder import EncoderManager
from data.database import database_ctx
from data.extractor import ExtractorManager
from data.refresher import Refresher


class DataManager:
    def __init__(self, config_reddit, config_db, extracted_tries=3, encoded_tries=3):
        self.config_reddit = config_reddit
        self.config_db = config_db
        self.extracted_tries = extracted_tries
        self.encoded_tries = encoded_tries
        self.log = logging.getLogger(__name__)

        self.cm = self._get_curator_manager()
        self.xm = self._get_extractor_manager()
        self.rf = self._get_refresher()
        self.em = self._get_encoder_manager()

        self.select_subreddit_sql = 'select * from subreddit'
        self.update_subreddit_sql = 'update subreddit, (select subreddit, max(created) as updated from submission group by subreddit) latest set subreddit.updated=latest.updated where subreddit.name=latest.subreddit'
        self.select_submission_sql = 'select id, url from submission where extracted between %s and 0'
        self.insert_submission_sql = 'replace into submission(id,url,subreddit,author,created) values (%s,%s,%s,%s,%s)'
        self.latest_submission_sql = 'select subreddit, max(created) as updated from submission group by subreddit'
        self.update_submission_sql = 'update submission, (select submission.id as id, count(image.id) as result from submission left join image on submission.id=image.submission_id where submission.extracted between %s and 0 group by submission.id) extracted set submission.extracted=if(extracted.result!=0,1,submission.extracted-1) where submission.id=extracted.id'
        self.select_image_sql = 'select id, url from image where encoded between %s and 0'
        self.insert_image_sql = 'replace into image(url,submission_id) values (%s,%s)'

        self.log.debug("DataManager created.")

    def update(self):
        # self._get_submissions()
        # self._extract_images()
        self._encode_images()
        # self._refresh_submissions()

    def _get_submissions(self):
        subreddit_ctx = self._get_subreddit_ctx()
        new_submissions = self.cm.get_new_submissions(subreddit_ctx)
        self.log.info(f"Collected {len(new_submissions)} new submissions. Adding...")
        with database_ctx(self.config_db) as db:
            db.executemany(self.insert_submission_sql, new_submissions)
            db.execute(self.update_subreddit_sql)

    def _refresh_submissions(self):
        self.rf.update()

    def _extract_images(self):
        submission_ctx = self._get_submission_ctx()
        new_images = self.xm.extract_new_images(submission_ctx)
        self.log.info(f"Extracted {len(new_images)} new images. Adding...")
        with database_ctx(self.config_db) as db:
            db.executemany(self.insert_image_sql, new_images)
            db.execute(self.update_submission_sql, -self.extracted_tries + 1)

    def _encode_images(self):
        images_ctx = self._get_image_ctx()
        self.em.update(images_ctx)

    def _get_subreddit_ctx(self):
        self.log.debug("Getting subreddit list...")
        with database_ctx(self.config_db) as db:
            db.execute(self.select_subreddit_sql)
            rows = db.fetchall()
        self.log.debug(f"Detected {len(rows)} subreddits.")
        return rows

    def _get_submission_ctx(self):
        self.log.debug("Getting un-extracted submissions...")
        with database_ctx(self.config_db) as db:
            db.execute(self.select_submission_sql, -self.extracted_tries + 1)
            rows = db.fetchall()
        self.log.debug(f"Detected {len(rows)} submissions.")
        return rows

    def _get_image_ctx(self):
        self.log.debug("Getting un-encoded images...")
        with database_ctx(self.config_db) as db:
            db.execute(self.select_image_sql, -self.encoded_tries + 1)
            rows = db.fetchall()
        self.log.debug(f"Detected {len(rows)} images.")
        return rows

    def _get_curator_manager(self):
        return CuratorManager.get_default_manager(self.config_reddit)

    def _get_extractor_manager(self):
        return ExtractorManager.get_default_manager(self.config_reddit)

    def _get_encoder_manager(self):
        return EncoderManager.get_default_manager(self.config_db)

    def _get_refresher(self):
        return Refresher.get_default_refresher(self.config_reddit, self.config_db)
