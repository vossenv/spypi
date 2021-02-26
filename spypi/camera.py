import json
import logging
import os
import time
from collections import deque
from datetime import datetime

import ArducamSDK
import cv2
import numpy as np
import picamera
from picamera import PiCamera
from picamera.array import PiRGBAnalysis

from spypi.error import CameraConfigurationException, ArducamException
from spypi.lib.ImageConvert import convert_image
from spypi.resources import get_resource
from spypi.utils import MultiCounter, start_thread


class Camera():

    def __init__(self, config):
        self.camera_type = config['camera']
        self.dev_id = config['device_id']
        self.frame_size = tuple(config['frame_size'])
        self.init_delay = config['init_delay']
        self.init_retry = config['init_retry']
        self.max_error_rate = config['max_error_rate']
        self.cam_rotate = config['cam_rotate']
        self.codec = config['codec']
        self.extra_info = []
        self.framerate = 30
        self.logger = logging.getLogger(self.camera_type)
        self.log_metrics = False
        self.ignore_warnings = False
        self.log_extra_info = False
        self.images = deque(maxlen=5)
        self.image_counter = MultiCounter(50)

    @classmethod
    def create(cls, config):
        cam = config['camera']
        if cam == 'arducam':
            return ArduCam(config)
        elif cam == 'picam':
            return PiCam(config)
        elif cam == 'picam-direct':
            return PiCamDirect(config)
        elif cam == 'usb':
            return UsbCam(config)

        raise ValueError("Unknown camera type: {}".format(cam))

    def add_image(self, image):
        self.images.append(image)

        if self.image_counter.increment():
            # No need to fetch every single frame - it causes data errors
            if self.log_extra_info:
                self.extra_info = self.get_extra_label_info()

            # Just for metrics
            if self.log_metrics:
                self.logger.debug("Camera // framerate: {}".format(self.image_counter.get_rate(2)))

    def connect(self):
        pass

    def start(self):
        pass

    def stop(self):
        pass

    def restart(self):
        self.logger.info("Restarting camera")
        self.stop()
        self.start()
        self.logger.info("Restart done!")

    def next_image(self):
        if len(self.images) > 1:
            i = self.images[0].copy()
            return i

    def read_next_frame(self):
        pass

    def get_extra_label_info(self):
        return []


class PiCam(Camera):

    def __init__(self, config):
        super(PiCam, self).__init__(config)

        sz = 32 * round(self.frame_size[0] / 32), 16 * round(self.frame_size[1] / 16)

        if sz != self.frame_size:
            self.logger.warning("Specified frame size {0} is not divisiblee by 32x16. Rounding to {1}"
                                .format(self.frame_size, sz))
            self.frame_size = sz

    def connect(self):
        self.logger.info("Connecting to picamera")
        for i in range(self.init_retry):
            try:
                self.logger.info("Attempt: {}".format(i))
                self.cam = PiCamera(resolution=self.frame_size, framerate=self.framerate)
                self.cam.rotation = self.cam_rotate
                time.sleep(self.init_delay)
                return
            except Exception as e:
                self.logger.error("Failed to connect to camera: {}: {}".format(type(e), e))
                time.sleep(self.init_delay)
                if i == self.init_retry - 1:
                    raise

    def start(self):
        self.logger.info("Starting picam")
        self.connect()
        self.cam.start_recording(PiCamBuffer(self.cam, self.add_image), 'rgb')
        self.logger.info("Picam thread started")

    def stop(self):
        self.logger.info("Stopping picam")
        self.cam.stop_recording()
        self.cam.close()
        self.images.clear()
        self.logger.info("Picam stopped")


class PiCamDirect(PiCam):

    def __init__(self, config):
        super(PiCamDirect, self).__init__(config)
        self.vstream = None
        self.capture_image = False

    def start(self):
        self.logger.info("Starting picam")
        self.connect()
        start_thread(self.record)
        if self.capture_image:
            start_thread(self.capture_thread)

        self.logger.info("Picam thread started")

    def get_blank_image(self):
        return np.empty((self.frame_size[1], self.frame_size[0], 3), dtype=np.uint8)

    def capture_thread(self):
        self.cam.annotate_background = picamera.Color('black')
        self.cam.annotate_text_size = 60
        while True:
            self.cam.annotate_text = datetime.now().strftime("%Y-%m-%d: %H:%M:%S:%f")[:-5]
            image = self.get_blank_image()
            self.cam.capture(image, 'rgb', use_video_port=True)
            image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            self.add_image(image)
            time.sleep(0.13)

    def new_file(self):
        return self.vstream.get_filename(extension=self.codec)

    def record(self):
        data_rate = MultiCounter(10)
        sizes = deque(maxlen=7)
        cx = 0
        while self.vstream is None:
            self.logger.info("wait for video stream")
            time.sleep(0.5)
        self.logger.info("Stream ready! Start capture")

        filename = self.new_file()
        self.cam.start_recording(filename, format=self.codec)
        self.logger.info("Recording started")

        while True:
            self.cam.wait_recording(5)
            disk_size = self.vstream.get_filesize(filename)
            if round(disk_size) >= self.vstream.max_file_size:
                if self.log_metrics:
                    cx += 1
                    data_rate.increment()
                    sizes.append(disk_size)
                    self.logger.debug("Data rate: {0} MB/min // count: {1}"
                                      .format(round(data_rate.get_rate() * 60 * sum(sizes) / len(sizes), 8), cx))
                old_filename = filename
                filename = self.new_file()
                self.logger.debug(
                    "Max size exceeded ({0}). Start new file: {1}".format(disk_size, filename))
                self.cam.split_recording(filename)
                os.rename(old_filename, old_filename.replace("LOCKED-", ""))


class PiCamBuffer(PiRGBAnalysis):
    def __init__(self, camera, handler):
        super(PiCamBuffer, self).__init__(camera)
        self.handler = handler

    def analyze(self, image):
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        self.handler(image)


class UsbCam(Camera):

    def __init__(self, config):
        super(UsbCam, self).__init__(config)

    def connect(self):
        from imutils.video import WebcamVideoStream
        self.stream = WebcamVideoStream(src=self.dev_id)


class ArduCam(Camera):

    def __init__(self, config):
        super(ArduCam, self).__init__(config)

        self.register_config_path = config['arducam_registers'] or get_resource('default_registers.json')
        self.usb_version = None
        self.register_config = {}
        self.cam_config = {}
        self.handle = {}
        self.valid = False
        self.color_mode = None
        self.save_flag = False
        self.save_raw = False
        self.handle = {}
        self.first = True
        self.width = 0
        self.height = 0
        self.field_index = 0
        self.running = False
        self.error_counter = MultiCounter()
        self.data_fields = {
            'TIME': 0,
            'ISO': 0,
            'LUM1': 0,
            'LUM2': 0,
        }

        with open(self.register_config_path, 'r') as f:
            self.register_config = json.load(f)

    def read_frames(self):
        while True and self.running:
            try:
                image = self.read_next_frame()
                if image is not None:
                    self.add_image(image)
            except ArducamException as e:
                self.error_counter.increment()
                if self.max_error_rate < self.error_counter.get_rate():
                    break
                if self.ignore_warnings and isinstance(e, ArducamException) and e.code == 65316:
                    pass
                else:
                    self.logger.warning(e)
            except Exception as e:
                self.logger.error("Unknown error encountered: {}".format(e))
                return

        self.logger.info("Resetting due to errors")
        self.restart()

    def start(self, full=True):
        self.logger.info("Start arducam capture thread")
        self.handle = {}
        if full:
            self.configure()
        else:
            self.connect_cam()
        self.running = True
        start_code = ArducamSDK.Py_ArduCam_beginCaptureImage(self.handle)
        if start_code != 0:
            raise ArducamException("Error starting capture thread", code=start_code)
        start_thread(self.read_frames)
        self.extra_info = self.get_extra_label_info()
        self.logger.info("Arducam thread started")

    def stop(self):
        self.logger.info("Stopping arducam")
        self.running = False
        ArducamSDK.Py_ArduCam_del(self.handle)
        ArducamSDK.Py_ArduCam_flush(self.handle)
        ArducamSDK.Py_ArduCam_endCaptureImage(self.handle)
        ArducamSDK.Py_ArduCam_close(self.handle)
        self.images.clear()
        self.logger.info("Arducam stopped")

    def restart(self):
        self.logger.info("Restarting camera")
        self.stop()
        self.start(full=False)
        self.logger.info("Restart done!")

    def start_capture(self):
        self.logger.info("Start arducam capture thread")
        start_code = ArducamSDK.Py_ArduCam_beginCaptureImage(self.handle)
        if start_code != 0:
            raise ArducamException("Error starting capture thread", code=start_code)
        self.logger.debug("Thread started")

    def connect_cam(self):
        code = -1
        self.logger.info("Connecting to arducam")
        for i in range(self.init_retry):
            self.logger.info("Attempt: {}".format(i))
            code, self.handle, rtn_cfg = ArducamSDK.Py_ArduCam_autoopen(self.cam_config)
            if code == 0:
                self.usb_version = rtn_cfg['usbType']
                self.logger.info("Camera connected!")
                return
            time.sleep(self.init_delay)
        raise ArducamException("Failed to connect to camera", code=code)

    def configure(self):
        camera_parameter = self.register_config["camera_parameter"]
        self.width = int(camera_parameter["SIZE"][0])
        self.height = int(camera_parameter["SIZE"][1])
        BitWidth = camera_parameter["BIT_WIDTH"]
        ByteLength = 1
        if BitWidth > 8 and BitWidth <= 16:
            ByteLength = 2
            self.save_raw = True
        FmtMode = int(camera_parameter["FORMAT"][0])
        self.color_mode = (int)(camera_parameter["FORMAT"][1])

        I2CMode = camera_parameter["I2C_MODE"]
        I2cAddr = int(camera_parameter["I2C_ADDR"], 16)
        TransLvl = int(camera_parameter["TRANS_LVL"])
        self.cam_config = {
            "u32CameraType": 0x4D091031,
            "u32Width": self.width, "u32Height": self.height,
            "usbType": 0,
            "u8PixelBytes": ByteLength,
            "u16Vid": 0,
            "u32Size": 0,
            "u8PixelBits": BitWidth,
            "u32I2cAddr": I2cAddr,
            "emI2cMode": I2CMode,
            "emImageFmtMode": FmtMode,
            "u32TransLvl": TransLvl
        }

        self.connect_cam()
        self.configure_board("board_parameter")
        if self.usb_version == ArducamSDK.USB_1 or self.usb_version == ArducamSDK.USB_2:
            self.configure_board("board_parameter_dev2")
        if self.usb_version == ArducamSDK.USB_3:
            self.configure_board("board_parameter_dev3_inf3")
        if self.usb_version == ArducamSDK.USB_3_2:
            self.configure_board("board_parameter_dev3_inf2")

        self.write_regs("register_parameter")
        if self.usb_version == ArducamSDK.USB_3:
            self.write_regs("register_parameter_dev3_inf3")
        if self.usb_version == ArducamSDK.USB_3_2:
            self.write_regs("register_parameter_dev3_inf2")

        code = ArducamSDK.Py_ArduCam_setMode(self.handle, ArducamSDK.CONTINUOUS_MODE)
        if code != 0:
            raise ArducamException("Failed to set mode", code=code)

    def configure_board(self, reg_name):
        for r in self.get_register_value(reg_name):
            self.logger.debug("Writing register to cam {0}: {1}".format(self.dev_id, r))
            buffs = []
            command = r[0]
            value = r[1]
            index = r[2]
            buffsize = r[3]
            for j in range(0, len(r[4])):
                buffs.append(int(r[4][j], 16))
            ArducamSDK.Py_ArduCam_setboardConfig(self.handle, int(command, 16), int(value, 16), int(index, 16),
                                                 int(buffsize, 16), buffs)

    def get_register_value(self, reg_name):
        val = self.register_config.get(reg_name)
        if val is None:
            raise CameraConfigurationException("Specified parameter not in config json: {}".format(reg_name))
        return val

    def write_regs(self, reg_name):
        for r in self.get_register_value(reg_name):
            if r[0] == "DELAY":
                time.sleep(float(r[1]) / 1000)
                continue
            self.logger.debug("Writing register to cam {0}: {1}".format(self.dev_id, r))
            ArducamSDK.Py_ArduCam_writeSensorReg(self.handle, int(r[0], 16), int(r[1], 16))

    def read_next_frame(self):
        code = ArducamSDK.Py_ArduCam_captureImage(self.handle)
        if code > 255:
            raise ArducamException("Error capturing image", code=code)
        if ArducamSDK.Py_ArduCam_availableImage(self.handle):
            try:
                rtn_val, data, rtn_cfg = ArducamSDK.Py_ArduCam_readImage(self.handle)
                if rtn_val != 0 or rtn_cfg['u32Size'] == 0:
                    raise ArducamException("Bad image read! Datasize was {}".format(rtn_cfg['u32Size']), code=rtn_val)
                return convert_image(data, rtn_cfg, self.color_mode)
            finally:
                ArducamSDK.Py_ArduCam_del(self.handle)

    def get_extra_label_info(self):
        if self.data_fields['LUM2'] == 0:
            self.data_fields['LUM2'] = ArducamSDK.Py_ArduCam_readSensorReg(self.handle, int(12546))[1]
        if self.field_index == 0 or self.data_fields['TIME'] == 0:
            self.data_fields['TIME'] = ArducamSDK.Py_ArduCam_readSensorReg(self.handle, int(12644))[1]
        if self.field_index == 1 or self.data_fields['TIME'] == 0:
            self.data_fields['ISO'] = ArducamSDK.Py_ArduCam_readSensorReg(self.handle, int(12586))[1]
        if self.field_index == 2 or self.data_fields['TIME'] == 0:
            self.data_fields['LUM1'] = ArducamSDK.Py_ArduCam_readSensorReg(self.handle, int(12626))[1]

        self.field_index = self.field_index + 1 if self.field_index < 2 else 0

        return [("Time: {0} ISO: {1} LUM:{2}/{3}").format(
            self.data_fields['TIME'],
            self.data_fields['ISO'],
            self.data_fields['LUM1'],
            self.data_fields['LUM2'])]
