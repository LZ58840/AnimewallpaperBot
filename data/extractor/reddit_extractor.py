import logging

import praw
from prawcore import Forbidden

from data.extractor.extractor import Extractor


class RedditExtractor(Extractor):
    _regex = r"(^(http|https):\/\/)?(((i|preview)\.redd\.it\/)(?P<imgid>\w+\.\w+)|(www\.reddit\.com\/gallery\/)(?P<galleryid>\w+))"
    _url = "https://i.redd.it"

    def __init__(self, reddit_config):
        self.reddit = praw.Reddit(**reddit_config)
        self.log = logging.getLogger(__name__)

    def extract_images(self, url, match=None):
        match = self.match_regex(url) if match is None else match
        if not match:
            return None

        result = []

        if (img_id := match.group('imgid')) is not None:
            # Single image, just append image URL
            result.append(f"{self._url}/{img_id}")

        elif (gallery_id := match.group('galleryid')) is not None:
            # Gallery of images, access submission to obtain images
            try:
                submission = self.reddit.submission(gallery_id)
                result.extend([
                    f"{self._url}/{item['media_id']}.{submission.media_metadata[item['media_id']]['m'].split('/')[1]}"
                    for item in submission.gallery_data["items"]
                ])

            except (AttributeError, TypeError, Forbidden):
                # Mark 404 and 403 request errors as failed
                self.log.warning(f"Failed to extract {url}, skipping...")
                return None

        return result

    @classmethod
    def get_default_extractor(cls, reddit_config):
        return cls(reddit_config)

