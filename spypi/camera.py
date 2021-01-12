import json
import logging
import time
from collections import deque
from io import BytesIO

import ArducamSDK
import numpy as np
from imutils.video import VideoStream
from picamera import PiCamera
from simple_pid import PID

from spypi.error import CameraConfigurationException, ArducamException, ImageReadException
from spypi.lib.ImageConvert import convert_image
from spypi.resources import get_resource
from spypi.utils import FPSCounter, SimpleCounter, create_task


# class MyOutput(object):
#     def __init__(self):
#         self.size = 0
#         self.buffer = deque(maxlen=60)
#
#     def write(self, s):
#         #jpg_original = base64.b64decode(s)
#         jpg_as_np = np.frombuffer(s, dtype=np.uint8)
#         img = cv2.imdecode(jpg_as_np, flags=1)
#
#         print(img)
#
#         # nparr = np.fromstring(s, np.uint8)
#         #
#         # print(nparr)
#         #
#         # img_np = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
#         # self.buffer.append(img_np)
#         # if len(self.buffer) > 0:
#         #     print(self.buffer[0])
#         # print("\n\n\n")
#         #self.size += len(s)
#
#     def flush(self):
#         pass
#         #print('%d bytes would have been written' % self.size)

# with PiCamera() as camera:
#     camera.resolution = (640, 480)
#     camera.framerate = 60
#     op = MyOutput()
#     camera.start_recording(op, format='h264')
#     camera.wait_recording(10)
#
#     x = op.buffer.pop()
#
#
#     camera.stop_recording()

class Camera():

    def __init__(self, config):
        self.camera_type = config['camera']
        self.dev_id = config['device_id']
        self.frame_size = tuple(config['frame_size'])
        self.init_delay = config['init_delay']
        self.init_retry = config['init_retry']
        self.max_error_rate = config['max_error_rate']
        self.stream = None
        self.extra_info = []
        self.logger = logging.getLogger("camera")
        self.log_metrics = False
        self.ignore_warnings = False
        self.log_extra_info = False
        self.running = False
        self.images = deque(maxlen=10)
        self.fps_counter = FPSCounter()
        self.ecount = SimpleCounter(50)
        self.count = SimpleCounter(50)

    @classmethod
    def create(cls, config):
        cam = config['camera']
        if cam == 'arducam':
            return ArduCam(config)
        elif cam == 'picam':
            return PiCam(config)
        elif cam == 'imupicam':
            return ImUPiCam(config)
        elif cam == 'usb':
            return UsbCam(config)

        raise ValueError("Unknown camera type: {}".format(cam))

    def read_frames(self):
        while True and self.running:
            try:
                image = self.read_next_frame()
                if image is not None:
                    # add images to respective deques for processing ASYNC
                    self.images.append(image)

                    # No need to fetch every single frame - it causes data errors
                    if self.log_extra_info and self.count.count % 100 == 0:
                        self.extra_info = self.get_extra_label_info()

                    # Just for metrics
                    if self.log_metrics and self.count.increment():
                        self.logger.debug("Capture rate: {} FPS".format(self.fps_counter.get_fps()))

                    self.fps_counter.increment()

            except (ImageReadException, ArducamException) as e:
                self.ecount.increment()
                r = self.ecount.get_rate()
                if self.log_metrics:
                    self.logger.debug("Error rate: {}".format(round(r, 2)))
                if self.max_error_rate < r:
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
        if len(self.images) > 3:
            return self.images[0].copy()

    def read_next_frame(self):
        pass

    def get_extra_label_info(self):
        return []


class ImUPiCam(Camera):

    def __init__(self, config):
        super(ImUPiCam, self).__init__(config)
        self.start()

    def read_next_frame(self):
        time.sleep(0.025)
        return self.cam.read()

    def connect(self):
        self.cam = VideoStream(
            src=self.dev_id,
            usePiCamera=True,
            resolution=self.frame_size,
        )

    def start(self):
        self.logger.info("Starting picam")
        self.running = True
        self.connect()
        self.cam.start()
        create_task(self.read_frames).start()
        self.logger.info("Picam thread started")

    def stop(self):
        self.logger.info("Stopping picam")
        self.running = False
        self.cam.stop()
        self.images.clear()
        self.logger.info("Picam stopped")

    def next_image(self):
        if len(self.images) > 3:
            return self.images[0].copy()

    def get_extra_label_info(self):
        return []


class PiCam(Camera):

    def __init__(self, config):
        super(PiCam, self).__init__(config)

        self.height = self.frame_size[1]
        self.width = self.frame_size[0]

        self.start()

    def get_blank_image(self):
        return np.empty((self.height, self.width, 3), dtype=np.uint8)

    def read_next_frame(self):
        t1 = time.perf_counter()
        my_stream = BytesIO()
        # image = self.get_blank_image()
        # self.cam.capture(my_stream, 'jpeg')

        dt = time.perf_counter() - t1
        return None

        # filename = os.path.abspath("frame.jpg")
        # cv2.imwrite(filename, output)
        # output = output.reshape((112, 128, 3))
        # output = output[:100, :100, :]
        # output = np.empty((1300, 1000, 3), dtype=np.uint8)
        # x = self.picam.capture(output, format='rgb')

    def connect(self):
        self.logger.info("Connecting to picamera")
        self.cam = PiCamera(resolution=self.frame_size)
        time.sleep(2)

    def start(self):
        self.logger.info("Starting picam")
        self.running = True
        self.connect()
        create_task(self.read_frames).start()
        self.logger.info("Picam thread started")

    def stop(self):
        self.logger.info("Stopping picam")
        self.running = False
        self.cam.close()
        self.images.clear()
        self.logger.info("Picam stopped")

    def next_image(self):
        if len(self.images) > 3:
            return self.images[0].copy()

    def get_extra_label_info(self):
        return []


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
        self.extra_info = self.get_extra_label_info()

    def start(self, full=False):
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
        create_task(self.read_frames).start()
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

    def start_capture(self):
        self.logger.info("Start arducam capture thread")
        start_code = ArducamSDK.Py_ArduCam_beginCaptureImage(self.handle)
        if start_code != 0:
            raise ArducamException("Error starting capture thread", code=start_code)
        self.logger.debug("Thread started")

    def connect_cam(self):
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
                # ArducamSDK.Py_ArduCam_flush(self.handle)

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
