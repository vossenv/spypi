import ast

# Keep to regenerate table, but comment in case of dependency issues cross platform
# import ArducamSDK
# ARDUCAM_ERROR_CODES = {c: n for n, c in vars(ArducamSDK).items()
#                        if isinstance(n, str)
#                        and len(n) > 10
#                        and n.startswith("USB_")}

ARDUCAM_ERROR_CODES = {
    0: 'USB_CAMERA_NO_ERROR',
    65281: 'USB_CAMERA_USB_CREATE_ERROR',
    65282: 'USB_CAMERA_USB_SET_CONTEXT_ERROR',
    65283: 'USB_CAMERA_VR_COMMAND_ERROR',
    65284: 'USB_CAMERA_USB_VERSION_ERROR',
    65285: 'USB_CAMERA_BUFFER_ERROR',
    65286: 'USB_CAMERA_NOT_FOUND_DEVICE_ERROR',
    65291: 'USB_CAMERA_I2C_BIT_ERROR',
    65292: 'USB_CAMERA_I2C_NACK_ERROR',
    65293: 'USB_CAMERA_I2C_TIMEOUT',
    65312: 'USB_CAMERA_USB_TASK_ERROR',
    65313: 'USB_CAMERA_DATA_OVERFLOW_ERROR',
    65314: 'USB_CAMERA_DATA_LACK_ERROR',
    65315: 'USB_CAMERA_FIFO_FULL_ERROR',
    65316: 'USB_CAMERA_DATA_LEN_ERROR',
    65317: 'USB_CAMERA_FRAME_INDEX_ERROR',
    65318: 'USB_CAMERA_USB_TIMEOUT_ERROR',
    65328: 'USB_CAMERA_READ_EMPTY_ERROR',
    65329: 'USB_CAMERA_DEL_EMPTY_ERROR',
    65361: 'USB_CAMERA_SIZE_EXCEED_ERROR',
    65377: 'USB_USERDATA_ADDR_ERROR',
    65378: 'USB_USERDATA_LEN_ERROR',
    65393: 'USB_BOARD_FW_VERSION_NOT_SUPPORT_ERROR'
}


class CameraConfigurationException(BaseException):
    pass


class ImageReadException(BaseException):
    pass


class PiCamException(BaseException):
    def __init__(self, message, root_exception):
        BaseException.__init__(self)
        self.root_exception = root_exception
        self.root_cause = str(root_exception)
        self.message = "{0}.  Root error is code {1}: '{2}'".format(message, code, self.root_cause)
        self.args = (self.message, root_exception)

class ArducamException(BaseException):

    def __init__(self, message, code=None):
        BaseException.__init__(self)
        self.code = code
        self.root_cause = get_arducam_error_name(code) or "unknown"
        self.message = "{0}.  Root error is code {1}: '{2}'".format(message, code, self.root_cause)
        self.args = (self.message, code)


def get_arducam_error_name(code):
    val = ast.literal_eval(str(code))
    return ARDUCAM_ERROR_CODES.get(val)
