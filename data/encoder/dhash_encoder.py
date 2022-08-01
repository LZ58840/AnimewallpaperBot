import imagehash

from data.encoder.encoder import Encoder


class DhashEncoder(Encoder):
    def encode_image(self, image_obj):
        red, green, blue = image_obj.split()

        return (
            bin(int(str(imagehash.dhash(red)), 16)).lstrip('0b').zfill(64),
            bin(int(str(imagehash.dhash(green)), 16)).lstrip('0b').zfill(64),
            bin(int(str(imagehash.dhash(blue)), 16)).lstrip('0b').zfill(64),
        )

    @staticmethod
    def get_insert_sql():
        return "replace into dhash(id,red,green,blue) values (%s,b%s,b%s,b%s)"

    @classmethod
    def get_default_encoder(cls):
        return DhashEncoder()
