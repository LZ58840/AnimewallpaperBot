import asyncio
import logging
import re
import time

import asyncpraw
from aiohttp import ContentTypeError, ClientSession, ClientTimeout, TCPConnector
from aiohttp_retry import ExponentialRetry, RetryClient
from asyncprawcore import Forbidden

from utils import load_configs


class Extractor:
    _regex = None

    async def extract_from_url(self, session, url, match):
        raise NotImplementedError

    @classmethod
    def new_default_extractor(cls, **kwargs):
        raise NotImplementedError

    @classmethod
    def match_regex(cls, url):
        return re.match(cls._regex, url)

    @classmethod
    def get_regex(cls):
        return cls._regex


class GenericExtractor(Extractor):
    _regex = r"(https?:\/\/.*\.(?:png|jpg|jpeg))"

    async def extract_from_url(self, session, url, match):
        return [url] if match else None

    @classmethod
    def new_default_extractor(cls):
        return cls()


class ImgurExtractor(Extractor):
    _regex = r"(^(http|https):\/\/)?(i\.)?imgur.com\/(gallery\/(?P<imgur_galleryid>\w+)|a\/(?P<imgur_albumid>\w+)#?)?(?P<imgur_imgid>\w*)"

    def __init__(self, imgur_config):
        self.retry_options = ExponentialRetry(attempts=3)
        self.session_timeout = ClientTimeout(total=None, sock_connect=120, sock_read=120)
        self.url_prefix = "https://api.imgur.com/3"
        self.headers = {"Authorization": f"Client-ID {imgur_config['auth']}"}
        self.log = logging.getLogger(__name__)

    async def extract_from_url(self, session, url, match):
        request_url, result = None, None
        retry_client = RetryClient(raise_for_status=False, client_session=session, retry_options=self.retry_options,
                                   timeout=self.session_timeout)

        def extractor_fn(r):
            return None

        if (img_id := match.group('imgur_imgid')) not in [None, '', '0']:
            # Set to image endpoint
            request_url = f"{self.url_prefix}/image/{img_id}"
            extractor_fn = self._extract_from_image

        elif (album_id := match.group('imgur_albumid')) is not None:
            # Set to album endpoint
            request_url = f"{self.url_prefix}/album/{album_id}/images"
            extractor_fn = self._extract_from_album

        elif (gallery_id := match.group('imgur_galleryid')) is not None:
            # Set to gallery endpoint
            request_url = f"{self.url_prefix}/gallery/{gallery_id}/images"
            extractor_fn = self._extract_from_album

        async with retry_client.request(method='GET', url=request_url, headers=self.headers) as response:
            if response.status != 200:
                self.log.warning(f"Failed to grab {request_url} with status {response.status}, skipping...")
                return None

            try:
                response_json = await response.json()
                result = extractor_fn(response_json)

            except (ContentTypeError, KeyError):
                self.log.warning(f"Failed to extract {request_url}, skipping...")
                return None

            finally:
                return result

    @staticmethod
    def _extract_from_image(response_json):
        return [response_json["data"]["link"]]

    @staticmethod
    def _extract_from_album(response_json):
        # Album or gallery of images
        if isinstance(response_json["data"], list):
            # Album/gallery has more than one image
            return [image_json["link"] for image_json in response_json["data"]]
        else:
            # Album/gallery has only one image
            return [response_json["data"]["link"]]

    @classmethod
    def new_default_extractor(cls, imgur_config):
        return cls(imgur_config)


class RedditExtractor(Extractor):
    _regex = r"(^(http|https):\/\/)?(((i|preview)\.redd\.it\/)(?P<reddit_imgid>\w+\.\w+)|(www\.reddit\.com\/gallery\/)(?P<reddit_galleryid>\w+))"

    def __init__(self, reddit_config):
        self.reddit = None
        self.reddit_config = reddit_config
        self.log = logging.getLogger(__name__)
        self.base_url = "https://i.redd.it"

    async def extract_from_url(self, session, url, match):
        self.reddit = asyncpraw.Reddit(**self.reddit_config, requestor_kwargs={"session": session})

        if (img_id := match.group('reddit_imgid')) is not None:
            # Single image, just append image URL
            return [f"{self.base_url}/{img_id}"]

        elif (gallery_id := match.group('reddit_galleryid')) is not None:
            # Gallery of images, access submission to obtain images
            try:
                submission = await self.reddit.submission(gallery_id)
                self.log.debug(f"Extracting {len(submission.gallery_data['items'])} images from {url}...")
                return [
                    f"{self.base_url}/{item['media_id']}.{submission.media_metadata[item['media_id']]['m'].split('/')[1]}"
                    for item in submission.gallery_data["items"]
                ]

            except (AttributeError, TypeError, Forbidden):
                # Mark 404 and 403 request errors as failed
                self.log.warning(f"Failed to extract {url}, skipping...")
                return None

        return None

    @classmethod
    def new_default_extractor(cls, reddit_config):
        return cls(reddit_config)


class ExtractorManager:
    def __init__(self, configs, extractor_map=None, label_regex_str=None):
        self.configs = configs
        self.extractor_map = {} if extractor_map is None else extractor_map
        self.label_regex = re.compile(r"" if label_regex_str is None else label_regex_str)
        self.session_timeout = ClientTimeout(total=None, sock_connect=120, sock_read=120)
        self.log = logging.getLogger(__name__)

        self.log.debug("ExtractorManager created.")

    def extract_images(self, submission_ctx):
        self.log.debug("Extracting images from submissions...")
        labelled_submissions = self._label_urls(submission_ctx)
        return asyncio.run(self._extract_images(labelled_submissions))

    def _label_urls(self, submission_ctx):
        return [
            (
                submission["id"],
                submission["url"],
                *valid_label
            ) for submission in submission_ctx
            if (valid_label := self._label_url(submission["url"])) is not None
        ]

    def _label_url(self, url):
        match = self.label_regex.match(url)
        if match is None:
            return None
        for extractor in self.extractor_map:
            if match.group(extractor) is not None:
                return extractor, match

    async def _extract_images(self, labelled_submissions):
        session_connector = TCPConnector(limit_per_host=50)
        async with ClientSession(timeout=self.session_timeout, connector=session_connector) as session:
            tasks = [
                asyncio.create_task(self._extract_from_url(session, submission))
                for submission in labelled_submissions
            ]
            extracted = await asyncio.gather(*tasks)
            return [image for submission_group in extracted for image in submission_group]

    async def _extract_from_url(self, session, submission):
        submission_id, url, extractor, match = submission
        self.log.debug(f"{url} is of type {extractor}, extracting...")
        extracted_images = await self.extractor_map[extractor].extract_from_url(session, url, match)
        return [(link, submission_id) for link in extracted_images] if extracted_images is not None else []

    def _set_label_regex(self):
        joined_regex_str = r"|".join(
            rf"(?P<{extractor}>{self.extractor_map[extractor].get_regex()})"
            for extractor in self.extractor_map
        )
        self.label_regex = re.compile(joined_regex_str)

    def _new_imgur_extractor(self):
        return ImgurExtractor.new_default_extractor(self.configs["imgur"])

    def _new_reddit_extractor(self):
        return RedditExtractor.new_default_extractor(self.configs["reddit"])

    @staticmethod
    def _new_generic_extractor():
        return GenericExtractor.new_default_extractor()

    def _load_all_extractors(self):
        self.extractor_map["imgur"] = self._new_imgur_extractor()
        self.extractor_map["reddit"] = self._new_reddit_extractor()
        self.extractor_map["generic"] = self._new_generic_extractor()

    @classmethod
    def new_default_manager(cls, configs):
        default_manager = cls(configs)
        default_manager._load_all_extractors()
        default_manager._set_label_regex()
        return default_manager


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(message)s [%(name)s]"
    )

    test_configs = load_configs()

    logging.info(test_configs["reddit"]["user_agent"])

    test_submission_ctx = [
        {
            'id': 'xayvt4',
            'url': 'https://i.redd.it/bl904pd7a3n91.png',
            'subreddit': 'Animewallpaper',
            'author': 'RedditImageNormal',
            'created': 1662840922,
            'removed': 0,
            'extracted': 0
        },
        {
            'id': 'xbb4cl',
            'url': 'https://www.reddit.com/gallery/xbb4cl',
            'subreddit': 'Animewallpaper',
            'author': 'RedditGalleryDeleted',
            'created': 1662877403,
            'removed': 0,
            'extracted': 0
        },
        {
            'id': "xzc29",
            'url': "http://i.imgur.com/LA8iz.jpg",
            'subreddit': 'Animewallpaper',
            'author': 'ImgurImageDeleted',
            'created': 1344573586,
            'removed': 0,
            'extracted': 0
        },
        {
            'id': "zgy1o",
            'url': "http://imgur.com/a/Pto3z",
            'subreddit': 'Animewallpaper',
            'author': 'ImgurAlbumDeleted',
            'created': 1346966986,
            'removed': 0,
            'extracted': 0
        },
        {
            'id': "8hpl9p",
            'url': "https://i.imgur.com/mXiJju2.png",
            'subreddit': 'Animewallpaper',
            'author': 'ImgurImageNormal',
            'created': 1525716554,
            'removed': 0,
            'extracted': 0
        },
        {
            'id': "8hofmw",
            'url': "https://imgur.com/a/AoFpsPk",
            'subreddit': 'Animewallpaper',
            'author': 'ImgurAlbumNormal',
            'created': 1525716554,
            'removed': 0,
            'extracted': 0
        },
        {
            'id': "357r82",
            'url': "https://cdn.awwni.me/q7rs.png",
            'subreddit': 'Animewallpaper',
            'author': 'GenericImageNormal',
            'created': 1431030434,
            'removed': 0,
            'extracted': 0
        },
    ]

    xm = ExtractorManager.new_default_manager(test_configs)

    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    start_time = time.time()
    test_extracted_images = xm.extract_images(test_submission_ctx)
    logging.info("Test run completed in %s seconds." % (time.time() - start_time))
