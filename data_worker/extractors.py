import logging

from aiohttp import ContentTypeError
from aiohttp_retry import RetryClient
from asyncprawcore import Forbidden

IMGUR_REGEX_STR = r"(^(http|https):\/\/)?(i\.)?imgur.com\/(gallery\/(?P<gallery_id>\w+)|a\/(?P<album_id>\w+)#?)?(?P<image_id>\w*)"
REDDIT_REGEX_STR = r"(^(http|https):\/\/)?(((i|preview)\.redd\.it\/)(?P<image_id>\w+\.\w+)|(www\.reddit\.com\/gallery\/)(?P<gallery_id>\w+))"


async def extract_from_imgur_url(auth, image_id, album_id, gallery_id) -> list[str]:
    request_url = "https://api.imgur.com/3/"
    async with RetryClient(raise_for_status=False) as client:
        if image_id not in (None, '', '0'):
            request_url += f"image/{image_id}"
        elif album_id is not None:
            request_url += f"album/{album_id}/images"
        elif gallery_id is not None:
            request_url += f"gallery/{gallery_id}/images"
        async with client.request(method='GET', url=request_url, headers=auth) as response:
            if response.status != 200:
                logging.error(f"error getting {request_url} with {response.status}, skipping...")
                return []
            try:
                response_json = await response.json()
                if isinstance(response_json["data"], list):
                    return [image_json["link"] for image_json in response_json["data"]]
                return [response_json["data"]["link"]]
            except (ContentTypeError, KeyError):
                logging.error(f"error parsing {request_url}, skipping...")
                return []


async def extract_from_reddit_url(submission, image_id, gallery_id) -> list[str]:
    if image_id is not None:
        return [f"https://i.redd.it/{image_id}"]
    elif gallery_id is not None:
        try:
            return [
                f"https://i.redd.it/{item['media_id']}.{submission.media_metadata[item['media_id']]['m'].split('/')[1]}"
                for item in submission.gallery_data["items"]
            ]
        except (AttributeError, TypeError, Forbidden):
            return []
    return []
