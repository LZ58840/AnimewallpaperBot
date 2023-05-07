import math
import pickle
from collections import Counter

import cv2


FLANN_INDEX_KDTREE = 1  # way faster than 0
GROUP_TREES = 5
SHOWDOWN_TREES = 1
CHECKS = 50


def get_group_matcher(descriptor_rows):
    flann_params = dict(algorithm=FLANN_INDEX_KDTREE, trees=GROUP_TREES)
    search_params = dict(checks=CHECKS)
    flann_matcher = cv2.FlannBasedMatcher(flann_params, search_params)
    for descriptor_row in descriptor_rows:
        flann_matcher.add(pickle.loads(descriptor_row['sift']))
    flann_matcher.train()
    return flann_matcher


def get_showdown_matcher():
    flann_params = dict(algorithm=FLANN_INDEX_KDTREE, trees=SHOWDOWN_TREES)
    search_params = dict(checks=CHECKS)
    return cv2.FlannBasedMatcher(flann_params, search_params)


def sigmoid(x, b=0.5, o=20) -> float:
    return 1. / (1 + math.exp(-b * (x - o)))


def match_descriptors_to_group(descriptors_str, matcher, ratio=.7):
    descriptors = pickle.loads(descriptors_str)
    matches = matcher.knnMatch(descriptors, k=2)
    good_matches = [m.imgIdx for m, n in matches if m.distance < ratio * n.distance]
    matched_image_tally = Counter(good_matches)
    return matched_image_tally.items()


def match_descriptors_to_descriptors(query_descriptors_str, train_descriptors_str, matcher, ratio=.7):
    query_descriptors, train_descriptors = pickle.loads(query_descriptors_str), pickle.loads(train_descriptors_str)
    matches = matcher.knnMatch(query_descriptors, train_descriptors, k=2)
    return sum(1 for m, n in matches if m.distance < ratio * n.distance)
