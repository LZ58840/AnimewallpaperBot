import asyncio
import json
import time
from unittest import TestCase

import praw
from praw.models import Submission, Comment

from utils import database_ctx, get_reddit_auth, get_test_reddit_auth, get_mysql_auth
from moderator_worker import ModeratorWorker, ModeratorWorkerStatus
from tests import SettingsFactory, ImageFactory


# Base TestCase class for all Moderator Worker related tests to inherit.
# setup and cleanup classes are defined here.
class TestModeratorWorker(TestCase):
    def setUp(self) -> None:
        self.reddit_user = praw.Reddit(**get_test_reddit_auth())
        self.reddit_user.validate_on_submit = True
        self.reddit_mod = praw.Reddit(**get_reddit_auth())
        self.moderator_worker = ModeratorWorker()
        self.settings_factory = SettingsFactory()
        self.image_factory = ImageFactory()
        self.mysql_auth = get_mysql_auth()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.set_debug(True)

    def insertSubredditRow(self, settings, latest_utc=None, revision_utc=None) -> None:
        subreddit_values = ('LZ58840', json.dumps(settings), latest_utc, revision_utc)
        with database_ctx(self.mysql_auth) as db:
            db.execute('INSERT IGNORE INTO subreddits VALUES (%s, %s, %s, %s)', subreddit_values)

    def insertSubmissionRow(self, s_id, created_utc, author='LZ58845', removed=False, deleted=False, approved=False, moderated=False) -> None:
        submission_values = (s_id, 'LZ58840', author, created_utc, removed, deleted, approved, moderated)
        with database_ctx(self.mysql_auth) as db:
            db.execute('INSERT IGNORE INTO submissions VALUES (%s, %s, %s, %s, %s, %s, %s, %s)', submission_values)

    def insertImageRow(self, i_id, s_id, url, width, height) -> None:
        image_values = (i_id, s_id, url, width, height)
        with database_ctx(self.mysql_auth) as db:
            db.execute('INSERT IGNORE INTO images VALUES (%s, %s, %s, %s, %s)', image_values)

    def getSubmissionRow(self, s_id):
        with database_ctx(self.mysql_auth) as db:
            db.execute('SELECT * FROM submissions WHERE id=%s', s_id)
            row = db.fetchone()
        return row

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


class TestModeratorWorkerStatus(TestModeratorWorker):
    def test_should_only_refresh_approved_submission(self):
        self.insertSubredditRow(self.settings_factory.get_default_settings())
        title = f'AWB Test Submission Approved {int(time.time())}'
        image = self.image_factory.get_placeholder_square_image()
        submission = self.makeSubmission(title=title, paths=[image])
        self.addCleanup(self.cleanUp, submissions=[submission], comments=[])
        self.insertSubmissionRow(submission.id, submission.created_utc)
        self.reddit_mod.submission(submission.id).mod.approve()
        response = self.loop.run_until_complete(self.moderator_worker.moderate_submission(submission.id))
        self.assertEqual(response.status, ModeratorWorkerStatus.REFRESHED)
        self.assertFalse(response.removed)
        got_submission_row = self.getSubmissionRow(submission.id)
        self.assertTrue(got_submission_row['approved'])
        got_submission = self.reddit_mod.submission(submission.id)
        self.assertIsNotNone(got_submission.approved_by)

    def test_should_only_refresh_removed_submission(self):
        self.insertSubredditRow(self.settings_factory.get_default_settings())
        title = f'AWB Test Submission Removed {int(time.time())}'
        image = self.image_factory.get_placeholder_square_image()
        submission = self.makeSubmission(title=title, paths=[image])
        self.addCleanup(self.cleanUp, submissions=[submission], comments=[])
        self.insertSubmissionRow(submission.id, submission.created_utc)
        self.reddit_mod.submission(submission.id).mod.remove()
        response = self.loop.run_until_complete(self.moderator_worker.moderate_submission(submission.id))
        self.assertEqual(response.status, ModeratorWorkerStatus.REFRESHED)
        self.assertFalse(response.removed)
        got_submission_row = self.getSubmissionRow(submission.id)
        self.assertTrue(got_submission_row['removed'])
        got_submission = self.reddit_mod.submission(submission.id)
        self.assertEqual(got_submission.banned_by, "AnimewallpaperBot")
        self.assertEqual(got_submission.removed_by_category, "moderator")

    def test_should_only_refresh_deleted_submission(self):
        self.insertSubredditRow(self.settings_factory.get_default_settings())
        title = f'AWB Test Submission Deleted {int(time.time())}'
        image = self.image_factory.get_placeholder_square_image()
        submission = self.makeSubmission(title=title, paths=[image])
        self.addCleanup(self.cleanUp, submissions=[submission], comments=[])
        self.insertSubmissionRow(submission.id, submission.created_utc)
        submission.delete()
        response = self.loop.run_until_complete(self.moderator_worker.moderate_submission(submission.id))
        self.assertEqual(response.status, ModeratorWorkerStatus.REFRESHED)
        self.assertFalse(response.removed)
        got_submission_row = self.getSubmissionRow(submission.id)
        self.assertTrue(got_submission_row['deleted'])
        got_submission = self.reddit_mod.submission(submission.id)
        self.assertEqual(got_submission.removed_by_category, "deleted")

    def test_should_skip_moderated_submission(self):
        self.insertSubredditRow(self.settings_factory.get_default_settings())
        title = f'AWB Test Submission Moderated {int(time.time())}'
        image = self.image_factory.get_placeholder_square_image()
        submission = self.makeSubmission(title=title, paths=[image])
        self.addCleanup(self.cleanUp, submissions=[submission], comments=[])
        self.insertSubmissionRow(submission.id, submission.created_utc, moderated=True)
        response = self.loop.run_until_complete(self.moderator_worker.moderate_submission(submission.id))
        self.assertEqual(response.status, ModeratorWorkerStatus.SKIPPED)
        self.assertFalse(response.removed)
        got_submission = self.reddit_mod.submission(submission.id)
        self.assertIsNone(got_submission.banned_by)
        self.assertIsNone(got_submission.removed_by_category)
        self.assertIsNone(got_submission.approved_by)

    def test_should_moderate_submission_when_enabled(self):
        self.insertSubredditRow(self.settings_factory.get_enabled_settings())
        title = f'AWB Test Settings Enabled {int(time.time())}'
        image = self.image_factory.get_placeholder_square_image()
        submission = self.makeSubmission(title=title, paths=[image])
        self.addCleanup(self.cleanUp, submissions=[submission], comments=[])
        self.insertSubmissionRow(submission.id, submission.created_utc)
        response = self.loop.run_until_complete(self.moderator_worker.moderate_submission(submission.id))
        self.assertEqual(response.status, ModeratorWorkerStatus.MODERATED)
        got_submission_row = self.getSubmissionRow(submission.id)
        self.assertTrue(got_submission_row['moderated'])


class TestResolutionAny(TestModeratorWorker):
    def test_should_not_remove_tagged_submission(self):
        self.insertSubredditRow(self.settings_factory.get_resolution_any_enabled())
        title = f'AWB Test ResolutionAny Tagged {int(time.time())} [256x144]'
        image = self.image_factory.get_placeholder_horizontal_image()
        submission = self.makeSubmission(title=title, paths=[image])
        self.addCleanup(self.cleanUp, submissions=[submission], comments=[])
        self.insertSubmissionRow(submission.id, submission.created_utc)
        response = self.loop.run_until_complete(self.moderator_worker.moderate_submission(submission.id))
        self.assertEqual(response.status, ModeratorWorkerStatus.MODERATED)
        self.assertFalse(response.removed)
        got_submission = self.reddit_mod.submission(submission.id)
        self.assertIsNone(got_submission.banned_by)
        self.assertIsNone(got_submission.removed_by_category)

    def test_should_remove_untagged_submission_with_comment(self):
        self.insertSubredditRow(self.settings_factory.get_resolution_any_enabled())
        title = f'AWB Test ResolutionAny Untagged {int(time.time())}'
        image = self.image_factory.get_placeholder_square_image()
        submission = self.makeSubmission(title=title, paths=[image])
        self.insertSubmissionRow(submission.id, submission.created_utc)
        response = self.loop.run_until_complete(self.moderator_worker.moderate_submission(submission.id))
        self.assertEqual(response.status, ModeratorWorkerStatus.MODERATED)
        self.assertTrue(response.removed)
        self.assertIsNotNone(response.comment_id)
        got_submission = self.reddit_mod.submission(submission.id)
        self.assertEqual(got_submission.banned_by, "AnimewallpaperBot")
        self.assertEqual(got_submission.removed_by_category, "moderator")
        got_comment = self.reddit_mod.comment(response.comment_id)
        self.addCleanup(self.cleanUp, submissions=[submission], comments=[])
        self.assertEqual(got_comment.author.name, self.reddit_mod.user.me().name)
        self.assertTrue(got_comment.distinguished)
        self.assertTrue(got_comment.stickied)


class TestResolutionMismatch(TestModeratorWorker):
    def test_should_not_remove_matched_image(self):
        self.insertSubredditRow(self.settings_factory.get_resolution_mismatch_enabled())
        title = f'AWB Test ResolutionMismatch Single Image Matched [256x144]'
        image = self.image_factory.get_placeholder_horizontal_image()
        submission = self.makeSubmission(title=title, paths=[image])
        self.addCleanup(self.cleanUp, submissions=[submission], comments=[])
        self.insertSubmissionRow(submission.id, submission.created_utc)
        self.insertImageRow(1, submission.id, submission.url, 256, 144)
        response = self.loop.run_until_complete(self.moderator_worker.moderate_submission(submission.id))
        self.assertEqual(response.status, ModeratorWorkerStatus.MODERATED)
        self.assertFalse(response.removed)
        got_submission = self.reddit_mod.submission(submission.id)
        self.assertIsNone(got_submission.banned_by)
        self.assertIsNone(got_submission.removed_by_category)

    def test_should_remove_mismatched_image(self):
        self.insertSubredditRow(self.settings_factory.get_resolution_mismatch_enabled())
        title = f'AWB Test ResolutionMismatch Single Image Mismatched [1280x720]'
        image = self.image_factory.get_placeholder_horizontal_image()
        submission = self.makeSubmission(title=title, paths=[image])
        self.insertSubmissionRow(submission.id, submission.created_utc)
        self.insertImageRow(1, submission.id, submission.url, 256, 144)
        response = self.loop.run_until_complete(self.moderator_worker.moderate_submission(submission.id))
        self.assertEqual(response.status, ModeratorWorkerStatus.MODERATED)
        self.assertTrue(response.removed)
        self.assertIsNotNone(response.comment_id)
        got_submission = self.reddit_mod.submission(submission.id)
        self.assertEqual(got_submission.banned_by, "AnimewallpaperBot")
        self.assertEqual(got_submission.removed_by_category, "moderator")
        got_comment = self.reddit_mod.comment(response.comment_id)
        self.addCleanup(self.cleanUp, submissions=[submission], comments=[])
        self.assertEqual(got_comment.author.name, self.reddit_mod.user.me().name)
        self.assertTrue(got_comment.distinguished)
        self.assertTrue(got_comment.stickied)


class TestResolutionBad(TestModeratorWorker):
    def test_should_not_remove_good_resolution_image(self):
        self.insertSubredditRow(self.settings_factory.get_resolution_bad_enabled(None, '144x256'))
        title = f'AWB Test ResolutionBad Single Image Good [144x256]'
        image = self.image_factory.get_placeholder_vertical_image()
        submission = self.makeSubmission(title=title, paths=[image])
        self.addCleanup(self.cleanUp, submissions=[submission], comments=[])
        self.insertSubmissionRow(submission.id, submission.created_utc)
        self.insertImageRow(1, submission.id, submission.url, 144, 256)
        response = self.loop.run_until_complete(self.moderator_worker.moderate_submission(submission.id))
        self.assertEqual(response.status, ModeratorWorkerStatus.MODERATED)
        self.assertFalse(response.removed)
        got_submission = self.reddit_mod.submission(submission.id)
        self.assertIsNone(got_submission.banned_by)
        self.assertIsNone(got_submission.removed_by_category)

    def test_should_remove_bad_resolution_image(self):
        self.insertSubredditRow(self.settings_factory.get_resolution_bad_enabled('1920x1080', None))
        title = f'AWB Test ResolutionBad Single Image Bad [256x144]'
        image = self.image_factory.get_placeholder_horizontal_image()
        submission = self.makeSubmission(title=title, paths=[image])
        self.addCleanup(self.cleanUp, submissions=[submission], comments=[])
        self.insertSubmissionRow(submission.id, submission.created_utc)
        self.insertImageRow(1, submission.id, submission.url, 256, 144)
        response = self.loop.run_until_complete(self.moderator_worker.moderate_submission(submission.id))
        self.assertEqual(response.status, ModeratorWorkerStatus.MODERATED)
        self.assertTrue(response.removed)
        self.assertIsNotNone(response.comment_id)
        got_submission = self.reddit_mod.submission(submission.id)
        self.assertEqual(got_submission.banned_by, "AnimewallpaperBot")
        self.assertEqual(got_submission.removed_by_category, "moderator")
        got_comment = self.reddit_mod.comment(response.comment_id)
        self.assertEqual(got_comment.author.name, self.reddit_mod.user.me().name)
        self.assertTrue(got_comment.distinguished)
        self.assertTrue(got_comment.stickied)


class TestAspectRatioBad(TestModeratorWorker):
    def test_should_not_remove_proper_aspect_ratio_image(self):
        self.insertSubredditRow(self.settings_factory.get_aspect_ratio_bad_enabled(None, '9:21 to 10:16'))
        title = f'AWB Test AspectRatioBad Single Image Good [144x256]'
        image = self.image_factory.get_placeholder_vertical_image()
        submission = self.makeSubmission(title=title, paths=[image])
        self.addCleanup(self.cleanUp, submissions=[submission], comments=[])
        self.insertSubmissionRow(submission.id, submission.created_utc)
        self.insertImageRow(1, submission.id, submission.url, 144, 256)
        response = self.loop.run_until_complete(self.moderator_worker.moderate_submission(submission.id))
        self.assertEqual(response.status, ModeratorWorkerStatus.MODERATED)
        self.assertFalse(response.removed)
        got_submission = self.reddit_mod.submission(submission.id)
        self.assertIsNone(got_submission.banned_by)
        self.assertIsNone(got_submission.removed_by_category)

    def test_should_remove_aspect_ratio_too_tall_image(self):
        self.insertSubredditRow(self.settings_factory.get_aspect_ratio_bad_enabled('16:10 to none', None))
        title = f'AWB Test AspectRatioBad Single Image Too Tall [192x144]'
        image = self.image_factory.get_placeholder_horizontal_image_tall()
        submission = self.makeSubmission(title=title, paths=[image])
        self.addCleanup(self.cleanUp, submissions=[submission], comments=[])
        self.insertSubmissionRow(submission.id, submission.created_utc)
        self.insertImageRow(1, submission.id, submission.url, 192, 144)
        response = self.loop.run_until_complete(self.moderator_worker.moderate_submission(submission.id))
        self.assertEqual(response.status, ModeratorWorkerStatus.MODERATED)
        self.assertTrue(response.removed)
        self.assertIsNotNone(response.comment_id)
        got_submission = self.reddit_mod.submission(submission.id)
        self.assertEqual(got_submission.banned_by, "AnimewallpaperBot")
        self.assertEqual(got_submission.removed_by_category, "moderator")
        got_comment = self.reddit_mod.comment(response.comment_id)
        self.assertEqual(got_comment.author.name, self.reddit_mod.user.me().name)
        self.assertTrue(got_comment.distinguished)
        self.assertTrue(got_comment.stickied)

    def test_should_remove_aspect_too_wide_image(self):
        self.insertSubredditRow(self.settings_factory.get_aspect_ratio_bad_enabled(None, '9:21 to 10:16'))
        title = f'AWB Test AspectRatioBad Single Image Too Wide [144x192]'
        image = self.image_factory.get_placeholder_vertical_image_wide()
        submission = self.makeSubmission(title=title, paths=[image])
        self.addCleanup(self.cleanUp, submissions=[submission], comments=[])
        self.insertSubmissionRow(submission.id, submission.created_utc)
        self.insertImageRow(1, submission.id, submission.url, 144, 192)
        response = self.loop.run_until_complete(self.moderator_worker.moderate_submission(submission.id))
        self.assertEqual(response.status, ModeratorWorkerStatus.MODERATED)
        self.assertTrue(response.removed)
        self.assertIsNotNone(response.comment_id)
        got_submission = self.reddit_mod.submission(submission.id)
        self.assertEqual(got_submission.banned_by, "AnimewallpaperBot")
        self.assertEqual(got_submission.removed_by_category, "moderator")
        got_comment = self.reddit_mod.comment(response.comment_id)
        self.assertEqual(got_comment.author.name, self.reddit_mod.user.me().name)
        self.assertTrue(got_comment.distinguished)
        self.assertTrue(got_comment.stickied)

class TestRateLimitAny(TestModeratorWorker):
    def test_should_allow_up_to_limit(self):
        self.insertSubredditRow(self.settings_factory.get_rate_limit_any_enabled(intvl=1, freq=3, inc_deleted=True))
        image = self.image_factory.get_placeholder_vertical_image_wide()
        cleanup_list = []
        for i in range(3):
            title = f'AWB Test RateLimitAny {i+1} [144x256]'
            submission = self.makeSubmission(title=title, paths=[image])
            cleanup_list.append(submission)
            self.insertSubmissionRow(submission.id, submission.created_utc)
            response = self.loop.run_until_complete(self.moderator_worker.moderate_submission(submission.id))
            self.assertEqual(response.status, ModeratorWorkerStatus.MODERATED)
            self.assertFalse(response.removed)
            got_submission = self.reddit_mod.submission(submission.id)
            self.assertIsNone(got_submission.banned_by)
            self.assertIsNone(got_submission.removed_by_category)
        self.addCleanup(self.cleanUp, submissions=cleanup_list, comments=[])

    def test_should_remove_past_limit(self):
        self.insertSubredditRow(self.settings_factory.get_rate_limit_any_enabled(intvl=1, freq=3, inc_deleted=True))
        image = self.image_factory.get_placeholder_vertical_image()
        cleanup_list = []
        # Insert non-offending submissions
        for i in range(3):
            title = f'AWB Test RateLimitAny {i+1} [144x256]'
            submission = self.makeSubmission(title=title, paths=[image])
            cleanup_list.append(submission)
            self.insertSubmissionRow(submission.id, submission.created_utc)
            response = self.loop.run_until_complete(self.moderator_worker.moderate_submission(submission.id))
            self.assertEqual(response.status, ModeratorWorkerStatus.MODERATED)
            self.assertFalse(response.removed)
            got_submission = self.reddit_mod.submission(submission.id)
            self.assertIsNone(got_submission.banned_by)
            self.assertIsNone(got_submission.removed_by_category)
        # Insert offending submission
        title = f'AWB Test RateLimitAny 4 [144x256]'
        submission = self.makeSubmission(title=title, paths=[image])
        cleanup_list.append(submission)
        self.insertSubmissionRow(submission.id, submission.created_utc)
        response = self.loop.run_until_complete(self.moderator_worker.moderate_submission(submission.id))
        self.assertEqual(response.status, ModeratorWorkerStatus.MODERATED)
        self.assertTrue(response.removed)
        self.assertIsNotNone(response.comment_id)
        got_submission = self.reddit_mod.submission(submission.id)
        self.assertEqual(got_submission.banned_by, "AnimewallpaperBot")
        self.assertEqual(got_submission.removed_by_category, "moderator")
        got_comment = self.reddit_mod.comment(response.comment_id)
        self.assertEqual(got_comment.author.name, self.reddit_mod.user.me().name)
        self.assertTrue(got_comment.distinguished)
        self.assertTrue(got_comment.stickied)
        # Delete submission
        submission.delete()
        self.loop.run_until_complete(self.moderator_worker.moderate_submission(submission.id))
        # Insert another submission
        title = f'AWB Test RateLimitAny 5 [144x256]'
        submission = self.makeSubmission(title=title, paths=[image])
        cleanup_list.append(submission)
        self.insertSubmissionRow(submission.id, submission.created_utc)
        response = self.loop.run_until_complete(self.moderator_worker.moderate_submission(submission.id))
        self.assertEqual(response.status, ModeratorWorkerStatus.MODERATED)
        self.assertTrue(response.removed)
        self.assertIsNotNone(response.comment_id)
        got_submission = self.reddit_mod.submission(submission.id)
        self.assertEqual(got_submission.banned_by, "AnimewallpaperBot")
        self.assertEqual(got_submission.removed_by_category, "moderator")
        got_comment = self.reddit_mod.comment(response.comment_id)
        self.assertEqual(got_comment.author.name, self.reddit_mod.user.me().name)
        self.assertTrue(got_comment.distinguished)
        self.assertTrue(got_comment.stickied)
        self.addCleanup(self.cleanUp, submissions=cleanup_list, comments=[])


class TestFlair(TestModeratorWorker):
    def test_should_skip_flair(self):
        self.insertSubredditRow(self.settings_factory.get_all_enabled())
        title = f'AWB Test Flair Single Image Other Flair [900x1600]'
        image = self.image_factory.get_vertical_wallpaper()
        submission = self.makeSubmission(title=title, paths=[image], flair="Other")
        self.addCleanup(self.cleanUp, submissions=[submission], comments=[])
        self.insertSubmissionRow(submission.id, submission.created_utc)
        self.insertImageRow(1, submission.id, submission.url, 900, 1600)
        response = self.loop.run_until_complete(self.moderator_worker.moderate_submission(submission.id))
        self.assertEqual(response.status, ModeratorWorkerStatus.SKIPPED)
        self.assertFalse(response.removed)
        got_submission = self.reddit_mod.submission(submission.id)
        self.assertIsNone(got_submission.banned_by)
        self.assertIsNone(got_submission.removed_by_category)

    def test_should_allow_flair(self):
        self.insertSubredditRow(self.settings_factory.get_all_enabled())
        title = f'AWB Test Flair Single Image Allow Flair [900x1600]'
        image = self.image_factory.get_vertical_wallpaper()
        submission = self.makeSubmission(title=title, paths=[image], flair="Mobile")
        self.addCleanup(self.cleanUp, submissions=[submission], comments=[])
        self.insertSubmissionRow(submission.id, submission.created_utc)
        self.insertImageRow(1, submission.id, submission.url, 900, 1600)
        response = self.loop.run_until_complete(self.moderator_worker.moderate_submission(submission.id))
        self.assertEqual(response.status, ModeratorWorkerStatus.MODERATED)
        self.assertFalse(response.removed)
        got_submission = self.reddit_mod.submission(submission.id)
        self.assertIsNone(got_submission.banned_by)
        self.assertIsNone(got_submission.removed_by_category)

    def test_should_filter_flair(self):
        self.insertSubredditRow(self.settings_factory.get_all_enabled())
        title = f'AWB Test Flair Single Image Filter Flair [900x1600]'
        image = self.image_factory.get_vertical_wallpaper()
        submission = self.makeSubmission(title=title, paths=[image], flair="Desktop")
        self.addCleanup(self.cleanUp, submissions=[submission], comments=[])
        self.insertSubmissionRow(submission.id, submission.created_utc)
        self.insertImageRow(1, submission.id, submission.url, 900, 1600)
        response = self.loop.run_until_complete(self.moderator_worker.moderate_submission(submission.id))
        self.assertEqual(response.status, ModeratorWorkerStatus.MODERATED)
        self.assertTrue(response.removed)
        self.assertIsNotNone(response.comment_id)
        got_submission = self.reddit_mod.submission(submission.id)
        self.assertEqual(got_submission.banned_by, "AnimewallpaperBot")
        self.assertEqual(got_submission.removed_by_category, "moderator")
        got_comment = self.reddit_mod.comment(response.comment_id)
        self.assertEqual(got_comment.author.name, self.reddit_mod.user.me().name)
        self.assertTrue(got_comment.distinguished)
        self.assertTrue(got_comment.stickied)
