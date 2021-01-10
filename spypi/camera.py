import json
import logging
import threading
import time
from collections import deque

import ArducamSDK
from picamera import PiCamera

from spypi.error import CameraConfigurationException, ArducamException, ImageReadException
from spypi.lib.ImageConvert import convert_image
from spypi.resources import get_resource
from spypi.utils import FPSCounter, SimpleCounter


class Camera():

    def __init__(self, config):
        self.camera_type = config['camera']
        self.dev_id = config['device_id']
        self.frame_size = tuple(config['frame_size'])
        self.init_delay = config['init_delay']
        self.init_retry = config['init_retry']
        self.stream = None
        self.extra_info = []
        self.logger = logging.getLogger("camera")
        self.counter = FPSCounter()
        self.images = deque(maxlen=20)
        self.count = 0
        self.log_metrics = False
        self.ignore_warnings = False
        self.log_extra_info = True
        self.running = True

    @classmethod
    def create(cls, config):
        cam = config['camera']
        if cam == 'arducam':
            return ArduCam(config)
        elif cam == 'picam':
            return ImUPiCam(config)
        elif cam == 'usb':
            return UsbCam(config)

        raise ValueError("Unknown camera type: {}".format(cam))

    def read_frames(self):
        cc = SimpleCounter(50)
        while True and self.running:
            if 75 < cc.get_rate() < 150:
                break
            try:
                image = self.read_next_frame()
                if image is not None:
                    # add images to respective deques for processing ASYNC
                    self.images.append(image)

                    # No need to fetch every single frame - it causes data errors
                    if self.log_extra_info and self.count % 300 == 0:
                        self.extra_info = self.get_extra_label_info()

                    # Just for metrics
                    if self.log_metrics and self.count % 500 == 0:
                        self.logger.debug("Capture rate: {} FPS".format(self.counter.get_fps()))
                        self.count = 0
                    self.count += 1

            except (ImageReadException, ArducamException) as e:
                cc.increment()
                self.logger.info("Error rate: {}".format(round(cc.get_rate(), 2)))
                self.logger.warning(e)
            except Exception as e:
                self.logger.error("Unknown error encountered: {}".format(e))

        self.logger.info("Resetting due to errors")
        self.reset()

    def connect(self):
        pass

    def start(self):
        pass

    def reset(self):
        pass

    def next_image(self):
        if len(self.images) > 5:
            return self.images[0]

    def read_next_frame(self):
        pass

    def get_extra_label_info(self):
        return []


class ImUPiCam(Camera):

    def __init__(self, config):
        super(ImUPiCam, self).__init__(config)

    def connect(self):
        from imutils.video import VideoStream
        self.stream = VideoStream(
            src=self.dev_id,
            usePiCamera=True,
            resolution=self.frame_size,
            framerate=5
        )


class PiCam(Camera):

    def __init__(self, config):
        super(PiCam, self).__init__(config)

    def connect(self):
        self.picam = PiCamera(resolution=self.frame_size)


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
        self.data_fields = {
            'TIME': 0,
            'ISO': 0,
            'LUM1': 0,
            'LUM2': 0,
        }

        with open(self.register_config_path, 'r') as f:
            self.register_config = json.load(f)

        self.start(full=True)
        self.logger.debug("Thread started")
        self.extra_info = self.get_extra_label_info()

    def start(self, full=False):
        self.handle = {}
        if full:
            self.configure()
        else:
            self.connect_cam()
        self.running = True
        self.logger.info("Start arducam capture thread")
        start_code = ArducamSDK.Py_ArduCam_beginCaptureImage(self.handle)
        if start_code != 0:
            raise ArducamException("Error starting capture thread", code=start_code)
        threading.Thread(target=self.read_frames).start()

    def reset(self, callback=None):
        self.running = False
        ArducamSDK.Py_ArduCam_del(self.handle)
        ArducamSDK.Py_ArduCam_endCaptureImage(self.handle)
        ArducamSDK.Py_ArduCam_close(self.handle)
        self.images.clear()
        self.start()

    def start_capture(self):
        self.logger.info("Start arducam capture thread")
        start_code = ArducamSDK.Py_ArduCam_beginCaptureImage(self.handle)
        if start_code != 0:
            raise ArducamException("Error starting capture thread", code=start_code)
        self.logger.debug("Thread started")

    def connect_cam(self):
        self.logger.info("Beginning banana scan... ")
        code, self.handle, rtn_cfg = ArducamSDK.Py_ArduCam_autoopen(self.cam_config)
        if code != 0:
            raise ArducamException("Failed to connect to camera", code=code)
        self.usb_version = rtn_cfg['usbType']
        self.logger.info("Camera connected!")

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
                # @rtn_val, data, rtn_cfg = ArducamSDK.Py_ArduCam_getSingleFrame(self.handle)
                if rtn_val != 0 or rtn_cfg['u32Size'] == 0:
                    raise ArducamException("Bad image read! Datasize was {}".format(rtn_cfg['u32Size']), code=rtn_val)
                self.counter.increment()
                return convert_image(data, rtn_cfg, self.color_mode)
            finally:
                ArducamSDK.Py_ArduCam_del(self.handle)
                ArducamSDK.Py_ArduCam_flush(self.handle)

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
