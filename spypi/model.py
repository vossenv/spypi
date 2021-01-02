import logging
import os
import threading
import time
from datetime import datetime
from os.path import join

import cv2


class VideoStream():

    def __init__(self, filename_prefix=None, directory=None, max_file_size=0):
        self.filename_prefix = filename_prefix
        self.directory = directory or os.getcwd()
        self.frames = []
        self.size = 0
        self.disk_size = 0
        self.max_file_size = max_file_size
        self.file_count = 0
        self.logger = logging.getLogger("video")
        self.fps_counter = FPSCounter()
        self.writer = None
        os.makedirs(self.directory, exist_ok=True)

    def get_filename(self):
        return join(self.directory, "{0}-{1}.avi.locked".format(
            self.filename_prefix, datetime.now().strftime("%Y-%m-%d_%H-%M-%S")))

    def get_writer(self):
        self.current_filename = self.get_filename()
        return cv2.VideoWriter(
            self.current_filename,
            cv2.VideoWriter_fourcc('X', 'V', 'I', 'D'),
            self.fps_counter.get_fps(),
            (1280, 964)
        )

    def add_frame(self, frame):
        self.frames.append(frame)
        if len(self.frames) > 200:
            self.dump_async()

    def dump_async(self):
        self.dump_buffer()
        # dt = threading.Thread(target=self.dump_buffer)
        # dt.start()

    def dump_buffer(self):
        if self.writer is None:
            self.writer = self.get_writer()
        dump = self.frames.copy()
        self.frames = []
        for f in dump:
            self.writer.write(f)
        self.disk_size = round(os.stat(self.current_filename).st_size * 1e-6, 2)
        self.writer.release()
        self.logger.info("Finished dump -> size: {} MB".format(self.disk_size))
        if self.disk_size >= self.max_file_size:
            self.start_new_file()
            self.logger.info("Max file size of {0} MB exceeded. "
                             "Beginning new file: {1}".format(self.max_file_size, self.current_filename))

    def start_new_file(self):
        self.close()
        os.rename(self.current_filename, self.current_filename.rstrip(".locked"))
        self.writer = self.get_writer()

    def close(self):
        self.writer.release()


class FPSCounter():

    def __init__(self):
        self.time = 0

    def start(self):
        self.time = time.perf_counter()
        return self

    def get_fps(self):
        return 20

        # t = time.perf_counter()
        # fps = round(frames / (t - self.time), 2)
        # self.time = t
        # return fps
