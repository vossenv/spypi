import picamera
import os
import numpy as np

os.chdir("recordings")
camera = picamera.PiCamera(resolution=(1300, 1000))
camera.rotation=180
counter = 0
ID = str(np.random.rand())[2:8]

camera.start_recording(ID + "_" + "%05d" % counter + ".h264")
camera.wait_recording(60)

while True:
    counter += 1
    camera.split_recording(ID + "_" + "%05d" % counter + ".h264")
    camera.wait_recording(60)

#camera.stop_recording()
