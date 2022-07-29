import imagehash

from data.encoder.encoder import Encoder


class DhashEncoder(Encoder):
    def encode_image(self, image_obj):
        red, green, blue = image_obj.split()

        return {
            "red": bin(int(str(imagehash.dhash(red)), 16)).lstrip('0b').zfill(64),
            "green": bin(int(str(imagehash.dhash(green)), 16)).lstrip('0b').zfill(64),
            "blue": bin(int(str(imagehash.dhash(blue)), 16)).lstrip('0b').zfill(64),
        }

    @classmethod
    def get_default_encoder(cls):
        return DhashEncoder()
