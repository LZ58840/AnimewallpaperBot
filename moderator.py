import json
import logging

import praw


class Moderator:
    def __init__(self, config_reddit, config_settings, config_db, max_expiry=86400):
        self.reddit = praw.Reddit(**config_reddit)
        self.max_expiry = max_expiry
        self.name = config_reddit["username"].lower()
        self.settings = {}
        self.config_settings = config_settings
        self.config_db = config_db
        logging.debug("Moderator created.")

    def update_settings(self):
        if self.name not in list(page.name for page in self.subreddit.wiki):
            self.subreddit.wiki.create(
                name=self.name,
                content=json.dumps(self.config_settings),
                reason="Set/reset default settings"
            )
            logging.info("Settings page created.")
        self.settings = self.config_settings.get_new_submissions(json.loads(self.subreddit.wiki[self.name].content_md))
        logging.info("Settings updated.")

    def handle_unmoderated(self):
        pass

    def handle_spam(self):
        pass

    def run(self):
        pass

