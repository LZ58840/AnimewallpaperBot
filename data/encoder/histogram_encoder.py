import cv2
import numpy as np

from data.encoder.encoder import Encoder


class HistogramEncoder(Encoder):
    def __init__(self, bins=5):
        self.bins = bins

    def encode_image(self, image_obj):
        img_cv = cv2.cvtColor(np.array(image_obj), cv2.COLOR_RGB2BGR)

        return {
            "blue": np.concatenate(
                cv2.calcHist(
                    images=[img_cv],
                    channels=[0],
                    mask=None,
                    histSize=[self.bins],
                    ranges=[0, 256]
                )
            ).ravel().astype(int).tolist(),

            "green": np.concatenate(
                cv2.calcHist(
                    images=[img_cv],
                    channels=[1],
                    mask=None,
                    histSize=[self.bins],
                    ranges=[0, 256]
                )
            ).ravel().astype(int).tolist(),

            "red": np.concatenate(
                cv2.calcHist(
                    images=[img_cv],
                    channels=[2],
                    mask=None,
                    histSize=[self.bins],
                    ranges=[0, 256]
                )
            ).ravel().astype(int).tolist(),
        }

    @classmethod
    def get_default_encoder(cls, bins):
        return HistogramEncoder(bins)
