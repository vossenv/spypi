import io
import logging
import os
from datetime import datetime

import cv2
import requests

from spypi.camera import Camera
from spypi.error import ImageReadException, ArducamException
from spypi.model import VideoStream
from spypi.utils import show_image, crop_image, rotate_image, resize_image, draw_rectangle, add_label, \
    compute_text_scale


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
        self.logger = logging.getLogger("processor")

        processing_config = config['processing']
        self.video_stream = None
        self.connector = None
        self.text_scaling_set = None
        self.record_video = processing_config['record_video']
        self.recording_directory = processing_config['recording_directory']
        self.send_images = processing_config['send_images']
        self.send_video = processing_config['send_video']
        self.video_filesize = processing_config['video_filesize']
        self.crop = processing_config['crop']
        self.rotation = processing_config['rotation']
        self.image_size = processing_config['image_size']
        self.framerate = processing_config['framerate']
        self.data_bar_size = processing_config['data_bar_size']
        self.text_pad = processing_config['text_pad']

    def run(self):
        self.camera = Camera.create(self.config['device'])

        if self.send_images:
            self.connector = Connector(self.config['connection'])

        if self.record_video:
            self.video_stream = VideoStream(
                filename_prefix=self.config['connection']['name'],
                directory=self.recording_directory,
                max_file_size=self.video_filesize,
                framerate=self.framerate
            )

        while True:
            try:
                image = self.camera.get_next_image()
                if image is not None:
                    if self.send_images:
                        self.connector.send_image(self.apply_stream_transforms(image))
                    if self.video_stream:
                        self.video_stream.add_frame(self.apply_video_transforms(image))

            except (ImageReadException, ArducamException) as e:
                self.logger.warning("Bad image read: {}".format(e))

    def apply_stream_transforms(self, image):
        image = rotate_image(image, self.rotation)
        image = crop_image(image, self.crop)
        image = resize_image(image, self.image_size)
        return self.apply_data_bar(image)

    def apply_video_transforms(self, image):
        image = rotate_image(image, self.rotation)
        return self.apply_data_bar(image)

    def apply_data_bar(self, image):
        h, w, _ = image.shape
        label = ['this', 'is', 'a test', datetime.now().strftime("%Y-%m-%d: %H:%M:%S:%f")[:-5]]

        # Size of black rectangle (by % from CFG)
        bar_size = round(self.data_bar_size * 0.01 * w) if w > 300 else 100

        # Padding around text (shrinks to 2 for small frames)
        padding = self.text_pad if h > 300 else 2

        # Calculate the text scaling to fit width and height based on specified bar size.
        # Only run the first time since this value is fixed
        if not self.text_scaling_set:
            self.text_scaling_set = True
            self.text_scale, self.text_height = compute_text_scale(label, bar_size, padding)
            self.vertical_space = self.text_height*len(label) + (len(label) - 1)*padding

        # Draw a box of proper height including between line padding
        image = draw_rectangle(image, [w, self.vertical_space + 2 * padding], (0, 0, 0))

        # Add labels
        image = add_label(image, label, self.text_height, self.text_scale, (255, 255, 255), padding)

        return image


class ImageWriter():
    def __init__(self, config):
        self.logger = logging.getLogger("reader")
        self.camera = Camera.create(config['device'])
        self.processor = ImageProcessor(config)

    def write_images(self, number):
        i = 0
        while i < number:
            try:
                image = self.camera.get_next_image()
                if image is not None:
                    filename = os.path.abspath("frame-{}.jpg".format(i + 1))
                    cv2.imwrite(filename, self.processor.apply_stream_transforms(image))
                    self.logger.info("Wrote {}".format(filename))
                    i += 1
            except (ImageReadException, ArducamException) as e:
                self.logger.warning("Bad image read: {}".format(e))


class ImagePlayer():
    def __init__(self, config):
        self.logger = logging.getLogger("reader")
        self.camera = Camera.create(config['device'])
        self.processor = ImageProcessor(config)

    def run(self):
        while True:
            try:
                image = self.camera.get_next_image()
                if image is not None:
                    show_image(self.processor.apply_stream_transforms(image))

            except (ImageReadException, ArducamException) as e:
                self.logger.warning("Bad image read: {}".format(e))
