import json
import logging
import time

from spypi.error import CameraConfigurationException
from spypi.resources import get_resource
from spypi.utils import is_windows


class Camera():

    def __init__(self, config):
        self.camera_type = config['camera']
        self.frame_width = config['frame_width']
        self.frame_height = config['frame_height']
        self.start_delay = config['start_delay']
        self.init_delay = config['init_delay']
        self.stream = None

    @classmethod
    def create(cls, config):
        cam = config['camera']

        if is_windows() and not cam == 'usb':
            raise EnvironmentError(
                "Cannot use type '{}' on windows - use USB instead.".format(cam))

        if cam == 'arducam':
            return ArduCam(config)
        elif cam == 'picam':
            return PiCam(config)
        elif cam == 'usb':
            return UsbCam(config)

        raise ValueError("Unknown camera type: {}".format(cam))

    def connect(self):
        pass


class PiCam(Camera):

    def __init__(self, config):
        super(PiCam, self).__init__(config)

    def connect(self):
        from imutils.video import VideoStream
        self.stream = VideoStream(
            src=0,
            usePiCamera=True,
            resolution=(self.frame_width, self.frame_height),
            framerate=5
        )


class UsbCam(Camera):

    def __init__(self, config):
        super(UsbCam, self).__init__(config)

    def connect(self):
        from imutils.video import WebcamVideoStream
        self.stream = WebcamVideoStream(src=0)


class ArduCam(Camera):
    import ArducamSDK

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
        self.dev_id = 0

        with open(self.register_config_path, 'r') as f:
            self.register_config = json.load(f)

        self.configure()
        self.set_mode()


    def connect_cam(self):

        self.logger.info("Beginning banana scan... ")
        self.ArducamSDK.Py_ArduCam_scan()

        ret = -1
        for i in range(3):
            time.sleep(5)
            ret, self.handle, rtn_cfg = self.ArducamSDK.Py_ArduCam_open(self.cam_config, self.dev_id)
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
        if self.usb_version == self.ArducamSDK.USB_1 or self.usb_version == self.ArducamSDK.USB_2:
            self.configure_board("board_parameter_dev2")
        if self.usb_version == self.ArducamSDK.USB_3:
            self.configure_board("board_parameter_dev3_inf3")
        if self.usb_version == self.ArducamSDK.USB_3_2:
            self.configure_board("board_parameter_dev3_inf2")

        self.write_regs("register_parameter")
        if self.usb_version == self.ArducamSDK.USB_3:
            self.write_regs("register_parameter_dev3_inf3")
        if self.usb_version == self.ArducamSDK.USB_3_2:
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
            self.ArducamSDK.Py_ArduCam_setboardConfig(self.handle, int(command, 16), int(value, 16), int(index, 16),
                                                      int(buffsize, 16), buffs)

    def set_mode(self):
        r = self.ArducamSDK.Py_ArduCam_setMode(self.handle, self.ArducamSDK.CONTINUOUS_MODE)
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
            self.ArducamSDK.Py_ArduCam_writeSensorReg(self.handle, int(r[0], 16), int(r[1], 16))
