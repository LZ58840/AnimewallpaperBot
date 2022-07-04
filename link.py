import re

_imgur_type_regex = r"(^(http|https):\/\/)?(i\.)?imgur.com\/((?P<gallery>gallery\/)(?P<galleryid>\w+)|(?P<album>a\/)(?P<albumid>\w+)#?)?(?P<imgid>\w*)"
_reddit_type_regex = r"(^(http|https):\/\/)?(((i|preview)\.redd\.it\/)(?P<imgid>\w+\.\w+)|(www\.reddit\.com\/gallery\/)(?P<galleryid>\w+))"
_generic_type_regex = r"(https?:\/\/.*\.(?:png|jpg|jpeg))"

link_types = {
    "imgur": {
        "regex": _imgur_type_regex,
        "api_url": "https://api.imgur.com/3",
        "api_quantity": 1000,
        "api_refresh": 60
    },
    "reddit": {
        "regex": _reddit_type_regex,
        "api_url": "https://i.redd.it",
        "api_quantity": 1000,
        "api_refresh": 60
    },
    "generic": {
        "regex": _generic_type_regex,
        "api_url": "",
        "api_quantity": 1000,
        "api_refresh": 60
    }
}


def get_link_type(url):
    for link_type in link_types:
        if re.match(link_types[link_type]["regex"], url):
            return link_type
    return None
