
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

