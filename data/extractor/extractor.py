import re


class Extractor:
    _regex = None

    def extract_images(self, url, match=None):
        raise NotImplementedError

    @classmethod
    def get_default_extractor(cls, **kwargs):
        raise NotImplementedError

    @classmethod
    def match_regex(cls, url):
        return re.match(cls._regex, url)
