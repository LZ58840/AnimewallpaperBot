import json
import logging
import time

import praw


class Moderator:
    def __init__(self,
                 config_reddit,
                 config_settings,
                 config_db,
                 subreddit="Animewallpaper",
                 limit=100,
                 refresh=60,
                 name="animewallpaperbot"):
        self.settings = None
        self.reddit = praw.Reddit(**config_reddit)
        self.subreddit = self.reddit.subreddit(subreddit)
        self.unmoderated = self.subreddit.mod.unmoderated
        self.spam = self.subreddit.mod.spam
        self.limit = limit
        self.refresh = refresh
        self.name = name
        self.config_settings = config_settings
        self.config_db = config_db
        logging.info("Moderator created.")

    def update_settings(self):
        if self.name not in list(page.name for page in self.subreddit.wiki):
            self.subreddit.wiki.create(
                name=self.name,
                content=json.dumps(self.config_settings),
                reason="Set/reset default settings"
            )
            logging.info("Settings page created.")
        self.settings = self.config_settings.update(json.loads(self.subreddit.wiki[self.name].content_md))
        logging.info("Settings updated.")

    def handle_unmoderated(self):
        pass

    def handle_spam(self):
        pass

    def run(self):
        while True:
            logging.debug("Refreshing submissions...")
            logging.debug(f"Operations completed. Next refresh in {self.refresh} seconds.")
            time.sleep(self.refresh)
