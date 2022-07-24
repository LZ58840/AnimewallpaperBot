from json import JSONDecodeError

import requests
from requests.exceptions import MissingSchema

from data.extractor.extractor import Extractor


class ImgurExtractor(Extractor):
    _regex = r"(^(http|https):\/\/)?(i\.)?imgur.com\/((?P<gallery>gallery\/)(?P<galleryid>\w+)|(?P<album>a\/)(?P<albumid>\w+)#?)?(?P<imgid>\w*)"
    _url = "https://api.imgur.com/3"
    _headers = {"Authorization": f"Client-ID {'IMGUR_CLIENT_ID'}"}

    def extract_images(self, url, match=None):
        match = self.match_regex(url) if match is None else match
        if not match:
            return None

        request_url = None
        result = []
        img_id, album_id, gallery_id = None, None, None

        if (img_id := match.group('imgid')) not in [None, '', '0']:
            # Set to image endpoint
            request_url = f"{self._url}/image/{img_id}"

        elif (album_id := match.group('albumid')) is not None:
            # Set to album endpoint
            request_url = f"{self._url}/album/{album_id}/images"

        elif (gallery_id := match.group('galleryid')) is not None:
            # Set to gallery endpoint
            request_url = f"{self._url}/gallery/{gallery_id}/images"

        try:
            response = requests.get(url=request_url, headers=self._headers)

            if response.status_code != 200:
                return None

            response_json = response.json()

            if img_id not in [None, '', '0']:
                # Single image, just append URL
                result.append(response_json["data"]["extractor"])

            elif album_id is not None or gallery_id is not None:
                # Album or gallery of images
                if isinstance(response_json["data"], list):
                    # Album/gallery has more than one image
                    result.extend([image_json["extractor"] for image_json in response_json["data"]])

                else:
                    # Album/gallery has only one image
                    result.append(response_json["data"]["extractor"])

        except (JSONDecodeError, KeyError, MissingSchema):
            return None

        finally:
            return result

    @classmethod
    def get_default_extractor(cls):
        return cls()
