class Encoder:
    def encode_image(self, image_obj):
        raise NotImplementedError

    @staticmethod
    def get_insert_sql():
        raise NotImplementedError

    @classmethod
    def get_default_encoder(cls, **kwargs):
        raise NotImplementedError
