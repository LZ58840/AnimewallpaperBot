import PIL
import requests
from PIL import Image

from histogram_encoder import HistogramEncoder
from dhash_encoder import DhashEncoder


class EncoderManager:
    _headers = {"Authorization": f"Client-ID {'REDDIT_USER_AGENT'}"}

    def __init__(self, config_db, encoder_map=None, resolution=(512, 512)):
        self.config_db = config_db
        self.encoder_map = {} if encoder_map is None else encoder_map
        self.resolution = resolution
        self.images = None

    def update(self, images_ctx):
        self.images = []
        for image_ctx in images_ctx:
            image_url, submission_id = image_ctx[1], image_ctx[0]
            if image_obj := self._download_image(image_url) is not None:
                self.images.append((submission_id, image_obj))

    def _download_image(self, url):
        try:
            response = requests.get(url=url, headers=self._headers, stream=True)
            image_obj = Image.open(response.raw).\
                convert("RGB").\
                resize(self.resolution) \
                if response.status_code == 200 \
                else None
            return image_obj
        except (PIL.UnidentifiedImageError, ValueError):
            return None

    def get_encoded_images(self):
        result = {encoder_name: [] for encoder_name in self.encoder_map}
        for image in self.images:
            for encoder_name in self.encoder_map:
                result[encoder_name].append((
                    image[0],
                    self.encoder_map[encoder_name].encode_image(image[1])
                ))
        return result

    @staticmethod
    def _get_histogram_encoder(bins):
        return HistogramEncoder(bins)

    @staticmethod
    def _get_dhash_encoder():
        return DhashEncoder()

    def _load_all_encoders(self):
        self.encoder_map["dhash"] = self._get_dhash_encoder()
        self.encoder_map["4histogram"] = self._get_histogram_encoder(4)

    @classmethod
    def get_default_manager(cls, config_db):
        default_manager = cls(config_db)
        default_manager._load_all_encoders()
        return default_manager
