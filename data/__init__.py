import logging

from curator import CuratorManager
from encoder import EncoderManager
from database import database_ctx
from extractor import ExtractorManager
from refresher import Refresher


class DataManager:
    def __init__(self, config_reddit, config_db, extracted_tries=3, downloaded_tries=3):
        self.config_reddit = config_reddit
        self.config_db = config_db
        self.extracted_tries = extracted_tries
        self.downloaded_tries = downloaded_tries

        self.cm = self._get_curator_manager()
        self.xm = self._get_extractor_manager()
        self.rf = self._get_refresher()
        self.em = self._get_encoder_manager()

        self.select_subreddit_sql = 'select * from subreddit'
        self.select_submission_sql = 'select id, url from submission where extracted between %s and 0'
        self.insert_submission_sql = 'replace into submission(id,url,subreddit,author,created) values (%s,%s,%s,%s,%s)'
        self.insert_image_sql = 'replace into image(url,submission_id) values (%s,%s)'
        self.update_submission_sql = 'update submission set submission.downloaded=if(downloaded.result!=0,1,submission.downloaded-1) from (select submission.id as id, count(image.id) as result from submission left join image on submission.id=image.submission_id where submission.downloaded between %s and 0) as downloaded where submission.id=downloaded.id'
        self.latest_submission_sql = 'select subreddit, max(created) as updated from submission group by subreddit'
        self.update_subreddit_sql = 'update subreddit set subreddit.updated=new_updated.updated from (select subreddit, max(created) as updated from submission group by subreddit) new_updated where subreddit.name=new_updated.subreddit'
        self.update_encoder_sql = ''  # TODO
        self.update_image_sql = ''  # TODO
        self.select_image_sql = ''  # TODO

        logging.debug("Aggregator created.")

    def update(self):
        self._get_submissions()
        self._extract_images()
        self._encode_images()
        self._refresh_submissions()

    def _get_submissions(self):
        subreddit_ctx = self._get_subreddit_ctx()
        new_submissions = self.cm.get_new_submissions(subreddit_ctx)
        logging.info(f"Collected {len(new_submissions)} new submissions. Adding...")
        with database_ctx(self.config_db) as db:
            db.executemany(self.insert_submission_sql, new_submissions)
            db.execute(self.update_subreddit_sql)

    def _refresh_submissions(self):
        self.rf.update()

    def _extract_images(self):
        submission_ctx = self._get_submission_ctx()
        new_images = self.xm.extract_new_images(submission_ctx)
        logging.info(f"Extracted {len(new_images)} new images. Adding...")
        with database_ctx(self.config_db) as db:
            db.executemany(self.insert_image_sql, new_images)
            db.execute(self.update_submission_sql)

    def _encode_images(self):
        images_ctx = None  # TODO: get all un-downloaded images
        self.em.update(images_ctx)
        new_images = self.em.get_encoded_images()
        with database_ctx(self.config_db) as db:
            for encoder_name in new_images:
                db.executemany(self.update_encoder_sql, encoder_name, new_images[encoder_name])
            db.execute(self.update_image_sql)

    def _get_subreddit_ctx(self):
        logging.debug("Getting subreddit list...")
        with database_ctx(self.config_db) as db:
            db.execute(self.select_subreddit_sql)
            rows = db.fetchall()
        logging.debug(f"Detected {len(rows)} subreddits.")
        return rows

    def _get_submission_ctx(self):
        logging.debug("Getting un-extracted submissions...")
        with database_ctx(self.config_db) as db:
            db.execute(self.select_submission_sql, -self.extracted_tries)
            rows = db.fetchall()
        logging.debug(f"Detected {len(rows)} submissions.")
        return rows

    def _get_curator_manager(self):
        return CuratorManager.get_default_manager(self.config_reddit)

    def _get_extractor_manager(self):
        return ExtractorManager.get_default_manager(self.config_reddit)

    def _get_encoder_manager(self):
        return EncoderManager.get_default_manager(self.config_db)

    def _get_refresher(self):
        return Refresher.get_default_refresher(self.config_reddit, self.config_db)
