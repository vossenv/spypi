import io
import logging

import cv2
import os
import requests

from spypi.camera import Camera
from spypi.error import ImageReadException, ArducamException
from spypi.model import VideoStream
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
        self.logger = logging.getLogger("processor")
        self.camera = Camera.create(config['device'])
        self.connector = Connector(config['connection'])

        processing_config = config['processing']
        self.video_stream = None
        self.record_video = processing_config['record_video']
        self.recording_directory = processing_config['recording_directory']
        self.send_images = processing_config['send_images']
        self.send_video = processing_config['send_video']
        self.video_filesize = processing_config['video_filesize']
        self.image_crop = processing_config['image_crop']
        self.video_crop = processing_config['video_crop']
        self.rotation = processing_config['rotation']
        self.image_size = processing_config['image_size']
        self.framerate = processing_config['framerate']

        if self.record_video:
            self.video_stream = VideoStream(
                filename_prefix=self.connector.name,
                directory=self.recording_directory,
                max_file_size=self.video_filesize,
                framerate=self.framerate
            )

    def run(self):
        while True:
            try:
                image = self.camera.get_next_image()
                if image is not None:
                    if self.send_images:
                        self.connector.send_image(image)
                    if self.video_stream:
                        self.video_stream.add_frame(image)

            except (ImageReadException, ArducamException) as e:
                self.logger.warning("Bad image read: {}".format(e))


class ImageWriter():
    def __init__(self, config):
        self.logger = logging.getLogger("reader")
        self.camera = Camera.create(config['device'])

    def write_images(self, number):
        i = 0
        while i < number:
            try:
                image = self.camera.get_next_image()
                if image is not None:
                    filename = os.path.abspath("frame-{}.jpg".format(i + 1))
                    cv2.imwrite(filename, image)
                    self.logger.info("Wrote {}".format(filename))
                    i += 1
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
