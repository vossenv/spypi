import logging.config
import platform
import socket
import sys

import cv2
import distro
import imutils
import yaml

from spypi._version import __version__
from spypi.resources import get_resource


def is_windows():
    return platform.system().lower() == "windows"


def get_environment():
    env_os = platform.system()
    if env_os.lower() == "windows":
        env_os_version = platform.version()
    elif env_os.lower() == "linux":
        vers = distro.linux_distribution()
        env_os = vers[0]
        env_os_version = vers[1] + " " + vers[2]
    else:
        raise EnvironmentError("Unknown / unsupported platform: {}".format(env_os))
    return {
        'app_version': __version__,
        'python_version': platform.python_version(),
        'os': env_os,
        'os_version': env_os_version
    }


def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        ip = s.getsockname()[0]
    except:
        ip = '127.0.0.1'
    s.close()
    return str(ip)


class StreamToLogger(object):
    def __init__(self, logger, log_level):
        self.logger = logger
        self.log_level = logging.getLevelName(log_level)

    def write(self, message):
        for line in message.rstrip().splitlines():
            self.logger.log(self.log_level, line.rstrip())

    def flush(self): pass


def init_logger(config):
    level = config.get('level') or 'DEBUG'
    filename = config.get('filename') or None
    stream_log = config.get('stream_log') or False

    level = level.upper()
    with open(get_resource("logger_config.yaml")) as cfg:
        data = yaml.safe_load(cfg)
        data['formatters']['standard']['format'] = \
            data['formatters']['standard']['format'] \
                .replace('%(asctime)s ', '%(asctime)s [{}] '.format(get_ip()))
        if filename:
            data['handlers']['file']['filename'] = filename
        else:
            data['handlers'].pop('file')
            data['loggers']['']['handlers'] = ['console']
        data['loggers']['']['level'] = level
        logging.config.dictConfig(data)

        if stream_log:
            sys.stderr = sys.stdout = StreamToLogger(logging.getLogger(), level)

        return logging.getLogger()


class Image():

    def __init__(self, image):
        self.image = image

def show_image(image):
    cv2.imshow("stream", image)
    cv2.waitKey(5)


def compute_text_scale(text, box_h, box_w, pad=10):
    face = cv2.FONT_HERSHEY_DUPLEX
    lines = text.split("\n")
    longest = max(lines, key=len)

    delta = 0.1
    scale = delta

    while True:
        ((tw, th), _) = cv2.getTextSize(longest, face, scale, 1)
        if th >= box_h - 2 * pad:
            scale = scale - delta
            break
        if tw >= box_w - 2 * pad:
            scale = scale - delta
            break
        else:
            scale += delta

    ((tw, th), _) = cv2.getTextSize(longest, face, scale, 1)
    return scale, th * len(lines) + (len(lines) - 1) * pad


def add_label(image, text, scale=1, color=(255, 255, 255), pad=10):
    cv2.putText(image, text, (pad, image.shape[0] - pad),
                cv2.FONT_HERSHEY_DUPLEX, scale, color, 1, cv2.LINE_AA)
    return image


def rotate_image(image, angle):
    if angle == 0:
        return image
    return imutils.rotate_bound(image, angle)


def resize_image(image, dims):
    if not dims:
        return image
    if min(dims) <= 0:
        raise ValueError("Dimensions must be positive")
    return cv2.resize(image, (dims[0], dims[1]))


def draw_rectangle(image, dims, color=(0, 0, 0)):
    h, w, _ = image.shape
    cv2.rectangle(image, (0, h), (dims[0], h - dims[1]), color, -1)
    return image


def crop_image(image, dims):
    if set(dims) == {0}:
        return image

    h, w, _ = image.shape
    top = round(dims[0] * 0.01 * h)
    left = round(dims[1] * 0.01 * w)
    bottom = round(dims[2] * 0.01 * h)
    right = round(dims[3] * 0.01 * w)

    if (w - left - right) <= 0 or (h - top - bottom) <= 0 or min(dims) < 0:
        raise ValueError("Crop dimensions exceed area or are negative")

    return image[top:h - bottom, left:w - right, :]
