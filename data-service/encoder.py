import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from collections import ChainMap

import cv2
import imagehash
import numpy as np
from PIL import UnidentifiedImageError, Image
from aiohttp import ClientSession, ClientTimeout, TCPConnector
from aiohttp_retry import ExponentialRetry, RetryClient

from utils import load_configs

Image.MAX_IMAGE_PIXELS = None


class Encoder:
    def __init__(self, resolution=(512, 512)):
        self.resolution = resolution

    async def encode_image(self, image_obj, pool=None):
        raise NotImplementedError

    @classmethod
    def new_default_encoder(cls, **kwargs):
        raise NotImplementedError


class DhashEncoder(Encoder):
    async def encode_image(self, image_obj, pool=None):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(pool, self._encode_image, image_obj.resize(self.resolution))

    @staticmethod
    def _encode_image(image_obj):
        red, green, blue = image_obj.split()

        return {
            "dhash_red": int(str(imagehash.dhash(red)), 16),
            "dhash_green": int(str(imagehash.dhash(green)), 16),
            "dhash_blue": int(str(imagehash.dhash(blue)), 16),
        }

    @classmethod
    def new_default_encoder(cls):
        return DhashEncoder()


class HistogramEncoder(Encoder):
    def __init__(self, resolution=(512, 512), bins=4):
        super().__init__(resolution)
        self.bins = bins
        self.columns = ("4histogram_red_1",
                        "4histogram_red_2",
                        "4histogram_red_3",
                        "4histogram_red_4",
                        "4histogram_green_1",
                        "4histogram_green_2",
                        "4histogram_green_3",
                        "4histogram_green_4",
                        "4histogram_blue_1",
                        "4histogram_blue_2",
                        "4histogram_blue_3",
                        "4histogram_blue_4")

    async def encode_image(self, image_obj, pool=None):
        loop = asyncio.get_event_loop()
        encoded = await loop.run_in_executor(pool, self._encode_image, image_obj.resize(self.resolution))
        return {self.columns[i]: encoded[i] for i in range(len(self.columns))}

    def _encode_image(self, image_obj):
        img_cv = cv2.cvtColor(np.array(image_obj), cv2.COLOR_RGB2BGR)

        return (
            *np.concatenate(
                cv2.calcHist(
                    images=[img_cv],
                    channels=[2],
                    mask=None,
                    histSize=[self.bins],
                    ranges=[0, 256]
                )
            ).ravel().astype(int).tolist(),
            *np.concatenate(
                cv2.calcHist(
                    images=[img_cv],
                    channels=[1],
                    mask=None,
                    histSize=[self.bins],
                    ranges=[0, 256]
                )
            ).ravel().astype(int).tolist(),
            *np.concatenate(
                cv2.calcHist(
                    images=[img_cv],
                    channels=[0],
                    mask=None,
                    histSize=[self.bins],
                    ranges=[0, 256]
                )
            ).ravel().astype(int).tolist()
        )

    @classmethod
    def new_default_encoder(cls, bins):
        return HistogramEncoder(bins)


class EncoderManager:
    def __init__(self, configs, encoder_map=None):
        self.retry_options = ExponentialRetry(attempts=3)
        self.session_timeout = ClientTimeout(total=None, sock_connect=120, sock_read=120)
        self.headers = {"User-Agent": configs["reddit"]["user_agent"]}
        self.encoder_map = {} if encoder_map is None else encoder_map
        self.log = logging.getLogger(__name__)

    def encode_images(self, image_ctx):
        self.log.debug("Encoding images...")
        return asyncio.run(self._download_and_encode_images(image_ctx))

    async def _download_and_encode_images(self, image_ctx):
        session_connector = TCPConnector(limit_per_host=50)
        sem = asyncio.Semaphore(100)
        async with ClientSession(auto_decompress=False, timeout=self.session_timeout, connector=session_connector) as session:
            with ThreadPoolExecutor() as pool:
                tasks = [asyncio.create_task(self._download_and_encode_from_url(session, pool, sem, image)) for image in image_ctx]
                encoded = await asyncio.gather(*tasks)
                return [image_data for image_data in encoded if image_data is not None]

    async def _download_and_encode_from_url(self, session, pool, sem, image):
        retry_client = RetryClient(raise_for_status=False, client_session=session, retry_options=self.retry_options)
        async with sem:
            try:
                async with retry_client.request(method='GET', allow_redirects=False, url=image["url"], headers=self.headers, timeout=self.session_timeout) as response:
                    if response.status != 200:
                        self.log.warning(f"Failed to download {image['url']} with status {response.status}, skipping...")
                        return None

                    image_raw = await response.content.read()
                    with Image.open(BytesIO(image_raw)).convert("RGB") as image_obj:
                        return {"id": image["id"], "width": image_obj.size[0], "height": image_obj.size[1], **dict(ChainMap(*await asyncio.gather(*[asyncio.create_task(self.encoder_map[encoder].encode_image(image_obj, pool)) for encoder in self.encoder_map])))}
            except (UnidentifiedImageError, ValueError):
                return None

    @staticmethod
    def _new_histogram_encoder(bins):
        return HistogramEncoder(bins=bins)

    @staticmethod
    def _new_dhash_encoder():
        return DhashEncoder()

    def _load_all_encoders(self):
        self.encoder_map["dhash"] = self._new_dhash_encoder()
        self.encoder_map["4histogram"] = self._new_histogram_encoder(4)

    @classmethod
    def new_default_manager(cls, configs):
        default_manager = cls(configs)
        default_manager._load_all_encoders()
        return default_manager


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(message)s [%(name)s]"
    )

    test_configs = load_configs()

    logging.info(test_configs["reddit"]["user_agent"])

    test_image_ctx = [
        {
            'id': 2,
            'url': 'https://cdn.awwni.me/q7rs.png',
            'submission_id': '357r82',
            'dhash': 0,
            '4histogram': 0,
            'width': None,
            'height': None,
        },
        {
            'id': 4,
            'url': 'http://i.imgur.com/LA8iz.jpg',
            'submission_id': 'xzc29',
            'dhash': 0,
            '4histogram': 0,
            'width': None,
            'height': None,
        },
        {
            'id': 5,
            'url': 'https://i.redd.it/bl904pd7a3n91.png',
            'submission_id': 'xayvt4',
            'dhash': 0,
            '4histogram': 0,
            'width': None,
            'height': None,
        },
        {
            'id': 7,
            'url': 'https://i.imgur.com/B4F9RQg.jpg',
            'submission_id': '8hofmw',
            'dhash': 0,
            '4histogram': 0,
            'width': None,
            'height': None,
        },
    ]

    em = EncoderManager.new_default_manager(test_configs)

    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    start_time = time.time()
    test_extracted_images = em.encode_images(test_image_ctx)
    logging.info("Test run completed in %s seconds." % (time.time() - start_time))
