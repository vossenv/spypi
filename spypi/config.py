import os
from collections import Mapping
from copy import deepcopy

import yaml
from schema import Schema, Optional

from spypi.resources import get_resource

with open(get_resource('config_defaults.yaml')) as f:
    CONFIG_DEFAULTS = yaml.safe_load(f)


def config_schema() -> Schema:
    from schema import And, Or
    return Schema({
        'device': {
            'camera': Or('picam', 'arducam', 'usb', 'picam-direct'),
            'device_id': int,
            'frame_size': [int, int],
            'init_delay': Or(float, int),
            'init_retry': Or(float, int),
            'arducam_registers': Or(None, And(str, len)),
            'max_error_rate': Or(float, int),
            'cam_rotate': Or(0, 90, 180, 270),
            'codec': Or('h264'),
            'annotation_scale': int,
        },
        Optional('connection'): {
            'name': And(str, len),
            'host': And(str, len),
            'timeout': int,
        },
        Optional('processing'): {
            'target_video_framerate': Or(int, float),
            'target_web_framerate': Or(int, float),
            'video_fr_pid': Or(None, [Or(int, float), Or(int, float),
                                      Or(int, float), Or(int, float), Or(int, float),  Or(int, float)]),
            'web_fr_pid': Or(None, [Or(int, float), Or(int, float),
                                      Or(int, float), Or(int, float), Or(int, float),  Or(int, float)]),
            'show_fps': Or(None, bool),
            'recording_directory': Or(None, And(str, len)),
            'record_video': Or(None, bool),
            'send_video': Or(None, bool),
            'send_images': Or(None, bool),
            'crop': [int, int, int, int],
            'video_filesize': Or(float, int),
            'rotation': Or(float, int),
            'image_size': Or(None, [int, int]),
            'data_bar_web': [Or(float, int), int],
            'data_bar_video': [Or(float, int), int],
        },
        Optional('logging'): {
            'level': Or('info', 'debug', 'INFO', 'DEBUG'),
            'filename': Or(None, And(str, len)),
            'log_stdout': Or(None, bool),
            'log_metrics': Or(None, bool),
            'log_extra_info': Or(None, bool),
            'ignore_warnings': Or(None, bool),
        }
    })


def load_config(path):
    with open(path) as f:
        cfg = yaml.safe_load(f) or {}
    cfgm = merge_dict(CONFIG_DEFAULTS, cfg, True)

    path = cfgm['logging']['filename']
    cfgm['logging']['filename'] = os.path.abspath(path)

    path = cfgm['processing']['recording_directory']
    cfgm['processing']['recording_directory'] = os.path.abspath(path)

    path = cfgm['device']['arducam_registers']
    if path is not None:
        path = os.path.abspath(path)
        if not os.path.exists(path):
            raise FileNotFoundError("Cannot find {} ".format(path))
        cfg['device']['arducam_registers'] = path

    _validate(cfgm)
    return cfgm


def _validate(raw_config: dict):
    from schema import SchemaError
    try:
        config_schema().validate(raw_config)
    except SchemaError as e:
        raise ConfigValidationError(e.code) from e


def merge_dict(d1, d2, immutable=False):
    """
    # Combine dictionaries recursively
    # preserving the originals
    # assumes d1 and d2 dictionaries!!
    :param d1: original dictionary
    :param d2: update dictionary
    :return:
    """

    d1 = {} if d1 is None else d1
    d2 = {} if d2 is None else d2
    d1 = deepcopy(d1) if immutable else d1

    for k in d2:
        # if d1 and d2 have dict for k, then recurse
        # else assign the new value to d1[k]
        if (k in d1 and isinstance(d1[k], Mapping)
                and isinstance(d2[k], Mapping)):
            merge_dict(d1[k], d2[k])
        else:
            d1[k] = d2[k]
    return d1


class ConfigValidationError(Exception):
    def __init__(self, message):
        super(ConfigValidationError, self).__init__(message)
