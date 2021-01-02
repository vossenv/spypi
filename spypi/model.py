import logging
import os
import threading
from datetime import datetime
from os.path import join

import cv2


class VideoStream():

    def __init__(self, filename_prefix=None, directory=None, max_file_size=0, framerate=20):
        self.filename_prefix = filename_prefix
        self.directory = directory or os.getcwd()
        self.frames = []
        self.size = 0
        self.disk_size = 0
        self.max_file_size = max_file_size
        self.file_count = 0
        self.logger = logging.getLogger("video")
        self.framerate = framerate
        self.writer = None
        os.makedirs(self.directory, exist_ok=True)

    def get_filename(self):
        return join(self.directory, "LOCKED-{0}-{1}.avi".format(
            self.filename_prefix, datetime.now().strftime("%Y-%m-%d_%H-%M-%S")))

    def get_writer(self):
        self.current_filename = self.get_filename()
        return cv2.VideoWriter(
            self.current_filename,
            cv2.VideoWriter_fourcc('X', 'V', 'I', 'D'),
            self.framerate,
            (1280, 964)
        )

    def add_frame(self, frame):
        self.frames.append(frame)
        if len(self.frames) > 200:
            self.dump_async()

    def dump_async(self):
        dt = threading.Thread(target=self.dump_buffer)
        dt.start()

    def dump_buffer(self):
        if self.writer is None:
            self.writer = self.get_writer()
        dump = self.frames.copy()
        self.frames = []
        for f in dump:
            self.writer.write(f)
        self.disk_size = round(os.stat(self.current_filename).st_size * 1e-6, 2)
        self.logger.debug("Finished dump -> size: {} MB".format(self.disk_size))
        if round(self.disk_size) >= self.max_file_size:
            self.start_new_file()
            self.logger.debug(
                "Max file size of {0} MB exceeded ({1}). Beginning new file: {2}"
                    .format(self.max_file_size, self.disk_size, self.current_filename))

    def start_new_file(self):
        self.close()
        os.rename(self.current_filename, self.current_filename.replace("LOCKED-", ""))
        self.writer = self.get_writer()

    def close(self):
        self.writer.release()
