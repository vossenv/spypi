import io
import logging
import os
import threading
import time
from datetime import datetime
from os.path import join

import cv2
import imutils
import requests

from spypi.utils import is_windows


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
        self.async_dump = is_windows()
        self.output_counter = 0
        os.makedirs(self.directory, exist_ok=True)

        if self.async_dump:
            dumper = threading.Thread(target=self.dump_thread)
            dumper.start()

    def get_filename(self):
        return join(self.directory, "LOCKED-{0}-{1}.avi".format(
            self.filename_prefix, datetime.now().strftime("%Y-%m-%d_%H-%M-%S")))

    def get_writer(self):
        self.filename = self.get_filename()
        return cv2.VideoWriter(self.filename, cv2.VideoWriter_fourcc('X', 'V', 'I', 'D'),
                               self.fps, (1280, 964))

    def add_frame(self, frame):
        if self.async_dump:
            self.frames.append(frame)
        else:
            self.dump_frame(frame)

    def dump_thread(self):
        while True:
            try:
                self.dump_frame(self.frames.pop(0))
            except IndexError:
                time.sleep(0.1)

    def dump_frame(self, frame):
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

    # def post_files(self, *files):
    #     status = 0
    #     headers = {}
    #     for f in files:
    #
    #         if isinstance(f, tuple):
    #             headers['File-Destination'] = f[1]
    #             f = f[0]
    #
    #         filesize = "%0.3f MB" % round(os.path.getsize(os.path.abspath(f)) / 1000000.0, 4)
    #         headers['Size'] = filesize
    #
    #         for i in range(1, self.max_retries + 1):
    #             try:
    #                 reprint("Sending " + f + " (" + filesize + ") .... Attempt " + str(i) + "/" + str(self.max_retries))
    #                 r = requests.post(url=output_options['fileserver_address'] + "/store", headers=headers,
    #                                   files=dict(file=open(f, 'rb')), timeout=self.timeout)
    #                 reprint("Result: " + str(r.status_code) + ": " + str(r.content))
    #                 status += r.status_code
    #                 if status % 200 == 0:
    #                     reprint("Removing " + f)
    #                     self.remove_files(f)
    #                 break
    #             except Exception as e:
    #                 status = -1
    #             if i == self.max_retries: reprint("Max tries exceeded, aborting transfers... ")
    #             reprint("Status " + str(status))
    #             if status % 200 != 0:
    #                 reprint("Failed to complete upload: " + f + ". Size: " + filesize + ". Error: " + str(e))
    #
    #     return status
