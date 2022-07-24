import PIL
import requests
from PIL import Image

from data.encoder.histogram_encoder import HistogramEncoder
from data.encoder.dhash_encoder import DhashEncoder
from data.database import database_ctx


class EncoderManager:
    _headers = {"User-Agent": "AnimewallpaperBot 1.0a (by u/LZ58840)"}

    def __init__(self, config_db, encoder_map=None, resolution=(512, 512), encoded_tries=3):
        self.config_db = config_db
        self.encoder_map = {} if encoder_map is None else encoder_map
        self.encoded_tries = encoded_tries
        self.resolution = resolution
        self.images = None
        self.update_image_encoded_sql = None
        self.update_image_resolution_sql = 'update image set image.width=%s, image.height=%s where image.id=%s'

    def update(self, images_ctx):
        self._download_images(images_ctx)
        result = self._encode_images()
        resolutions = self._get_image_resolutions()
        with database_ctx(self.config_db) as db:
            for encoder_name in self.encoder_map:
                db.executemany(self.encoder_map[encoder_name].get_insert_sql(), result[encoder_name])
            db.execute(self.update_image_encoded_sql, -self.encoded_tries + 1)
            db.executemany(self.update_image_resolution_sql, resolutions)

    def _download_image(self, url):
        try:
            response = requests.get(url=url, headers=self._headers, stream=True)
            image_obj = Image.open(response.raw).\
                convert("RGB") \
                if response.status_code == 200 \
                else None
            return image_obj
        except (PIL.UnidentifiedImageError, ValueError):
            return None

    def _download_images(self, images_ctx):
        self.images = []
        for image_ctx in images_ctx:
            if (image_obj := self._download_image(image_ctx["url"])) is not None:
                self.images.append((image_ctx["id"], image_obj, image_obj.size))

    def _encode_images(self):
        result = {encoder_name: [] for encoder_name in self.encoder_map}
        for image in self.images:
            for encoder_name in self.encoder_map:
                result[encoder_name].append((
                    image[0],
                    *self.encoder_map[encoder_name].encode_image(image[1].resize(self.resolution))
                ))
        return result

    def _get_image_resolutions(self):
        return [(*image[2], image[0]) for image in self.images]

    def _generate_update_image_sql(self):
        encoder_names = list(self.encoder_map.keys())
        self.update_image_encoded_sql = f"update image, (select image.id, exists(select `{encoder_names[0]}`.id as id from ({self._join_tables_sql(encoder_names)}) where `{encoder_names[0]}`.id=image.id) as result from image) encoded set image.encoded=if(encoded.result,1,image.encoded-1) where image.encoded between %s and 0 and image.id=encoded.id"

    @staticmethod
    def _join_tables_sql(encoder_names):
        joined_tables = f"`{encoder_names[0]}` "
        for i in range(1, len(encoder_names)):
            joined_tables += f"join `{encoder_names[i]}` on `{encoder_names[i-1]}`.id=`{encoder_names[i]}`.id "
        return joined_tables

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
        default_manager._generate_update_image_sql()
        return default_manager
