
from os.path import dirname, realpath, join
import os
import sys

__name__ = dirname(__file__).split(os.sep)[-1]

def get_resource_dir():
    if getattr(sys, 'frozen', False):
        return join(sys._MEIPASS, __name__)
    else:
        return dirname(realpath(__file__))

def get_resource(name):
    path = join(get_resource_dir(), name)
    if not os.path.exists(path):
        raise FileNotFoundError("Error: " + path + " does not exist")
    return path

def get_environment():

    # shell_exec('pip3 install distro')
    #
    # import distro

    env_os = platform.system()
    if env_os.lower() == "windows":
        env_os_version = platform.version()
    elif env_os.lower() == "linux":
        env_os_version = platform.machine() + " " + env_os

        # vers = distro.linux_distribution()
        # env_os = vers[0]
        #env_os_version = vers[1] + " " + vers[2]
    else:
        raise EnvironmentError("Unknown / unsupported platform: {}".format(env_os))
    return {
        'app_version': __version__,
        'python_version': platform.python_version(),
        'os': env_os,
        'os_version': env_os_version
    }
