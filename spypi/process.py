import io
import logging

import cv2
import requests

from spypi.camera import Camera
from spypi.error import ImageReadException, ArducamException
from spypi.utils import show_image


class Connector:

    def __init__(self, config):
        self.logger = logging.getLogger("connector")
        self.host = config['host']
        self.max_retries = config['max_retries']
        self.name = config['name']
        self.timeout = config['timeout']
        self.url = "{0}/cameras/{1}/update".format(self.host, self.name)

    def send_image(self, image):

        image_metadata = {'Test-Header': 5}
        header = {'Metadata': str(image_metadata)}
        a_numpy = io.BytesIO(cv2.imencode('.jpg', image)[1])
        try:
            r = requests.post(url=self.url, files=dict(file=a_numpy), headers=header, timeout=self.timeout)
        except Exception as e:
            self.logger.error(e)


class ImageProcessor():

    def __init__(self, config):
        self.config = config
        self.camera = Camera.create(config['device'])
        self.logger = logging.getLogger("processor")
        self.connector = Connector(config['connection'])

    def run(self):
        while True:
            try:
                image = self.camera.get_next_image()
                if image is not None:
                     self.connector.send_image(image)
            except (ImageReadException, ArducamException) as e:
                self.logger.warning("Bad image read: {}".format(e))


class ImagePlayer():
    def __init__(self, config):
        self.logger = logging.getLogger("reader")
        self.camera = Camera.create(config['device'])

    def run(self):
        while True:
            try:
                image = self.camera.get_next_image()
                if image is not None:
                    show_image(image)
            except (ImageReadException, ArducamException) as e:
                self.logger.warning("Bad image read: {}".format(e))
