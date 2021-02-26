import glob
import logging
import os
import time
from collections import deque
from datetime import datetime
from os.path import join

import cv2
from simple_pid import PID

from spypi.camera import Camera, PiCamDirect
from spypi.error import ImageReadException, ArducamException
from spypi.model import Connector, VideoStream, ImageManip as im
from spypi.utils import MultiCounter, start_thread

class ImageProcessor():

    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger("processor")
        self.camera = Camera.create(self.config['device'])
        processing_config = config['processing']
        self.video_stream = None
        self.connector = None
        self.text_scaling = {}
        self.record_video = processing_config['record_video']
        self.recording_directory = processing_config['recording_directory']
        self.send_images = processing_config['send_images']
        self.send_video = processing_config['send_video']
        self.video_filesize = processing_config['video_filesize']
        self.crop = processing_config['crop']
        self.rotation = processing_config['rotation']
        self.image_size = processing_config['image_size']
        self.data_bar_size = processing_config['data_bar_size']
        self.text_pad = processing_config['text_pad']
        self.target_web_framerate = processing_config['target_web_framerate']
        self.target_video_framerate = processing_config['target_video_framerate']
        self.show_fps = processing_config['show_fps']
        self.vid_pid = processing_config['video_fr_pid']
        self.web_pid = processing_config['web_fr_pid']
        self.log_metrics = self.config['logging']['log_metrics']
        self.ignore_warnings = self.camera.ignore_warnings = self.config['logging']['ignore_warnings']
        self.log_extra_info = self.camera.log_extra_info = self.config['logging']['log_extra_info']
        self.camera.log_metrics = self.log_metrics
        self.camera.capture_image = self.send_images
        self.camera.framerate = processing_config['target_video_framerate']

    def run(self):

        self.camera.start()

        if self.send_video or self.send_images:
            self.connector = Connector(self.config['connection'])

        if self.send_images:
            start_thread(
                self.stream_process,
                next=self.camera.next_image,
                transform=self.apply_stream_transforms,
                handle=self.connector.send_image,
                name="web",
                controller=self.get_pid(self.web_pid, self.target_web_framerate)
            )

        if self.record_video:

            if self.send_video:
                start_thread(self.send_directory_video)

            self.video_stream = self.camera.vstream = VideoStream(
                filename_prefix=self.config['connection']['name'],
                directory=self.recording_directory,
                max_file_size=self.video_filesize,
                resolution=self.camera.frame_size,
                fps=self.target_video_framerate,
                log_metrics = self.log_metrics,
            )

            if not isinstance(self.camera, PiCamDirect):
                start_thread(
                    self.stream_process,
                    next=self.camera.next_image,
                    transform=self.apply_video_transforms,
                    handle=self.video_stream.add_frame,
                    name="video",
                    controller=self.get_pid(self.vid_pid, self.target_video_framerate)
                )

    def get_pid(self, params, target):
        pid = PID(params[0], params[1], params[2], setpoint=target)
        pid.output_limits = (params[3], params[4])
        pid.interval = params[-1]
        return pid

    def stream_process(self, next, transform, handle, name, controller):
        delay = 0
        interval = controller.interval
        fc = MultiCounter(interval)
        fps_averages = deque(maxlen=interval)
        while True:
            try:
                img = next()
                if img is None:
                    continue
                f = fc.get_rate(2)
                fps_averages.append(f)
                if fc.increment():
                    fps = round(sum(fps_averages) / interval, 2)
                    delay = controller(fps)
                    if self.log_metrics:
                        self.logger.debug("{0} // framerate: {1} // sleeptime: {2}"
                                          .format(name.capitalize(), fps, round(delay, 4)))
                    cfps = self.camera.image_counter.get_rate(2)
                    if name == 'video' and not self.ignore_warnings and fps >= cfps:
                        self.logger.warning("Warning: stream-to-video fps ({0})> "
                                            "acquisition rate ({1})! Please adjust PID"
                                            .format(fps, cfps))
                handle(transform(img, f))
            except IndexError:
                pass
            finally:
                time.sleep(delay)

    def apply_stream_transforms(self, image, fps=None):
        image = im.crop(image, self.crop)
        image = im.resize(image, self.image_size)
        image = im.rotate(image, self.rotation, resize=False)
        return self.apply_data_bar(image, fps, 'web')

    def apply_video_transforms(self, image, fps=None):
        image = im.rotate(image, self.rotation)
        return self.apply_data_bar(image, fps, 'video')

    def apply_data_bar(self, image, fps, name):

        h, w, _ = image.shape
        time = datetime.now().strftime("%Y-%m-%d: %H:%M:%S:%f")[:-5]
        label = ["{0} @ {1:.2f} FPS".format(time, fps)] if self.show_fps else [time]
        if self.log_extra_info:
            label.extend(self.camera.extra_info)

        # Size of black rectangle (by % from CFG)
        bar_size = round(self.data_bar_size * 0.01 * w) if w > 300 else 100

        # Padding around text (shrinks to 2 for small frames)
        padding = self.text_pad if h > 300 else 2

        # Calculate the text scaling to fit width and height based on specified bar size.
        # Only run the first time since this value is fixed
        if not self.text_scaling.get(name):
            text_scale, text_height = im.compute_text_scale(label, bar_size, padding)
            vertical_space = text_height * len(label) + (len(label) - 1) * padding
            self.text_scaling[name] = [text_scale, text_height, vertical_space]

        text_scale = self.text_scaling[name][0]
        text_height = self.text_scaling[name][1]
        vspace = self.text_scaling[name][2]

        # Draw a box of proper height including between line padding
        image = im.rectangle(image, [w, vspace + 2 * padding], (0, 0, 0))

        # Add labels
        image = im.add_label(image, label, text_height, text_scale, (255, 255, 255), padding)
        return image

    def send_directory_video(self):
        pattern = join(self.recording_directory, "*.{}".format(self.camera.codec))
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
        self.processor.camera.start()

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
        self.processor.camera.start()

    def run(self):
        while True:
            try:
                image = self.processor.camera.read_next_frame()
                if image is not None:
                    im.show(self.processor.apply_stream_transforms(image))
            except (ImageReadException, ArducamException) as e:
                self.logger.warning("Bad image read: {}".format(e))
