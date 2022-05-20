import json
import logging
import time

import praw


class Moderator:
    def __init__(self, reddit, subreddit="Animewallpaper", refresh=60, name="animewallpaperbot", settings_default=None):
        self.settings = None
        self.reddit = praw.Reddit(**reddit)
        self.subreddit = self.reddit.subreddit(subreddit)
        self.refresh = refresh
        self.name = name
        self.settings_default = {} if settings_default is None else settings_default
        logging.info("Moderator created.")

    def update_settings(self):
        if self.name not in list(page.name for page in self.subreddit.wiki):
            self.subreddit.wiki.create(
                name=self.name,
                content=json.dumps(self.settings_default),
                reason="Set/reset default settings"
            )
        self.settings = self.settings_default.update(json.loads(self.subreddit.wiki[self.name].content_md))

    def run(self):
        while True:
            logging.debug("Refreshing submissions...")
            logging.debug(f"Operations completed. Next refresh in {self.refresh} seconds.")
            time.sleep(self.refresh)
