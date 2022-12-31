import asyncio
import json
import time
from unittest import TestCase

import praw
import oyaml as yaml
from prawcore import NotFound
from deepdiff import DeepDiff

from moderator_service import ModeratorService
from tests import SettingsFactory
from utils import get_reddit_auth, get_mysql_auth, database_ctx


class TestModeratorService(TestCase):
    settings_page_name = f'awb-integ-{int(time.time())}'

    def setUp(self) -> None:
        self.reddit_mod = praw.Reddit(**get_reddit_auth())
        self.moderator_service = ModeratorService()
        self.settings_factory = SettingsFactory()
        self.mysql_auth = get_mysql_auth()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.set_debug(True)

    def insertSubredditRow(self, settings, latest_utc=None, revision_utc=None) -> None:
        subreddit_values = ('LZ58840', json.dumps(settings), latest_utc, revision_utc)
        with database_ctx(self.mysql_auth) as db:
            db.execute('INSERT INTO subreddits VALUES (%s, %s, %s, %s)', subreddit_values)

    def getSubredditRow(self, subreddit='LZ58840'):
        with database_ctx(self.mysql_auth) as db:
            db.execute('SELECT * FROM subreddits WHERE name=%s', subreddit)
            row = db.fetchone()
        return row

    def insertSettingsWiki(self, wiki_name: str, settings):
        try:
            settings_page = self.reddit_mod.subreddit("LZ58840").wiki[wiki_name]
            settings_page.edit(
                content=yaml.safe_dump(settings),
                reason=f'Test manual insertion of settings {int(time.time())}'
            )
        except NotFound:
            raise Exception('Wiki page not found, please run init test.')

    def getSettingsRevisionUTC(self, wiki_name: str):
        try:
            settings_page = self.reddit_mod.subreddit("LZ58840").wiki[wiki_name]
            return settings_page.revision_date
        except NotFound:
            raise Exception('Wiki page not found, please run init test.')


class TestWikiSettings(TestModeratorService):
    def test_should_init_new_wiki_if_not_exists(self):
        self.insertSubredditRow(None)
        self.moderator_service.settings_page_name = self.settings_page_name
        self.loop.run_until_complete(self.moderator_service.update_settings())
        got_subreddit_row = self.getSubredditRow()
        diff = DeepDiff(json.loads(got_subreddit_row['settings']), self.settings_factory.get_default_settings())
        self.assertEqual(diff, {})
        self.assertEqual(got_subreddit_row['revision_utc'], self.getSettingsRevisionUTC(self.moderator_service.settings_page_name))

    def test_should_update_changed_settings(self):
        self.moderator_service.settings_page_name = self.settings_page_name
        old_subreddit_row = self.getSubredditRow()
        old_revision_utc = old_subreddit_row['revision_utc']
        self.insertSettingsWiki(self.settings_page_name, self.settings_factory.get_all_enabled())
        self.loop.run_until_complete(self.moderator_service.update_settings())
        got_subreddit_row = self.getSubredditRow()
        diff = DeepDiff(json.loads(got_subreddit_row['settings']), self.settings_factory.get_all_enabled())
        self.assertEqual(diff, {})
        self.assertGreater(got_subreddit_row['revision_utc'], old_revision_utc)
