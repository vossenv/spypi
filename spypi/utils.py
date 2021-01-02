import logging.config
import platform
import socket
import sys
import time

import cv2
import distro
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


def show_image(image):
    cv2.imshow("stream", image)
    cv2.waitKey(5)

def add_label(image, text):
    cv2.putText(image, str(text), (10, image.shape[0] - 10),
                cv2.FONT_HERSHEY_DUPLEX, 0.8, (255, 255, 255), 1, cv2.LINE_AA)


def process(image):
    image = cv2.medianBlur(image, 3)

    # if self.cam.rotation_angle != 0:
    #     image = imutils.rotate_bound(image, int(self.cam.rotation_angle))
    #
    # if counter % 10 == 0:
    #     fps = fps_counter.get_fps(10)
    # if self.cam.show_label:
    #     self.add_label(image, fps)
    # if self.cam.show_preview:
    # show_image(image)
    # if video is not None:
    #     video.add_frame(image)
    #     if counter != 0 and video.size >= self.cam.dump_size:
    #
    #        video.dump_async(fps)

