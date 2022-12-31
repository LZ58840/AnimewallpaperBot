import asyncio
import json
import time
from unittest import TestCase

import praw
from praw.models import Submission, Comment

from data_worker import DataWorker
from moderator_worker import ModeratorWorker, ModeratorWorkerStatus
from tests import SettingsFactory, ImageFactory
from utils import get_test_reddit_auth, get_reddit_auth, get_mysql_auth, database_ctx


class TestWorkflow(TestCase):
    def setUp(self) -> None:
        self.reddit_user = praw.Reddit(**get_test_reddit_auth())
        self.reddit_user.validate_on_submit = True
        self.reddit_mod = praw.Reddit(**get_reddit_auth())
        self.data_worker = DataWorker()
        self.moderator_worker = ModeratorWorker()
        self.settings_factory = SettingsFactory()
        self.image_factory = ImageFactory()
        self.mysql_auth = get_mysql_auth()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.set_debug(True)
        self.loop.run_until_complete(self.data_worker.make_all_sessions())

    def tearDown(self) -> None:
        self.loop.run_until_complete(self.data_worker.close_all_sessions())

    def insertSubredditRow(self, settings, latest_utc=None, revision_utc=None) -> None:
        subreddit_values = ('LZ58840', json.dumps(settings), latest_utc, revision_utc)
        with database_ctx(self.mysql_auth) as db:
            db.execute('INSERT INTO subreddits VALUES (%s, %s, %s, %s)', subreddit_values)

    def makeSubmission(self, title, paths: list[str], flair="") -> Submission:
        if len(paths) == 1:
            return self.reddit_user.subreddit('LZ58840').submit_image(
                title=title,
                image_path=paths[0],
                without_websockets=False,
                timeout=20,
                flair_id='8244ea76-b4fe-11eb-96a3-0ee18ead570d',
                flair_text=flair
            )
        return self.reddit_user.subreddit('LZ58840').submit_gallery(
            title=title,
            images=[{"image_path": path} for path in paths],
            flair_id='8244ea76-b4fe-11eb-96a3-0ee18ead570d',
            flair_text=flair
        )

    def cleanUp(self, submissions: list[Submission], comments: list[Comment]):
        submission_ids = [submission.id for submission in submissions]
        with database_ctx(self.mysql_auth) as db:
            db.executemany('DELETE FROM images WHERE submission_id=%s', submission_ids)
            db.executemany('DELETE FROM submissions WHERE id=%s', submission_ids)
            db.execute('DELETE FROM subreddits WHERE name=%s', 'LZ58840')
        for submission in submissions:
            submission.delete()
        for comment in comments:
            comment.delete()


class TestSingleImageSubmission(TestWorkflow):
    def test_should_not_remove_legal_submission(self):
        self.insertSubredditRow(self.settings_factory.get_all_enabled())
        title = f'AWB Test Legal Single Submission {int(time.time())} [900x1600]'
        image = self.image_factory.get_vertical_wallpaper()
        submission = self.makeSubmission(title=title, paths=[image], flair="Mobile")
        self.addCleanup(self.cleanUp, submissions=[submission], comments=[])
        self.loop.run_until_complete(self.data_worker.process_submission(submission.id))
        response = self.loop.run_until_complete(self.moderator_worker.moderate_submission(submission.id))
        self.assertEqual(response.status, ModeratorWorkerStatus.MODERATED)
        self.assertFalse(response.removed)
        got_submission = self.reddit_mod.submission(submission.id)
        self.assertIsNone(got_submission.banned_by)
        self.assertIsNone(got_submission.removed_by_category)

    def test_should_remove_bad_resolution_aspect_ratio_submission(self):
        self.insertSubredditRow(self.settings_factory.get_all_enabled())
        title = f'AWB Test Two Bad Single Submission {int(time.time())} [192x144]'
        image = self.image_factory.get_placeholder_horizontal_image_tall()
        submission = self.makeSubmission(title=title, paths=[image], flair="Desktop")
        self.addCleanup(self.cleanUp, submissions=[submission], comments=[])
        self.loop.run_until_complete(self.data_worker.process_submission(submission.id))
        response = self.loop.run_until_complete(self.moderator_worker.moderate_submission(submission.id))
        self.assertEqual(response.status, ModeratorWorkerStatus.MODERATED)
        self.assertTrue(response.removed)
        self.assertIsNotNone(response.comment_id)
        got_submission = self.reddit_mod.submission(submission.id)
        self.assertEqual(got_submission.banned_by, "LZ58842")
        self.assertEqual(got_submission.removed_by_category, "moderator")
        got_comment = self.reddit_mod.comment(response.comment_id)
        self.assertEqual(got_comment.author.name, self.reddit_mod.user.me().name)
        self.assertTrue(got_comment.distinguished)
        self.assertTrue(got_comment.stickied)

    def test_should_remove_all_bad_submission(self):
        self.insertSubredditRow(self.settings_factory.get_all_enabled())
        title = f'AWB Test All Bad Single Submission {int(time.time())} [900x1600]'
        image = self.image_factory.get_placeholder_vertical_image_wide()
        submission = self.makeSubmission(title=title, paths=[image], flair="Desktop")
        self.addCleanup(self.cleanUp, submissions=[submission], comments=[])
        self.loop.run_until_complete(self.data_worker.process_submission(submission.id))
        response = self.loop.run_until_complete(self.moderator_worker.moderate_submission(submission.id))
        self.assertEqual(response.status, ModeratorWorkerStatus.MODERATED)
        self.assertTrue(response.removed)
        self.assertIsNotNone(response.comment_id)
        got_submission = self.reddit_mod.submission(submission.id)
        self.assertEqual(got_submission.banned_by, "LZ58842")
        self.assertEqual(got_submission.removed_by_category, "moderator")
        got_comment = self.reddit_mod.comment(response.comment_id)
        self.assertEqual(got_comment.author.name, self.reddit_mod.user.me().name)
        self.assertTrue(got_comment.distinguished)
        self.assertTrue(got_comment.stickied)


class TestGallerySubmission(TestWorkflow):
    def test_should_not_remove_legal_submission(self):
        self.insertSubredditRow(self.settings_factory.get_all_enabled())
        title = f'AWB Test Legal Gallery Submission {int(time.time())} [1920x1080] [900x1600]'
        image_1 = self.image_factory.get_vertical_wallpaper()
        image_2 = self.image_factory.get_horizontal_wallpaper()
        submission = self.makeSubmission(title=title, paths=[image_1, image_2], flair="Gallery")
        self.addCleanup(self.cleanUp, submissions=[submission], comments=[])
        self.loop.run_until_complete(self.data_worker.process_submission(submission.id))
        response = self.loop.run_until_complete(self.moderator_worker.moderate_submission(submission.id))
        self.assertEqual(response.status, ModeratorWorkerStatus.MODERATED)
        self.assertFalse(response.removed)
        got_submission = self.reddit_mod.submission(submission.id)
        self.assertIsNone(got_submission.banned_by)
        self.assertIsNone(got_submission.removed_by_category)

    def test_should_remove_bad_resolution_aspect_ratio_submission(self):
        self.insertSubredditRow(self.settings_factory.get_all_enabled())
        title = f'AWB Test Two Bad Gallery Submission {int(time.time())} [192x144] [900x1600]'
        image_1 = self.image_factory.get_placeholder_horizontal_image_tall()
        image_2 = self.image_factory.get_vertical_wallpaper()
        submission = self.makeSubmission(title=title, paths=[image_1, image_2], flair="Gallery")
        self.addCleanup(self.cleanUp, submissions=[submission], comments=[])
        self.loop.run_until_complete(self.data_worker.process_submission(submission.id))
        response = self.loop.run_until_complete(self.moderator_worker.moderate_submission(submission.id))
        self.assertEqual(response.status, ModeratorWorkerStatus.MODERATED)
        self.assertTrue(response.removed)
        self.assertIsNotNone(response.comment_id)
        got_submission = self.reddit_mod.submission(submission.id)
        self.assertEqual(got_submission.banned_by, "LZ58842")
        self.assertEqual(got_submission.removed_by_category, "moderator")
        got_comment = self.reddit_mod.comment(response.comment_id)
        self.assertEqual(got_comment.author.name, self.reddit_mod.user.me().name)
        self.assertTrue(got_comment.distinguished)
        self.assertTrue(got_comment.stickied)

    def test_should_remove_all_bad_submission(self):
        self.insertSubredditRow(self.settings_factory.get_all_enabled())
        title = f'AWB Test All Bad Single Submission {int(time.time())} [900x1600]'
        image_1 = self.image_factory.get_placeholder_horizontal_image_tall()
        image_2 = self.image_factory.get_vertical_wallpaper()
        submission = self.makeSubmission(title=title, paths=[image_1, image_2], flair="Desktop")
        self.addCleanup(self.cleanUp, submissions=[submission], comments=[])
        self.loop.run_until_complete(self.data_worker.process_submission(submission.id))
        response = self.loop.run_until_complete(self.moderator_worker.moderate_submission(submission.id))
        self.assertEqual(response.status, ModeratorWorkerStatus.MODERATED)
        self.assertTrue(response.removed)
        self.assertIsNotNone(response.comment_id)
        got_submission = self.reddit_mod.submission(submission.id)
        self.assertEqual(got_submission.banned_by, "LZ58842")
        self.assertEqual(got_submission.removed_by_category, "moderator")
        got_comment = self.reddit_mod.comment(response.comment_id)
        self.assertEqual(got_comment.author.name, self.reddit_mod.user.me().name)
        self.assertTrue(got_comment.distinguished)
        self.assertTrue(got_comment.stickied)
