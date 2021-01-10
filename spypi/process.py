import asyncio
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
        self.use_asyncio = processing_config['use_asyncio']
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
        self.fps_enabled = processing_config['global_fps_enable']
        self.web_acq_delay = processing_config['web_acq_delay']
        self.video_acq_delay = processing_config['video_acq_delay']
        self.log_fps = self.config['logging']['log_fps']
        self.ignore_warnings = self.camera.ignore_warnings = self.config['logging']['ignore_warnings']
        self.log_extra_info = self.camera.log_extra_info = self.config['logging']['log_extra_info']
        self.camera.log_fps = self.log_fps and self.fps_enabled
        self.stream_process = self.sync_stream_process

    def run(self):

        tasks = []
        if self.use_asyncio:
            self.loop = asyncio.get_event_loop()
            self.stream_process = self.asio_stream_process

        if self.send_video or self.send_images:
            self.connector = Connector(self.config['connection'])

        if self.send_images:
            tasks.append(self.create_task(
                self.stream_process,
                next=self.camera.next_image,
                transform=self.apply_stream_transforms,
                handle=self.connector.send_image,
                name="Web",
                delay=self.web_acq_delay
            ))

        if self.record_video:
            self.video_stream = VideoStream(
                filename_prefix=self.config['connection']['name'],
                directory=self.recording_directory,
                max_file_size=self.video_filesize,
                resolution=self.config['processing']['xvid_size'],
                fps=self.framerate
            )

            tasks.append(self.create_task(
                self.stream_process,
                next=self.camera.next_video_frame,
                transform=self.apply_video_transforms,
                handle=self.video_stream.add_frame,
                name="Video",
                delay=self.video_acq_delay
            ))

            if self.send_video:
                threading.Thread(target=self.send_directory_video).start()

            if self.use_asyncio:
                self.loop.run_until_complete(asyncio.wait(tasks))
            else:
                [t.start() for t in tasks]

    def create_task(self, process_handle, **kwargs):
        if self.use_asyncio:
            return self.loop.create_task(process_handle(**kwargs))
        else:
            return threading.Thread(target=process_handle, args=kwargs.values())

    async def asio_stream_process(self, next, transform, handle, name, delay=0.0):
        interval = 500
        count = 0
        counter = FPSCounter()
        fps_queue = deque(maxlen=interval)
        while True:
            try:
                if self.fps_enabled:
                    f = counter.get_fps()
                    fps_queue.append(f)

                    if count % interval == 0 and self.log_fps:
                        fps = round(sum(fps_queue) / interval, 2)
                        self.logger.info("{0}: {1} frame avg fps: {2}".format(name, interval, fps))
                        self.count = 0
                    count += 1
                    counter.increment()
                    handle(transform(next(), f))
                else:
                    handle(transform(next()))
            except IndexError:
                time.sleep(0.001)
            finally:
                await asyncio.sleep(delay)

    def sync_stream_process(self, next, transform, handle, name, delay=0.0):
        interval = 500
        count = 0
        counter = FPSCounter()
        fps_queue = deque(maxlen=interval)
        while True:
            try:
                if self.fps_enabled:
                    f = counter.get_fps()
                    fps_queue.append(f)

                    if count % interval == 0 and self.log_fps:
                        fps = round(sum(fps_queue) / interval, 2)
                        self.logger.info("{0}: {1} frame avg fps: {2}".format(name, interval, fps))
                        self.count = 0
                    count += 1
                    counter.increment()
                    handle(transform(next(), f))
                else:
                    handle(transform(next()))
            except IndexError:
                time.sleep(0.001)
            finally:
                time.sleep(delay)

    def apply_stream_transforms(self, image, fps=None):
        image = im.crop(image, self.crop)
        image = im.resize(image, self.image_size)
        image = im.rotate(image, self.rotation)
        return self.apply_data_bar(image, fps)

    def apply_video_transforms(self, image, fps=None):
        image = im.rotate(image, self.rotation)
        return self.apply_data_bar(image, fps)

    def apply_data_bar(self, image, fps):

        h, w, _ = image.shape
        time = datetime.now().strftime("%Y-%m-%d: %H:%M:%S:%f")[:-5]
        label = ["{0} @ {1:.2f} FPS".format(time, fps)] if self.fps_enabled else [time]
        if self.log_extra_info:
            label.extend(self.camera.extra_info)

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


class ImageWriter():
    def __init__(self, config):
        self.logger = logging.getLogger("reader")
        self.processor = ImageProcessor(config)

    def write_images(self, number):
        i = 0
        while i < number:
            try:
                image = self.processor.camera.read_next_frame()
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
                image = self.processor.camera.read_next_frame()
                if image is not None:
                    im.show(self.processor.apply_stream_transforms(image))
            except (ImageReadException, ArducamException) as e:
                self.logger.warning("Bad image read: {}".format(e))
