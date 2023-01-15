import os
from copy import deepcopy

from utils import get_default_settings


class ImageFactory:
    images_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "images")

    def get_placeholder_square_image(self):
        return os.path.join(self.images_path, "placeholder_150x150.png")

    def get_placeholder_horizontal_image(self):
        return os.path.join(self.images_path, "placeholder_256x144.png")

    def get_placeholder_horizontal_image_tall(self):
        return os.path.join(self.images_path, "placeholder_192x144.png")

    def get_placeholder_vertical_image(self):
        return os.path.join(self.images_path, "placeholder_144x256.png")

    def get_placeholder_vertical_image_wide(self):
        return os.path.join(self.images_path, "placeholder_144x192.png")

    def get_vertical_wallpaper(self):
        return os.path.join(self.images_path, "900x1600.png")

    def get_horizontal_wallpaper(self):
        return os.path.join(self.images_path, "1920x1080.png")


class SettingsFactory:
    default_settings = get_default_settings()

    def get_default_settings(self):
        return deepcopy(self.default_settings)

    def get_enabled_settings(self):
        enabled_settings = deepcopy(self.default_settings)
        enabled_settings['enabled'] = True
        return enabled_settings

    def get_resolution_any_enabled(self):
        rae_settings = deepcopy(self.default_settings)
        rae_settings['enabled'] = True
        rae_settings['ResolutionAny']['enabled'] = True
        return rae_settings

    def get_resolution_mismatch_enabled(self):
        rme_settings = deepcopy(self.default_settings)
        rme_settings['enabled'] = True
        rme_settings['ResolutionMismatch']['enabled'] = True
        return rme_settings

    def get_resolution_bad_enabled(self, h_str, v_str):
        rbe_settings = deepcopy(self.default_settings)
        rbe_settings['enabled'] = True
        rbe_settings['ResolutionBad']['enabled'] = True
        rbe_settings['ResolutionBad']['horizontal'] = h_str
        rbe_settings['ResolutionBad']['vertical'] = v_str
        return rbe_settings

    def get_aspect_ratio_bad_enabled(self, h_str, v_str):
        arbe_settings = deepcopy(self.default_settings)
        arbe_settings['enabled'] = True
        arbe_settings['AspectRatioBad']['enabled'] = True
        arbe_settings['AspectRatioBad']['horizontal'] = h_str
        arbe_settings['AspectRatioBad']['vertical'] = v_str
        return arbe_settings

    def get_rate_limit_any_enabled(self, intvl, freq, inc_deleted):
        rla_settings = deepcopy(self.default_settings)
        rla_settings['enabled'] = True
        rla_settings['RateLimitAny']['enabled'] = True
        rla_settings['RateLimitAny']['interval_hours'] = intvl
        rla_settings['RateLimitAny']['frequency'] = freq
        rla_settings['RateLimitAny']['incl_deleted'] = inc_deleted
        return rla_settings

    def get_all_enabled(self):
        all_settings = deepcopy(self.default_settings)
        all_settings['enabled'] = True
        all_settings['flairs']['Desktop'] = "horizontal"
        all_settings['flairs']['Mobile'] = "vertical"
        all_settings['flairs']['Collection'] = "horizontal, vertical"
        all_settings['flairs']['Other'] = "skip"
        all_settings['ResolutionAny']['enabled'] = True
        all_settings['ResolutionMismatch']['enabled'] = True
        all_settings['ResolutionBad']['enabled'] = True
        all_settings['ResolutionBad']['horizontal'] = "1920x1080"
        all_settings['ResolutionBad']['vertical'] = "900x1600"
        all_settings['AspectRatioBad']['enabled'] = True
        all_settings['AspectRatioBad']['horizontal'] = "16:10 to none"
        all_settings['AspectRatioBad']['vertical'] = "9:21 to 10:16"
        all_settings['enabled'] = True
        all_settings['interval_hours'] = 24
        all_settings['frequency'] = 4
        all_settings['inc_deleted'] = True
        return all_settings

