import logging

from data.extractor.extractor import Extractor


class GenericExtractor(Extractor):
    _regex = r"(https?:\/\/.*\.(?:png|jpg|jpeg))"

    def extract_images(self, url, match=None):
        match = self.match_regex(url) if match is None else match
        if not match:
            return None

        return url

    @classmethod
    def get_default_extractor(cls):
        return cls()
