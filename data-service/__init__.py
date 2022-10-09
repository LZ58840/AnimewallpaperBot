import logging
import time

from utils import database_ctx
from .curator import CuratorManager
from .encoder import EncoderManager
from .extractor import ExtractorManager
from .refresher import Refresher


class DataService:
    def __init__(self, configs, cm=None, xm=None, em=None, rf=None):
        self.configs = configs
        self.cm = cm
        self.xm = xm
        self.em = em
        self.rf = rf
        self.log = logging.getLogger(__name__)

        self.log.debug("DataService created.")

    def run(self):
        self._get_new_submissions()
        self._extract_new_images()
        self._encode_new_images()
        self._refresh_submissions()

    def _get_new_submissions(self):
        subreddit_ctx = self._get_subreddit_ctx()
        new_submissions = self.cm.get_submissions(subreddit_ctx)
        with database_ctx(self.configs["db"]) as db:
            if len(new_submissions) > 0:
                self.log.info(f"Collected {len(new_submissions)} new submissions. Adding...")
                db.executemany('replace into submission(id,url,subreddit,author,created) values (%s,%s,%s,%s,%s)', new_submissions)
            db.execute('update subreddit, (select subreddit, max(created) as updated from submission group by subreddit) latest set subreddit.updated=latest.updated where subreddit.name=latest.subreddit')

    def _extract_new_images(self):
        submission_ctx = self._get_submission_unextracted_ctx()
        new_images = self.xm.extract_images(submission_ctx)
        with database_ctx(self.configs["db"]) as db:
            if len(new_images) > 0:
                self.log.info(f"Extracted {len(new_images)} new images. Adding...")
                db.executemany('replace into image_metadata(url,submission_id) values (%s,%s)', new_images)
            db.execute('update submission, (select submission.id as id, count(image_metadata.id) as result from submission left join image_metadata on submission.id=image_metadata.submission_id where submission.extracted=0 group by submission.id) extracted set submission.extracted=if(extracted.result!=0,1,-1) where submission.id=extracted.id')

    def _encode_new_images(self):
        image_ctx = self._get_image_ctx()
        new_encoded_images = self.em.encode_images(image_ctx)
        with database_ctx(self.configs["db"]) as db:
            if len(new_encoded_images) > 0:
                self.log.info(f"Encoded {len(new_encoded_images)} new images. Adding...")
                db.executemany(self._get_insert_image_data_sql(new_encoded_images[0]), new_encoded_images)
            db.execute('update image_metadata, (select image_metadata.id, exists(select image_data.id from image_data where image_data.id=image_metadata.id) as result from image_metadata) encoded set image_metadata.encoded=if(encoded.result,1,-1) where image_metadata.encoded=0 and image_metadata.id=encoded.id')

    def _refresh_submissions(self):
        delta_utc = self.rf.get_delta_utc()
        submission_ctx = self._get_submission_delta_ctx(delta_utc)
        updated_submissions = self.rf.update_submissions(submission_ctx)
        with database_ctx(self.configs["db"]) as db:
            if len(updated_submissions) > 0:
                self.log.info(f"Refreshed {len(updated_submissions)} submissions.")
                db.executemany('update submission set removed=%s where id=%s', updated_submissions)

    def _get_subreddit_ctx(self):
        self.log.debug("Getting subreddit list...")
        with database_ctx(self.configs["db"]) as db:
            db.execute('select * from subreddit')
            rows = db.fetchall()
        self.log.debug(f"Detected {len(rows)} subreddits.")
        return rows

    def _get_submission_unextracted_ctx(self):
        self.log.debug("Getting un-extracted submissions...")
        with database_ctx(self.configs["db"]) as db:
            db.execute('select id, url from submission where extracted=0')
            rows = db.fetchall()
        self.log.debug(f"Detected {len(rows)} submissions.")
        return rows

    def _get_submission_delta_ctx(self, delta_utc):
        self.log.debug(f"Getting submissions from the last {delta_utc} seconds...")
        after_utc = int(time.time()) - delta_utc
        with database_ctx(self.configs["db"]) as db:
            db.execute('select id from submission where created>%s', after_utc)
            rows = db.fetchall()
        self.log.debug(f"Detected {len(rows)} submissions.")
        return rows

    def _get_image_ctx(self):
        self.log.debug("Getting un-encoded images...")
        with database_ctx(self.configs["db"]) as db:
            db.execute('select id, url from image_metadata where encoded=0')
            rows = db.fetchall()
        self.log.debug(f"Detected {len(rows)} images.")
        return rows

    @staticmethod
    def _get_insert_image_data_sql(encoded_image):
        image_data_keys = encoded_image.keys()
        _cols = ','.join(f'`{key}`' for key in image_data_keys)
        _vals = ','.join(f'%({key})s' for key in image_data_keys)
        insert_image_data_sql = 'insert into image_data(%s) values (%s)' % (_cols, _vals)
        return insert_image_data_sql

    def _new_curator_manager(self):
        return CuratorManager.new_default_manager(self.configs)

    def _new_extractor_manager(self):
        return ExtractorManager.new_default_manager(self.configs)

    def _new_encoder_manager(self):
        return EncoderManager.new_default_manager(self.configs)

    def _new_refresher(self):
        return Refresher.new_default_refresher(self.configs)

    def _load_all_managers(self):
        self.cm = self._new_curator_manager()
        self.xm = self._new_extractor_manager()
        self.em = self._new_encoder_manager()
        self.rf = self._new_refresher()

    @classmethod
    def new_default_service(cls, configs):
        default_manager = cls(configs)
        default_manager._load_all_managers()
        return default_manager
