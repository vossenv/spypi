import glob
import logging
import os
import threading
import time
from collections import deque
from datetime import datetime
from os.path import join

import cv2

from spypi.camera import Camera
from spypi.error import ImageReadException, ArducamException
from spypi.model import Connector, VideoStream, ImageManip as im
from spypi.utils import FPSCounter


class ImageProcessor():

    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger("processor")
        self.camera = Camera.create(self.config['device'])
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
        self.count = 0
        self.extra_info = []
        self.images = deque(maxlen=20)
        self.video = deque(maxlen=20)

    def run(self):

        if self.send_images:
            self.connector = Connector(self.config['connection'])

        if self.record_video:
            self.video_stream = VideoStream(
                filename_prefix=self.config['connection']['name'],
                directory=self.recording_directory,
                max_file_size=self.video_filesize,
                fps=self.framerate
            )

        if self.send_images:
            ImageStreamHandler(
                self.images,
                self.apply_stream_transforms,
                self.connector.send_image
            ).start()

        if self.video_stream:
            ImageStreamHandler(
                self.video,
                self.apply_video_transforms,
                self.video_stream.add_frame
            ).start()

        if self.video_stream and self.send_video:
            threading.Thread(target=self.send_directory_video).start()

        while True:
            try:
                image = self.camera.get_next_image()
                if image is not None:

                    # add images to respective deques for processing ASYNC
                    self.images.append(image)
                    self.video.append(image)

                    # No need to fetch every single frame - it causes data errors
                    if self.count % 20 == 0:
                        self.extra_info = self.camera.get_extra_label_info()

                    # Just for metrics
                    if self.count % 500 == 0:
                        self.logger.debug("Capture rate: {} FPS".format(self.camera.counter.get_fps()))
                        self.count = 0
                    self.count += 1

            except (ImageReadException, ArducamException) as e:
                self.logger.warning(e)
            except Exception as e:
                self.logger.error("Unknown error encountered: {}".format(e))

    def apply_stream_transforms(self, image, fps=0):
        image = im.rotate(image, self.rotation)
        image = im.crop(image, self.crop)
        image = im.resize(image, self.image_size)
        return self.apply_data_bar(image, fps)

    def apply_video_transforms(self, image, fps=0):
        image = im.rotate(image, self.rotation)
        return self.apply_data_bar(image, fps)

    def apply_data_bar(self, image, fps):

        h, w, _ = image.shape
        time = [datetime.now().strftime("%Y-%m-%d: %H:%M:%S:%f")[:-5]]
        label = ["{0} @ {1} FPS ".format(time, fps)]
        label.extend(self.extra_info)

        # Size of black rectangle (by % from CFG)
        bar_size = round(self.data_bar_size * 0.01 * w) if w > 300 else 100

        # Padding around text (shrinks to 2 for small frames)
        padding = self.text_pad if h > 300 else 2

        # Calculate the text scaling to fit width and height based on specified bar size.
        # Only run the first time since this value is fixed
        if not self.text_scaling_set:
            self.text_scaling_set = True
            self.text_scale, self.text_height = im.compute_text_scale(label, bar_size, padding)
            self.vertical_space = self.text_height * len(label) + (len(label) - 1) * padding

        # Draw a box of proper height including between line padding
        image = im.rectangle(image, [w, self.vertical_space + 2 * padding], (0, 0, 0))

        # Add labels
        image = im.add_label(image, label, self.text_height, self.text_scale, (255, 255, 255), padding)
        return image

    def send_directory_video(self):
        pattern = join(self.recording_directory, "*.avi")
        while True:
            for file in glob.glob(pattern):
                if file.split(os.sep)[-1].startswith("LOCKED"):
                    continue
                result = self.connector.send_video(file)
                if result is True:
                    os.unlink(file)
            time.sleep(10)


class ImageStreamHandler(threading.Thread):

    def __init__(self, source, transform, handler):
        super().__init__()
        self.transform = transform
        self.handle = handler
        self.source = source
        self.counter = FPSCounter()

    def run(self):
        while True:
            try:
                i = self.source.pop()
                i = self.transform(i, self.counter.get_fps())
                self.handle(i)
                self.counter.increment()
            except IndexError:
                time.sleep(0.001)
                pass


class ImageWriter():
    def __init__(self, config):
        self.logger = logging.getLogger("reader")
        self.processor = ImageProcessor(config)

    def write_images(self, number):
        i = 0
        while i < number:
            try:
                image = self.processor.camera.get_next_image()
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
        self.processor = ImageProcessor(config)

    def run(self):
        while True:
            try:
                image = self.processor.camera.get_next_image()
                if image is not None:
                    im.show(self.processor.apply_stream_transforms(image))
            except (ImageReadException, ArducamException) as e:
                self.logger.warning("Bad image read: {}".format(e))
