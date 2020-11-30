
import importlib
import os
import platform
import sys
import tarfile
import zipfile
from subprocess import Popen, PIPE, STDOUT
from urllib.request import urlretrieve

import distro

from spypi._version import __version__


libraries = [
    'https://github.com/ArduCAM/ArduCAM_USB_Camera_Shield/raw/master/'
    'RaspberryPi/Python/External_trigger_demo/ArducamSDK.so',
    'https://github.com/ArduCAM/ArduCAM_USB_Camera_Shield/raw/'
    'master/RaspberryPi/Python/External_trigger_demo/ArducamSDK.cpython-37m-arm-linux-gnueabihf.so'
]

downloads = {

}


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


def download(url, outputdir):
    """
    Downloads the specfied URL, and puts it in dir.  If the file is a tar.gz, it is extracted
    and the original file is removed
    :param url: URL for target resource
    :param outputdir: Target directory for file
    :return:
    """

    filename = str(url.rpartition('/')[2])
    filepath = outputdir + os.sep + filename
    print("Downloading " + filename + " from " + url)
    urlretrieve(url, filepath)

    # Extract if needed
    if filepath.endswith(".tar.gz"):
        tarfile.open(filepath).extractall(path=outputdir)
        os.remove(filepath)
    elif filepath.endswith(".zip"):
        zipper = zipfile.ZipFile(filepath, 'r')
        zipper.extractall(outputdir)
        zipper.close()
        os.remove(filepath)


def check_module_import(module):
    try:
        importlib.import_module(module)
        return True
    except ImportError:
        return False


# Starts a shell process.  Inserts "y" key after command  to avoid hangups for shell prompts
def shell_exec(cmd):
    p = Popen(cmd.split(" "), stdout=PIPE, stdin=PIPE, stderr=STDOUT)
    for line in iter(p.stdout.readline, b''):
        try:
            print(line.rstrip('\n'))
        except TypeError:
            print(line.decode().rstrip('\n'))


def main():

    env = get_environment()
    if 'raspbian' not in env['os'].lower():
        print("This script is meant only for Raspbian")
        exit()

    if not env['python_version'].startswith("3.7"):
        print("Please run with python 3.7 only")
        exit()

    if os.geteuid() != 0:
        print("You must run this script as root: sudo python install.py...")
        exit()

    sys.stdin = open('/dev/tty')

    print()


if __name__ == '__main__':
    main()
