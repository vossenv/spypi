import os
from collections import Mapping
from copy import deepcopy

import yaml
from schema import Schema, Optional

CONFIG_DEFAULTS = {
    'hardware': {
        'camera': 'picam',
        'device_id': 0,
        'frame_width': 640,
        'frame_height': 480,
        'start_delay': 2,
        'init_delay': 5,
        'arducam_registers': None
    },
    'streaming': {
        'name': 'default',
        'address': "http://192.168.50.139:9001",
        'crop': {
            'top': 0,
            'left': 0,
            'bottom': 0,
            'right': 0,
        },
    },
    'output': {
        'frame_width': 512,
        'frame_height': 384,
        'address': "http://192.168.50.139:9001",
        'timeout': 10,
        'max_retries': 5
    },
    'logging': {
        'level': 'info',
        'filename': None,
        'stream_log': False
    },

}


def config_schema() -> Schema:
    from schema import And, Or
    return Schema({
        'hardware': {
            'camera': Or('picam', 'arducam', 'usb'),
            'device_id': int,
            'frame_width': int,
            'frame_height': int,
            'start_delay': Or(float, int),
            'init_delay': Or(float, int),
            'arducam_registers': Or(None, And(str, len)),
        },
        Optional('streaming'): {
            'name': And(str, len),
            'address': And(str, len),
            'crop': {
                'top': Or(float, int),
                'left': Or(float, int),
                'bottom': Or(float, int),
                'right': Or(float, int)
            }
        },
        Optional('output'): {
            'frame_width': int,
            'frame_height': int,
            'address': And(str, len),
            'timeout': int,
            'max_retries': int
        },
        'logging': {
            'level': Or('info', 'debug', 'INFO', 'DEBUG'),
            'filename': Or(None, And(str, len)),
            'stream_log': Or(None, bool)
        }
    })


def load_config(path):
    with open(path) as f:
        cfg = yaml.safe_load(f) or {}
    cfgm = merge_dict(CONFIG_DEFAULTS, cfg, True)

    if not cfg.get('streaming'):
        cfgm.pop('streaming')

    if not cfg.get('output'):
        cfgm.pop('output')

    path = cfgm['logging']['filename']
    if path is not None:
        cfgm['logging']['filename'] = os.path.abspath(path)

    path = cfgm['hardware']['arducam_registers']
    if path is not None:
        path = os.path.abspath(path)
        if not os.path.exists(path):
            raise FileNotFoundError("Cannot find {} ".format(path))
        cfg['hardware']['arducam_registers'] = path

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
