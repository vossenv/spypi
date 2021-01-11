import logging.config
import platform
import socket
import sys
import time

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
    stream_log = config.get('log_stdout') or False

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
            for l in data['loggers'].keys():
                data['loggers'][l]['handlers'] = ['console']
        data['loggers']['']['level'] = level
        logging.config.dictConfig(data)

        if stream_log:
            sys.stderr = sys.stdout = StreamToLogger(logging.getLogger(), level)

        return logging.getLogger()

class FPSCounter():

    def __init__(self):
        self.count = 0
        self.time0 = time.perf_counter()
        self.time = self.time0

    def increment(self):
        self.count += 1
        self.time = time.perf_counter()
        if self.count > 100:
            self.count = 0
            self.time0 = time.perf_counter()
            self.time = self.time0

    def get_fps(self):
        elapsed = self.time - self.time0
        if elapsed == 0:
            return 0
        fps = round(self.count / elapsed, 2)
        return fps

class SimpleCounter():

    def __init__(self, size = 10):
        self.size = size
        self.reset()

    def increment(self):
        self.count += 1
        if self.count >= self.size:
            self.reset()
            return True

    def get_rate(self):
        try:
            delta = (time.perf_counter() - self.time)
            return self.count/delta
        except ZeroDivisionError:
            time.sleep(0.01)
            return self.get_rate()

    def reset(self):
        self.count = 0
        self.time = time.perf_counter()