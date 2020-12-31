import ast

import ArducamSDK

ARDUCAM_ERROR_CODES = {c: n for n, c in vars(ArducamSDK).items()
                       if isinstance(n, str)
                       and len(n) > 10
                       and n.startswith("USB_")}


class CameraConfigurationException(BaseException):
    pass


class ImageCaptureException(BaseException):
    pass


class ImageReadException(BaseException):
    pass


class ArducamException(BaseException):

    def __init__(self, message, code=None):
        BaseException.__init__(self)
        self.root_cause = get_arducam_error_name(code) or "unknown"
        self.args = (message, code)
        self.message = "{0}.  Root error is code {1}: '{2}'".format(message, code, self.root_cause)


def get_arducam_error_name(code):
    val = ast.literal_eval(str(code))
    return ARDUCAM_ERROR_CODES.get(val)
