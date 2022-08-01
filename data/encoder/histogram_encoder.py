import cv2
import numpy as np

from data.encoder.encoder import Encoder


class HistogramEncoder(Encoder):
    def __init__(self, bins=5):
        self.bins = bins

    def encode_image(self, image_obj):
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

    @staticmethod
    def get_insert_sql():
        return "replace into `4histogram`(id,red_1,red_2,red_3,red_4,green_1,green_2,green_3,green_4,blue_1,blue_2,blue_3,blue_4) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"

    @classmethod
    def get_default_encoder(cls, bins):
        return HistogramEncoder(bins)
