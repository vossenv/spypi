import io
import logging
import os
from datetime import datetime
from os.path import join

import cv2
import imutils
import requests


class ImageManip():

    @staticmethod
    def show(image):
        cv2.imshow("stream", image)
        cv2.waitKey(5)

    @staticmethod
    def compute_text_scale(text, box_w, pad=10):
        face = cv2.FONT_HERSHEY_DUPLEX

        longest = max(text, key=len)

        ((w1, _), _) = cv2.getTextSize(longest, face, 1, 1)
        ((w5, _), _) = cv2.getTextSize(longest, face, 5, 1)

        scale = 4 / (w5 - w1) * (box_w - 2 * pad)
        ((_, hf), _) = cv2.getTextSize(longest, face, scale, 1)

        return scale, hf

    @staticmethod
    def add_label(image, text, text_height, scale=1, color=(255, 255, 255), pad=10):
        y = image.shape[0] - pad

        for l in reversed(text):
            cv2.putText(image, l, (pad, y),
                        cv2.FONT_HERSHEY_DUPLEX, scale, color, 1, cv2.LINE_AA)
            y = y - (text_height + pad)
        return image

    @staticmethod
    def rotate(image, angle):
        if angle == 0:
            return image
        return imutils.rotate_bound(image, angle)

    @staticmethod
    def resize(image, dims):
        if not dims:
            return image
        if min(dims) <= 0:
            raise ValueError("Dimensions must be positive")
        return cv2.resize(image, (dims[0], dims[1]))

    @staticmethod
    def rectangle(image, dims, color=(0, 0, 0)):
        h, w, _ = image.shape
        cv2.rectangle(image, (0, h), (dims[0], h - dims[1]), color, -1)
        return image

    @staticmethod
    def crop(image, dims):
        if set(dims) == {0}:
            return image

        h, w, _ = image.shape
        top = round(dims[0] * 0.01 * h)
        left = round(dims[1] * 0.01 * w)
        bottom = round(dims[2] * 0.01 * h)
        right = round(dims[3] * 0.01 * w)

        if (w - left - right) <= 0 or (h - top - bottom) <= 0 or min(dims) < 0:
            raise ValueError("Crop dimensions exceed area or are negative")

        return image[top:h - bottom, left:w - right, :]


class VideoStream():

    def __init__(self, filename_prefix=None, directory=None, max_file_size=0, fps=20):
        self.filename_prefix = filename_prefix
        self.directory = directory or os.getcwd()
        self.frames = []
        self.size = 0
        self.disk_size = 0
        self.max_file_size = max_file_size
        self.file_count = 0
        self.logger = logging.getLogger("video")
        self.fps = fps
        self.writer = self.get_writer()
        self.output_counter = 0
        os.makedirs(self.directory, exist_ok=True)

    def get_filename(self):
        return join(self.directory, "LOCKED-{0}-{1}.avi".format(
            self.filename_prefix, datetime.now().strftime("%Y-%m-%d_%H-%M-%S")))

    def get_writer(self):
        self.filename = self.get_filename()
        return cv2.VideoWriter(self.filename, cv2.VideoWriter_fourcc('X', 'V', 'I', 'D'),
                               self.fps, (1280, 964))

    def add_frame(self, frame):
        self.writer.write(frame)
        if self.output_counter % 20 == 0:
            self.output_counter = 0
            self.disk_size = round(os.stat(self.filename).st_size * 1e-6, 2)
            if round(self.disk_size) >= self.max_file_size:
                self.start_new_file()
                self.logger.debug(
                    "Max size exceeded ({0}). Start new file: {1}".format(self.disk_size, self.filename))
        self.output_counter += 1

    def start_new_file(self):
        self.writer.release()
        os.rename(self.filename, self.filename.replace("LOCKED-", ""))
        self.writer = self.get_writer()


class Connector:

    def __init__(self, config):
        self.logger = logging.getLogger("connector")
        self.host = config['host']
        self.name = config['name']
        self.timeout = config['timeout']
        self.image_url = "{0}/cameras/{1}/update".format(self.host, self.name)
        self.video_url = "{0}/store".format(self.host)

    def send_image(self, image):
        try:
            file = io.BytesIO(cv2.imencode('.jpg', image)[1])
            self.send_files(url=self.image_url, files=dict(file=file), headers={})
        except Exception as e:
            self.logger.error(e)

    def send_video(self, path):
        try:
            filesize = round(os.stat(path).st_size * 1e-6, 2)
            headers = {'Size': str(filesize)}
            file = open(path, 'rb')
            self.logger.debug("Sending video {0} ({1} MB)".format(path, filesize))
            return self.send_files(url=self.video_url, files=dict(file=file), headers=headers)
        except Exception as e:
            self.logger.error(e)

    def send_files(self, url, files, headers=None, timeout=None):
        headers = headers or {}
        timeout = timeout or self.timeout
        r = requests.post(url=url, files=files, headers=headers, timeout=timeout)
        if r.status_code != 200:
            self.logger.error(r.content)
        return True


