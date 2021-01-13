from collections import deque

import picamera
from picamera.array import PiRGBAnalysis

# class SplitFrames(object):
#     def __init__(self):
#         self.frame_num = 0
#         self.output = None
#         self.buffer = deque(maxlen=50)
#
#     def write(self, buf):
#         self.buffer.append(buf)
#
#         # if buf.startswith(b'\xff\xd8'):
#         #     # Start of new frame; close the old one (if any) and
#         #     # open a new output
#         #     if self.output:
#         #         self.output.close()
#         #     self.frame_num += 1
#         #     self.output = io.open('image%02d.jpg' % self.frame_num, 'wb')
#         # self.output.write(buf)
#
# with picamera.PiCamera(resolution='720p', framerate=30) as camera:
#     #time.sleep(2)
#     output = SplitFrames()
#     start = time.time()
#     camera.start_recording(output, format='rgb')
#     camera.wait_recording(2)
#
#     z = output
#
#     camera.stop_recording()
#     finish = time.time()
# print('Captured %d frames at %.2ffps' % (
#     output.frame_num,
#     output.frame_num / (finish - start)))
# from spypi.utils import MultiCounter
#
#
# class MyColorAnalyzer(PiRGBAnalysis):
#     def __init__(self, camera):
#         super(MyColorAnalyzer, self).__init__(camera)
#         self.last_color = ''
#         self.buffer = deque(maxlen=50)
#         self.fps = MultiCounter()
#         self.c = SimpleCounter(30)
#     def analyze(self, a):
#         self.buffer.append(a)
#         self.fps.increment()
#         if self.c.increment():
#             print(self.fps.get_rate())

        # Convert the average color of the pixels in the middle box
        # c = Color(
        #     r=int(np.mean(a[30:60, 60:120, 0])),
        #     g=int(np.mean(a[30:60, 60:120, 1])),
        #     b=int(np.mean(a[30:60, 60:120, 2]))
        #     )
        # # Convert the color to hue, saturation, lightness
        # h, l, s = c.hls
        # c = 'none'
        # if s > 1/3:
        #     if h > 8/9 or h < 1/36:
        #         c = 'red'
        #     elif 5/9 < h < 2/3:
        #         c = 'blue'
        #     elif 5/36 < h < 4/9:
        #         c = 'green'
        # # If the color has changed, update the display
        # if c != self.last_color:
        #     self.camera.annotate_text = c
        #     self.last_color = c

camera = picamera.PiCamera(resolution='1280x976', framerate=30)
# analyzer = MyColorAnalyzer(camera)
camera.rotation=270
#camera.start_recording(analyzer, 'rgb')
camera.start_recording('test.h264', 'h264')


while True:
    camera.capture('test.jpg', use_video_port=True)
    camera.wait_recording(1)

    #cv2.imwrite("frame12.jpg", analyzer.buffer.pop())
