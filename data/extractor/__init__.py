import logging

from data.extractor.generic_extractor import GenericExtractor
from data.extractor.imgur_extractor import ImgurExtractor
from data.extractor.reddit_extractor import RedditExtractor


class ExtractorManager:
    def __init__(self, config_reddit, extractor_map=None):
        self.config_reddit = config_reddit
        self.extractor_map = {} if extractor_map is None else extractor_map
        self.log = logging.getLogger(__name__)
        self.log.debug("ExtractorManager created.")

    def extract_new_images(self, submissions):
        self.log.debug("Extracting images from submissions...")
        new_images = []
        for submission in submissions:
            if (extracted_images := self._extract_images(submission["url"])) is not None:
                new_images.extend([(link, submission["id"]) for link in extracted_images])
        return new_images

    def _extract_images(self, url):
        for extractor in self.extractor_map:
            if match := self.extractor_map[extractor].match_regex(url):
                self.log.debug(f"{url} is of type {extractor}, extracting...")
                return self.extractor_map[extractor].extract_images(url, match)

    @staticmethod
    def _get_imgur_extractor():
        return ImgurExtractor.get_default_extractor()

    def _get_reddit_extractor(self):
        return RedditExtractor.get_default_extractor(self.config_reddit)

    @staticmethod
    def _get_generic_extractor():
        return GenericExtractor.get_default_extractor()

    def _load_all_extractors(self):
        self.extractor_map["imgur"] = self._get_imgur_extractor()
        self.extractor_map["reddit"] = self._get_reddit_extractor()
        self.extractor_map["generic"] = self._get_generic_extractor()

    @classmethod
    def get_default_manager(cls, config_reddit):
        default_manager = cls(config_reddit)
        default_manager._load_all_extractors()
        return default_manager
