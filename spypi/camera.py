import json
import logging
import threading
import time

import ArducamSDK

from spypi.ImageConvert import convert_image
from spypi.error import CameraConfigurationException, ImageCaptureException, USBCameraTaskError, ImageReadException
from spypi.resources import get_resource
from spypi.utils import show_image


class Camera():

    def __init__(self, config):
        self.camera_type = config['camera']
        self.dev_id = config['device_id']
        self.frame_width = config['frame_width']
        self.frame_height = config['frame_height']
        self.start_delay = config['start_delay']
        self.init_delay = config['init_delay']
        self.stream = None

    @classmethod
    def create(cls, config):
        cam = config['camera']

        # if is_windows() and not cam == 'usb':
        #     raise EnvironmentError(
        #         "Cannot use type '{}' on windows - use USB instead.".format(cam))

        if cam == 'arducam':
            return ArduCam(config)
        elif cam == 'picam':
            return PiCam(config)
        elif cam == 'usb':
            return UsbCam(config)

        raise ValueError("Unknown camera type: {}".format(cam))

    def connect(self):
        pass

    def start(self):
        pass

    def get_next_image(self):
        pass


class PiCam(Camera):

    def __init__(self, config):
        super(PiCam, self).__init__(config)

    def connect(self):
        from imutils.video import VideoStream
        self.stream = VideoStream(
            src=self.dev_id,
            usePiCamera=True,
            resolution=(self.frame_width, self.frame_height),
            framerate=5
        )


class UsbCam(Camera):

    def __init__(self, config):
        super(UsbCam, self).__init__(config)

    def connect(self):
        from imutils.video import WebcamVideoStream
        self.stream = WebcamVideoStream(src=self.dev_id)


class ArduCam(Camera):

    def __init__(self, config):
        super(ArduCam, self).__init__(config)

        self.logger = logging.getLogger("arducam")
        self.register_config_path = config['arducam_registers'] or get_resource('default_registers.json')
        self.usb_version = None
        self.register_config = {}
        self.cam_config = {}
        self.handle = {}
        self.running = False
        self.color_mode = None
        self.save_flag = False
        self.save_raw = False
        self.handle = {}
        self.width = 0
        self.height = 0

        with open(self.register_config_path, 'r') as f:
            self.register_config = json.load(f)

        self.configure()
        self.set_mode()

        self.logger.info("Start arducam capture thread")
        start_code = ArducamSDK.Py_ArduCam_beginCaptureImage(self.handle)
        if start_code != 0:
            raise ImageCaptureException("Error starting capture thread, code: {}".format(start_code))
        self.logger.debug("Thread started")

    def connect_cam(self):

        self.logger.info("Beginning banana scan... ")
        ArducamSDK.Py_ArduCam_scan()

        ret = -1
        for i in range(3):
            time.sleep(5)
            ret, self.handle, rtn_cfg = ArducamSDK.Py_ArduCam_open(self.cam_config, self.dev_id)
            if ret == 0:
                self.usb_version = rtn_cfg['usbType']
                return
        raise AssertionError("Failed to connect to camera - error code: {}".format(ret))

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

    def set_mode(self):
        r = ArducamSDK.Py_ArduCam_setMode(self.handle, ArducamSDK.CONTINUOUS_MODE)
        if r != 0:
            raise AssertionError("Failed to set mode: {}".format(r))

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

    def capture(self):
            try:
                rtn_val = ArducamSDK.Py_ArduCam_captureImage(self.handle)
                if rtn_val > 255:
                    if rtn_val == ArducamSDK.USB_CAMERA_USB_TASK_ERROR:
                        raise USBCameraTaskError("USB task error: {}".format(rtn_val))
                    raise ImageCaptureException("Error capture image, rtn_val: ".format(rtn_val))
                time.sleep(0.005)
            except ImageCaptureException as e:
                self.logger.warning("Non critical error capturing image: {}".format(str(e)))

    def get_next_image(self):

        self.capture()
        if ArducamSDK.Py_ArduCam_availableImage(self.handle):
            rtn_val, data, rtn_cfg = ArducamSDK.Py_ArduCam_readImage(self.handle)
            datasize = rtn_cfg['u32Size']

            if datasize == 0 or rtn_val != 0:
                raise ImageReadException("Bad image read: datasize: {0}, code: {1}".format(datasize, rtn_val))
            ArducamSDK.Py_ArduCam_del(self.handle)
            return convert_image(data, rtn_cfg, self.color_mode)
        else:
            time.sleep(0.001)


class FrameViewer(threading.Thread):
    def __init__(self, cam):
        super().__init__()
        self.logger = logging.getLogger("reader")
        while True:
            try:
                image = cam.get_next_image()
                if image is not None:
                    show_image(image)
            except ImageReadException as e:
                self.logger.warning("Bad image read: {}".format(e))


