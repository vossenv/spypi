import glob
import importlib
import os
import platform
import shutil
import site
import sys
import tarfile
import time
import zipfile
from os.path import abspath, join
from pathlib import Path
from subprocess import Popen, PIPE, STDOUT
from urllib.request import urlretrieve

import distro

from spypi._version import __version__

# curl -L https://git.io/JIcrf | sudo **python3** -

PYTHON_REPO_URL = '192.168.50.187:1095'
OPENCV_LIB_URL = "https://github.com/vossenv/spypi/raw/main/external/opencv-4-4-0.zip"
ARDUCAM_LIB_URLS = [
    'https://github.com/ArduCAM/ArduCAM_USB_Camera_Shield/raw/master/RaspberryPi/Python/External_trigger_demo/ArducamSDK.so',
    'https://github.com/ArduCAM/ArduCAM_USB_Camera_Shield/raw/master/RaspberryPi/Python/External_trigger_demo/ArducamSDK.cpython-37m-arm-linux-gnueabihf.so'
]
APT_REQ_PACKAGES = [
    'libjpeg-dev',
    'libgtk-3-dev',
    'libavcodec-dev',
    'libavformat-dev',
    'libswscale-dev',
    'libjasper-dev',
    'libgtk2.0-dev',
    'screen',
    'libatlas-base-dev',
    'libharfbuzz-dev',
]


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


def reporthook(count, block_size, total_size):
    global start_time
    if count == 0:
        start_time = time.time()
        return
    duration = time.time() - start_time
    progress_size = int(count * block_size)
    speed = int(progress_size / (1024 * duration))
    percent = int(count * block_size * 100 / total_size)
    sys.stdout.write("\r...%d%%, %d MB, %d KB/s, %d seconds passed" %
                     (percent, progress_size / (1024 * 1024), speed, duration))
    sys.stdout.flush()


def download(url, outputdir):
    """
    Downloads the specfied URL, and puts it in dir.  If the file is a tar.gz, it is extracted
    and the original file is removed
    :param url: URL for target resource
    :param outputdir: Target directory for file
    :return:
    """

    outputdir = os.path.abspath(outputdir)
    path = Path(outputdir)
    path.mkdir(parents=True, exist_ok=True)
    filename = str(url.rpartition('/')[2])
    filepath = outputdir + os.sep + filename

    print("Downloading {0} to {1}".format(url, filepath))
    urlretrieve(url, filepath, reporthook)
    print("")

    # Extract if needed
    if filepath.endswith(".tar.gz"):
        print("\nExtracting tar.gz")
        tarfile.open(filepath).extractall(path=outputdir)
        os.remove(filepath)
    elif filepath.endswith(".zip"):
        print("\nExtracting zip file")
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
            p.stdin.write(b'y\n')
            print(line.rstrip('\n'))

        except TypeError:
            print(line.decode().rstrip('\n'))


def move_repl(src, dst):
    dst = abspath(join(dst, src.split(os.sep)[-1]))
    print("Moving: {0} to {1}".format(src, dst))
    shutil.move(src, dst)


def validate():
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


def install_opencv(libdir, usrlibdir):
    print("Downloading OpenCV libraries")
    download(OPENCV_LIB_URL, 'cv2')

    for file in glob.glob('cv2/cv2.cpython*.*'):
        move_repl(file, libdir)
    for file in glob.glob('cv2/**.*'):
        move_repl(file, usrlibdir)
    shutil.rmtree('cv2')


def install_arducam(libdir):
    print("Downloading Arducam libraries")
    for r in ARDUCAM_LIB_URLS:
        download(r, libdir)


def configure_dependencies():
    shell_exec('apt update')
    for m in APT_REQ_PACKAGES:
        print("->  Installing required package: " + m)
        shell_exec("apt install -y {}".format(m))


def write_pipconf():
    print("Writing pip.conf")
    conf = [
        "[global]",
        "extra-index-url = http://{}/".format(PYTHON_REPO_URL),
        "trusted-host = {}".format(PYTHON_REPO_URL.split(":")[0])
    ]

    with open("/etc/pip.conf", 'w') as f:
        f.writelines('\n'.join(conf))
    f.close()


def main():
    validate()
    sys.stdin = open('/dev/tty')
    libdir = site.getsitepackages()[0]
    usrlibdir = "/usr/local/lib"

    print("Current python library: " + libdir)
    print("Usr library dir: " + usrlibdir)

    install_opencv(libdir, usrlibdir)
    install_arducam(libdir)
    shell_exec('ldconfig -v')
    configure_dependencies()
    write_pipconf()

if __name__ == '__main__':
    main()
