from __future__ import print_function
import sys

def reprint(msg):
    print(str(msg))
    sys.stdout.flush()

reprint("the modules will be imported")

import imutils
import cv2
import os
import collections
import numpy as np
import shutil
import threading
import traceback
import yaml
import pickle
import io
import signal
import requests
import itertools
import faulthandler
import socket
import logging
import time
import datetime
##################
reprint("the modules have been imported")


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


class LoggingContext:

    def init_logger(self, cfg):

        log_params = {
            'this_ip': self.get_ip(),
            'this_name': cfg['cam_prefix'].lstrip('_'),
            'log_level': logging.getLevelName(cfg['log_level'].upper()),
            'date_fmt': '%Y-%m-%d %H:%M:%S'
        }

        f_format = "%(asctime)s " + log_params['this_name'] + "  [%(name)-8.8s]  [%(levelname)-5.5s]  :::  " + log_params['this_ip'] + "  :::  %(message)s"
        logging.basicConfig(level=log_params['log_level'], format=f_format, datefmt=log_params['date_fmt'])
        logger = logging.getLogger("main")
        f_handler = logging.FileHandler('webcam_motion_stdlog.log', 'w')
        f_handler.setFormatter(logging.Formatter(f_format, log_params['date_fmt'] ))
        f_handler.setLevel(log_params['log_level'])
        logger.addHandler(f_handler)
        sys.stderr = sys.stdout = self.StreamToLogger(logger, log_params['log_level'])

    def get_ip(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(('10.255.255.255', 1))
            ip = s.getsockname()[0]
        except:
            ip = '127.0.0.1'
        s.close()
        return str(ip)

    class StreamToLogger(object):
        def __init__(self, logger, log_level):
            self.logger = logger
            self.log_level = log_level

        def write(self, message):
            for line in message.rstrip().splitlines():
                self.logger.log(self.log_level, line.rstrip())
        def flush(self): pass

class debugger:
    @staticmethod
    def explore(obj, memo):
        loc = id(obj)
        if loc not in memo:
            memo.add(loc)
            yield obj
        # Handle instances with slots.
            try:
                slots = obj.__slots__
            except AttributeError:
                pass
            else:
                for name in slots:
                    try:
                        attr = getattr(obj, name)
                    except AttributeError:
                        pass
                    else:
                    #yield from explore(attr, memo)
                        for bar in debugger.explore(attr, memo):
                            yield bar
        # Handle instances with dict.
            try:
                attrs = obj.__dict__
            except AttributeError:
                pass
            else:
            #yield from explore(attrs, memo)
                for bar in debugger.explore(attrs, memo):
                    yield bar
        # Handle dicts or iterables.
            for name in 'keys', 'values', '__iter__':
                try:
                    attr = getattr(obj, name)
                except AttributeError:
                    pass
                else:
                    for item in attr():
                    #yield from explore(item, memo)
                        for bar in debugger.explore(item, memo):
                            yield bar
    @staticmethod
    def totalsizeof(obj):
        t = lambda obj: sum(map(sys.getsizeof, debugger.explore(obj, set())))
        return t(obj)

class FileHandler:

    def __init__(self):
        self.save_path = backup_dir
        self.timeout = output_options['fileserver_timeout']
        self.max_retries = output_options['fileserver_max_retries']
        self.camid = str(cfg['cam_prefix']).lstrip('_');

    def make_backup(self, *filenames):
        if output_options['enable_file_backup']:
            reprint("Failed attempt, making a local backup... ")

            for f in filenames:
                shutil.copy(f, self.save_path)
                reprint("Backup (count: " + self.countDir(self.save_path)
                        + ")  created: " + os.path.join(self.save_path, f))
        else:
            reprint("Backup not enabled, skipping: " + str(filenames))

    def make_dir(self, path):
        reprint("Creating folders... " + path)
        try:
            os.mkdir(path)
        except OSError:
            pass

    def copy_to_remote(self, *files):
        status = 0
        for f in files:
            try:
                if isinstance(f, tuple):
                    finaldest = os.path.join(remote_dir, f[1]).rstrip(os.sep)
                    f = f[0]
                else:
                    finaldest = remote_dir
                reprint("Copying " + f + " to " + finaldest)
                shutil.copy(os.path.join(f), finaldest)
                status += 200
            except Exception as e:
                reprint("Transfer failed due to: " + str(e))
                return 3
        return status

    def post_files(self, *files):
        status = 0
        headers = {}
        for f in files:

            if isinstance(f, tuple):
                headers['File-Destination'] = f[1]
                f = f[0]

            filesize = "%0.3f MB" % round(os.path.getsize(os.path.abspath(f)) / 1000000.0, 4)
            headers['Size'] = filesize

            for i in range(1, self.max_retries + 1):
                try:
                    reprint("Sending " + f + " (" + filesize + ") .... Attempt " + str(i) + "/" + str(self.max_retries))
                    r = requests.post(url=output_options['fileserver_address'] + "/store", headers=headers, files=dict(file=open(f, 'rb')), timeout=self.timeout)
                    reprint("Result: " + str(r.status_code) + ": " + str(r.content))
                    status += r.status_code
                    if status % 200 == 0:
                        reprint("Removing " + f)
                        self.remove_files(f)
                    break
                except Exception as e:
                    status = -1
                if i == self.max_retries: reprint("Max tries exceeded, aborting transfers... ")
                reprint("Status " + str(status))
                if status % 200 != 0:
                    reprint("Failed to complete upload: " + f + ". Size: " + filesize + ". Error: " + str(e))


        return status













    def post_image(self, image):
        # per_motion = str("%2.2f" % (100 * np.average(avgthresh) / (255 * frame_w * frame_h)))

        image_metadata = {'Test-Header': 5}
        header = {'Metadata': str(image_metadata)}
        a_numpy = io.BytesIO(cv2.imencode('.jpg', image)[1])

        try:
            r = requests.post(url=output_options['imageserver_address'] + "/cameras/" + self.camid + "/update", files=dict(file=a_numpy), headers=header, timeout=self.timeout)
        except Exception as e:
            reprint(e)

    def clean_directory(self, dir):
        reprint("Cleaning directory " + dir + "....")
        for f in os.listdir(dir):
            self.remove_files(f)
        reprint("Finished cleanup")

    def remove_files(self, *filenames):
        for f in filenames:
            try:
                f = os.path.abspath(f)
                if not os.path.isdir(f):
                    reprint("Removing " + f)
                    os.unlink(f)
                else:
                    reprint("Skipping " + f + " because it is a directory...")
            except Exception as e:
                reprint("Could not remove: " + f + " due to " + str(e))

    def sendBackupFiles(self):

        if int(self.countDir(self.save_path)) == 0: return

        reprint("\nAttempting to transfer " + self.countDir(self.save_path) + " files from backup.... ")
        for f in os.listdir(self.save_path):
            path = "logs" if f.endswith(".txt") else ""
            f = os.path.join(self.save_path, f)
            if fh.post_files((f, path)) != 200:
                reprint("Failed transfer, waiting until subsuquent try to continue... ")
                return
            else:
                reprint("Success! " + self.countDir(self.save_path) + " remain. Removing backup of... " + f)
                fh.remove_files(f)

    def countDir(self, path):
        return str(len(os.listdir(path)))


class DisplayTools:
    class ProgressBar:
        def __init__(self):

            self.interval = 10
            self.steps = list(range(self.interval * 2, 100 + self.interval, self.interval))
            self.progress = itertools.cycle(self.steps)
            self.trigger = self.interval
            self.fraction = 2
            self.bar_width = 100 / self.fraction

        def update(self, percent):

            rp = int(round(percent, 0))
            proglen = int(round(rp / self.fraction, 0))
            bar = proglen * "=" + (int(round(100 / self.fraction, 0)) - proglen) * " "

            if rp > 0 and rp % self.trigger == 0:
                reprint("[" + bar + "] % " + str(self.trigger))
                if self.trigger < 100: self.trigger = self.progress.next()

#def gettemprh(temp, rh):

#    reprint("banana")
#    reprint(temp)
#    reprint(rh)


def writeout(video):
    #    logger = open( os.path.join(local_rec_folder, name + cfg["cam_prefix"] + "_pre.txt"), "w")
    #    logger.write("T-\tN\tArea\tPerim\tMax\tAvg\tA/N\tM/A\tAvgN\tTime\n")

    out = cv2.VideoWriter(os.path.join(record_dir, video['filename_pre']), cv2.VideoWriter_fourcc('X', 'V', 'I', 'D'), 5, (frame_w, frame_h))

    counter = 0
    for entry in video['buffer_copy']:
        entry = cv2.imdecode(entry,1)
        cv2.putText(entry, video['buffer_timestamp_copy'][counter], (10, entry.shape[0] - 10), cv2.FONT_HERSHEY_DUPLEX, 0.8, (255, 255, 255), 1, cv2.LINE_AA)
        out.write(entry)
        counter += 1
        time.sleep(0)
    #    counter = 0
    #    for entry in PostMovie:
    #        cv2.putText(entry, RecordedMovietimestamp[counter], (10, entry.shape[0] - 10), cv2.FONT_HERSHEY_DUPLEX, 0.8, (255, 255, 255), 1, cv2.LINE_AA)
    #        out.write(entry)
    #        counter += 1
    #        time.sleep(0)
    #    for entry in logarray:
    #        logger.write(entry)
    #        time.sleep(0)
    #    logger.close()
    out.release()


#    shutil.move(os.path.join(local_rec_folder, name + cfg["cam_prefix"] + ".avi"), os.path.join(remote_dir, name + cfg["cam_prefix"] + ".avi"))
#    shutil.move(os.path.join(local_rec_folder, name + cfg["cam_prefix"] + ".txt"), os.path.join(remote_dir, "logs", "log_" + name + cfg["cam_prefix"] + ".txt"))
#    cv2.imwrite(os.path.join(remote_dir, "hotspots", name + cfg["cam_prefix"] + ".jpg"), hot*255)


def writeframe(remote_dir, frame):
    cv2.imwrite(os.path.join(remote_dir, "image", datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + cfg["cam_prefix"] + ".jpg"), frame)

def analyzevideo(video):


    vpath = os.path.join(record_dir, video['filename_motion'])
    reprint("Analyzing file\t" + str(vpath))
    vs = cv2.VideoCapture(vpath)
    while True:
        (grabbed, frame) = vs.read()
        if not grabbed or video['person_detected'] == True:
            break
        (H, W) = frame.shape[:2]
        blob = cv2.dnn.blobFromImage(frame, 1 / 255.0, (160, 160), swapRB=True, crop=False)
        net.setInput(blob)
        layerOutputs = net.forward(ln)
        boxes = []
        confidences = []
        classIDs = []
        for output in layerOutputs:
            	# loop over each of the detections
            for detection in output:
            # extract the class ID and confidence (i.e., probability) of
            # the current object detection
                scores = detection[5:]
                classID = np.argmax(scores)
                confidence = scores[classID]
 
            # filter out weak predictions by ensuring the detected
            # probability is greater than the minimum probability
                if confidence > 0.2:
            	# scale the bounding box coordinates back relative to the
            	# size of the image, keeping in mind that YOLO actually
            	# returns the center (x, y)-coordinates of the bounding
            	# box followed by the boxes' width and height
                    box = detection[0:4] * np.array([W, H, W, H])
                    (centerX, centerY, width, height) = box.astype("int")
 
           	# use the center (x, y)-coordinates to derive the top and
          	# and left corner of the bounding box
                    x = int(centerX - (width / 2))
                    y = int(centerY - (height / 2))
 
            	# update our list of bounding box coordinates, confidences,
            	# and class IDs
                    boxes.append([x, y, int(width), int(height)])
                    confidences.append(float(confidence))
                    classIDs.append(classID)

            # apply non-maxima suppression to suppress weak, overlapping bounding
            # boxes
        idxs = cv2.dnn.NMSBoxes(boxes, confidences, 0.2, 0.1)

            # ensure at least one detection exists
        if len(idxs) > 0:
            	# loop over the indexes we are keeping

            for i in idxs.flatten():
                reprint("Object detected:\t{}\t{:.2f}".format(LABELS[classIDs[i]], confidences[i]))
#                if LABELS[classIDs[i]] == "car" or LABELS[classIDs[i]] == "person":
                if LABELS[classIDs[i]] == "person":
#                	(x, y) = (boxes[i][0], boxes[i][1])
#                	(w, h) = (boxes[i][2], boxes[i][3])
#                	color = [int(c) for c in COLORS[classIDs[i]]]
#                	cv2.rectangle(frame, (x, y), (x + w, y + h), color, 5)
#                	text = "{}: {:.2f}".format(LABELS[classIDs[i]], confidences[i])
#                        cv2.putText(frame, text, (x, y - 5), cv2.FONT_HERSHEY_DUPLEX, 1, color, 1, cv2.LINE_AA)
                        video['person_detected'] = True
                        break

    fh.remove_files(vpath)
    threading.Thread(target=concatenatevideo, args=[video]).start()


def concatenatevideo(video):
    p = DisplayTools.ProgressBar()

    reprint("Hooman:\t" + str(video['person_detected']))

    if video['person_detected'] == False:
        vpath = os.path.join(record_dir, video['filename_output'])
    else:
        vpath = os.path.join(record_dir, video['filename_base'] + "_person.avi")

    lpath = os.path.join(record_dir, video['filename_log'])
    prepath = os.path.join(record_dir, video['filename_pre'])
    postpath = os.path.join(record_dir, video['filename_post'])
    videos = [prepath, postpath]

    reprint("Begin concatenation.... \n")

    out = cv2.VideoWriter(vpath, cv2.VideoWriter_fourcc('X', 'V', 'I', 'D'), 5, (frame_w, frame_h))
    cap = cv2.VideoCapture(videos[0])

    index = 0
    loopindex = 0
    while (cap.isOpened()):

        ret, frame = cap.read()
        if frame is None:

            index += 1
            if index >= len(videos):
                break
            cap = cv2.VideoCapture(videos[index])
            ret, frame = cap.read()

        out.write(frame)

        p.update(100.00 * (float(loopindex) / float(video['frame_count'])))
        loopindex += 1

    cap.release()
    out.release()

    reprint("\nConcatenation finished.... Begin file transfers... \n")

    if output_options['enable_fileserver']:
        if fh.post_files(vpath) != 200: fh.make_backup(vpath)
        if fh.post_files((lpath, "logs")) != 200: fh.make_backup(lpath)
        else:
            fh.sendBackupFiles()

    if output_options['enable_remote_storage']:
        #if fh.copy_to_remote(vpath, (lpath, "logs")) != 400: fh.make_backup(vpath, lpath)
        if fh.copy_to_remote(vpath) != 200: fh.make_backup(vpath)
        if fh.copy_to_remote((lpath, "logs")) != 200: fh.make_backup(lpath)

    reprint("\nTransfers complete, beginning cleanup... \n")

    fh.remove_files(vpath, lpath, *videos)

    reprint("\nFinished process....")


def reset_counter():
    return 0

def currframe(image, Recording, FrameCounter, out):

#    ex = "counter" in locals()


#    if ex == False:
#     counter = reset_counter()

#    ex = "counter" in locals()
#    reprint(FrameCounter)



    image = imutils.rotate_bound(image, cfg["rotation_angle"])

#    colorconversion = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
#    clahe = cv2.createCLAHE(clipLimit=1.0, tileGridSize=(4,4))

#    for i in range(2):
#        colorconversion = clahe.apply(colorconversion)

#    if cfg["camera"] == "arducam":
#        kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
#        colorconversion = cv2.medianBlur(colorconversion,3)
#        colorconversion = cv2.filter2D(colorconversion, -1, kernel)



#    colorconversion = cv2.resize(colorconversion, (frame_w, frame_h), interpolation=cv2.INTER_AREA)
#    colorconversion = cv2.resize(colorconversion, (cfg["output_frame_width"], cfg["output_frame_height"]), interpolation=cv2.INTER_AREA)

#    imagedelta = colorconversion.shape[1] - colorconversion.shape[0]

#    if imagedelta > 0:
#        colorconversion = colorconversion[:, int(imagedelta/2):int(colorconversion.shape[1] - imagedelta/2)]
#    else:
#        colorconversion = colorconversion[int(imagedelta/2):int(colorconversion.shape[0] - imagedelta/2), :]


#    if Recording == True:
#        image = cv2.applyColorMap(colorconversion, 1)
#        image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
#        image[int(image.shape[0] * 0.92):int(image.shape[0]),0:int(image.shape[1]),:] = 0
#        image[0:int(image.shape[0]*0.08),0:int(image.shape[1]),:] = 0

#        cv2.rectangle(image,(0,0),(image.shape[0],image.shape[1]),(255,0,0),10)
#        image[int(image.shape[0] * 0.99):int(image.shape[0]),0:int(image.shape[1]),:] = (255,0,0)

#        image[int(image.shape[0] * 0.92):int(image.shape[0]),0:int(image.shape[1]),2] = 255
#        image = cv2.bitwise_not(image, image, mask=pov)
#        cv2.putText(image, "Rec", (image.shape[1] - 50, image.shape[0] - 10), cv2.FONT_HERSHEY_DUPLEX, 0.8, (0, 255, 0), 1, cv2.LINE_AA)
#    else:
#        image = cv2.cvtColor(colorconversion, cv2.COLOR_GRAY2BGR)
#        image[int(image.shape[0] * 0.92):int(image.shape[0]),0:int(image.shape[1]),:] = 0
#        image[0:int(image.shape[0]*0.08),0:int(image.shape[1]),:] = 0



#    a1 = [0, int(image.shape[0] * 0.93)] #0,896
#    a2 = [0, int((1 - 0) * image.shape[0])] #0,964
#    a3 = [int(image.shape[1] * 0.4), int((1 - 0) * image.shape[0])] #512,964
#    a4 = [int(image.shape[1] * 0.4), int(image.shape[0] * 0.93)] #512,896

#    digits_area = np.array([[a1, a2, a3, a4]], dtype=np.int32)

#    cv2.fillPoly(image, digits_area, (0,0,0) )

#    reprint("plantana")

#    if FrameCounter % 5 == 0:
#        filename = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + "_back_alley.avi"
#        reprint(filename)
#        out = cv2.VideoWriter(filename, cv2.VideoWriter_fourcc('X', 'V', 'I', 'D'), 8, (1280, 964))
#        FrameRecordingStarted = FrameCounter
#        reprint("Creating file " + str(filename))

#    reprint(out)
#    reprint("banana")

    if cfg["crop"] == True:
        colorconversion = image.copy()
        colorconversion = colorconversion[int(frame_h * cfg["fraction_masked_top"]):int((1 - cfg["fraction_masked_bottom"]) * frame_h), int(frame_w * cfg["fraction_masked_left"]):int((1 - cfg["fraction_masked_right"]) * frame_w)]

        a1 = [0, int(colorconversion.shape[0] * 0.93)] #0,896
        a2 = [0, int((1 - 0) * colorconversion.shape[0])] #0,964
        a3 = [int(colorconversion.shape[1] * 0.4), int((1 - 0) * colorconversion.shape[0])] #512,964
        a4 = [int(colorconversion.shape[1] * 0.4), int(colorconversion.shape[0] * 0.93)] #512,896
        digits_area = np.array([[a1, a2, a3, a4]], dtype=np.int32)
        cv2.fillPoly(colorconversion, digits_area, (0,0,0) )
        cv2.putText(colorconversion, datetime.datetime.now().strftime("%Y-%m-%d: %H:%M:%S:%f")[:-5], (10, colorconversion.shape[0] - 10), cv2.FONT_HERSHEY_DUPLEX, 0.8, (255, 255, 255), 1, cv2.LINE_AA)
        if cfg["camera"] == "arducam":
            ardu = ("Time: " + str((ArducamSDK.Py_ArduCam_readSensorReg(handle, int(12644))[1])) + " ISO: " + str((ArducamSDK.Py_ArduCam_readSensorReg(handle, int(12586))[1])) + " lum: " + str((ArducamSDK.Py_ArduCam_readSensorReg(handle, int(12626))[1])) + "/" + str((ArducamSDK.Py_ArduCam_readSensorReg(handle, int(12546))[1])))
            cv2.putText(colorconversion, ardu, (10, colorconversion.shape[0] - 40), cv2.FONT_HERSHEY_DUPLEX, 0.8, (255, 255, 255), 1, cv2.LINE_AA)
        fh.post_image(cv2.resize(colorconversion,(500,500)))



    a1 = [0, int(image.shape[0] * 0.93)] #0,896
    a2 = [0, int((1 - 0) * image.shape[0])] #0,964
    a3 = [int(image.shape[1] * 0.4), int((1 - 0) * image.shape[0])] #512,964
    a4 = [int(image.shape[1] * 0.4), int(image.shape[0] * 0.93)] #512,896

    digits_area = np.array([[a1, a2, a3, a4]], dtype=np.int32)

    cv2.fillPoly(image, digits_area, (0,0,0) )




    cv2.putText(image, datetime.datetime.now().strftime("%Y-%m-%d: %H:%M:%S:%f")[:-5], (10, image.shape[0] - 10), cv2.FONT_HERSHEY_DUPLEX, 0.8, (255, 255, 255), 1, cv2.LINE_AA)
    if cfg["camera"] == "arducam":
        ardu = ("Time: " + str((ArducamSDK.Py_ArduCam_readSensorReg(handle, int(12644))[1])) + " ISO: " + str((ArducamSDK.Py_ArduCam_readSensorReg(handle, int(12586))[1])) + " lum: " + str((ArducamSDK.Py_ArduCam_readSensorReg(handle, int(12626))[1])) + "/" + str((ArducamSDK.Py_ArduCam_readSensorReg(handle, int(12546))[1])))
        cv2.putText(image, ardu, (10, image.shape[0] - 40), cv2.FONT_HERSHEY_DUPLEX, 0.8, (255, 255, 255), 1, cv2.LINE_AA)

    if cfg["crop"] == False:
        fh.post_image(cv2.resize(image,(500,500)))



    out.write(cv2.resize(image,(1280,964)))

#    cv2.resize(image,(500,500))
#        try:
#            colorconversion = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
#        except:
#            colorconversion = image
#            pass
#        for i in range(2):
#            colorconversion = clahe.apply(colorconversion)



#    if (FrameCounter > 0) and (FrameCounter % 5 == 0) and (FrameRecordingStarted != FrameCounter):
#        out.release()
#        reprint("Sending file " + str(filename))
#        threading.Thread(target=fh.post_files,args=[filename]).start()










#    if cfg['write_frame']:
#        cv2.imwrite("frame.jpg", image)

#    counter += 1
#    reprint(counter)


#    fh.post_image(image)


def sigint_handler(signum, frame):
    global running
    running = False
    exit()


signal.signal(signal.SIGINT, sigint_handler)
# signal.signal(signal.SIGHUP, sigint_handler)
signal.signal(signal.SIGTERM, sigint_handler)


def captureImage_thread():
    global frame_acq, running

    DataTransferCounter = 0
    FrameCounter = 0


    while running:
        try:
            frame_acq = camera.read()
            DataTransferCounter += 1
            time.sleep(0.005)

#            reprint(DataTransferCounter)
            if DataTransferCounter == cfg['image_post_interval']:

                if FrameCounter % 500 == 0:
                    filename = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + "_backalley.avi"
                    reprint(filename)

                    out = cv2.VideoWriter(os.path.join(record_dir, filename), cv2.VideoWriter_fourcc('X', 'V', 'I', 'D'), 8, (1280, 964))
#                    out = cv2.VideoWriter(filename, cv2.VideoWriter_fourcc('X', 'V', 'I', 'D'), 8, (1280, 964))
                    FrameRecordingStarted = FrameCounter
                    reprint("Creating file " + str(filename))


                currframe(frame_acq.copy(), Recording, FrameCounter, out)
                FrameCounter += 1

                if FrameCounter % 500 == 0:
                    out.release()
                    reprint("Sending file " + str(filename))
                    threading.Thread(target=fh.post_files,args=[os.path.join(record_dir, filename)]).start()


                DataTransferCounter = 0


            #            reprint("frame acquired\t" + str(running))

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                running = False
                exit()
                break
        except:
            pass
    reprint("done acquiring\t" + str(running))


def readImage_thread():
    global frame_acq, frame_number, Recording, Buffer, previousFrame, RecordedMovie, RecordedMovietimestamp, log, PostMovementCounter, Reference, running, mask
    reprint("preparing")
    time.sleep(cfg['camera_init_delay'])
    reprint("starting")

    rec_index = 0
    while running:

        try:
            timeref = time.clock()
            frame = None

            if cfg["camera"] == "arducam":
                frame = np.zeros_like(ac.frame_acq)
                np.copyto(frame, ac.frame_acq)
            else:
                frame = np.zeros_like(frame_acq)
                np.copyto(frame, frame_acq)

            if cfg["optics_calibration"] == True:
                h, w = frame.shape[:2]
                newcameramtx, roi = cv2.getOptimalNewCameraMatrix(mtx, dist, (w, h), 1, (w, h))
                frame = cv2.undistort(frame, mtx, dist, None, newcameramtx)
                x, y, w, h = roi
                frame = frame[y:y + h, x:x + w]

            dateref = datetime.datetime.now().strftime("%Y-%m-%d: %H:%M:%S")

            frame = imutils.rotate_bound(frame, cfg["rotation_angle"])
            frame = cv2.resize(frame, (frame_w, frame_h), interpolation=cv2.INTER_AREA)

            raw_frame = np.zeros_like(frame)
            np.copyto(raw_frame, frame)

            if (frame_number % cfg["frame_delta_screenshot"]) == 0 and Recording == False:
                threading.Thread(target=writeframe, args=[remote_dir, frame]).start()

            frame_number = frame_number + 1

            if cfg["crop"] == True:
                frame = frame[int(frame_h * cfg["fraction_masked_top"]):int((1 - cfg["fraction_masked_bottom"]) * frame_h), int(frame_w * cfg["fraction_masked_left"]):int((1 - cfg["fraction_masked_right"]) * frame_w), :]
                frame = cv2.resize(frame, (frame_w, frame_h), interpolation=cv2.INTER_AREA)
                mask = np.zeros([frame_h, frame_w, 1], dtype="uint8")
                mask = cv2.bitwise_not(mask)
            else:
                mask = np.zeros([frame_h, frame_w, 1], dtype="uint8")
                mask[:, :, :] = 255
                mask[int(frame_h * cfg["fraction_masked_top"]):int((1 - cfg["fraction_masked_bottom"]) * frame_h), int(frame_w * cfg["fraction_masked_left"]):int((1 - cfg["fraction_masked_right"]) * frame_w), :] = 0
                mask = cv2.bitwise_not(mask)

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (cfg["ImageBlurKernel"], cfg["ImageBlurKernel"]), 0)

            gray_masked = cv2.bitwise_and(gray, gray, mask=mask)

            Buffertimestamp.append(dateref)
#            Buffer.append(raw_frame)
            result, raw_frame_encoded = cv2.imencode('.jpg', raw_frame, [int(cv2.IMWRITE_JPEG_QUALITY),100])
            Buffer.append(raw_frame_encoded)

            if previousFrame is None:
                previousFrame = gray


            if PostMovementCounter <= 0:
                logger.close()
                MotionWriter.release()
                out.release()

                video['frame_count'] = len(video['buffer_copy']) + rec_index

                log = []
                rec_index = 0
                Recording = False
                RecordedMovie = []
                RecordedMovietimestamp = []
                PostMovementCounter = PostMovementCounterReset
                RecordedMovie = RecordedMovietimestamp = BufferCopy = log = None

                reprint("Recording stopped:\t" + datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + "\tFrames: " + str(video['frame_count']))

                threading.Thread(target=analyzevideo, args=[video]).start()
#                threading.Thread(target=concatenatevideo, args=[video]).start()

            cv2.putText(frame, datetime.datetime.now().strftime("%Y-%m-%d: %H:%M:%S"), (10, frame.shape[0] - 10), cv2.FONT_HERSHEY_DUPLEX, 0.8, (255, 255, 255), 1, cv2.LINE_AA)


            previousFrame = gray


        except Exception as e:
            reprint(e)
            traceback.print_exc(file=sys.stdout)

    reprint("done displaying\t" + str(running))

#def readImage_thread():

#    reprint("running")
#    global handle,running,Width,Height,save_flag,acfg,color_mode,save_raw
#    global COLOR_BayerGB2BGR,COLOR_BayerRG2BGR,COLOR_BayerGR2BGR,COLOR_BayerBG2BGR
#    count = 0
#    totalFrame = 0
#    time0 = time.time()
#    time1 = time.time()
#    data = {}
#    counter = 0
#    clahe = cv2.createCLAHE(clipLimit=1.0, tileGridSize=(4,4))

#    while running:
#        display_time = time.time()
#        if ArducamSDK.Py_ArduCam_availableImage(handle) > 0:		
#            rtn_val,data,rtn_cfg = ArducamSDK.Py_ArduCam_readImage(handle)
#            datasize = rtn_cfg['u32Size']
#            if rtn_val != 0:
#                print("read data fail!")
#                continue
#                
#            if datasize == 0:
#                continue

#            image = convert_image(data,rtn_cfg,color_mode)

#            a1 = [0, int(image.shape[0] * 0.93)] #0,896
#            a2 = [0, int((1 - 0) * image.shape[0])] #0,964

#            a3 = [int(image.shape[1] * 0.4), int((1 - 0) * image.shape[0])] #512,964
#            a4 = [int(image.shape[1] * 0.4), int(image.shape[0] * 0.93)] #512,896

#            digits_area = np.array([[a1, a2, a3, a4]], dtype=np.int32)

#            cv2.fillPoly( image, digits_area, (0,0,0) )

#            if counter == 0:
#                filename = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + "_front_top.avi"
#                out = cv2.VideoWriter(filename, cv2.VideoWriter_fourcc('X', 'V', 'I', 'D'), 8, (cfg['output_frame_width'], cfg['output_frame_height']))
#                reprint("Creating file " + str(filename))

#            cv2.putText(image, datetime.datetime.now().strftime("%Y-%m-%d: %H:%M:%S %f"), (10, image.shape[0] - 10), cv2.FONT_HERSHEY_DUPLEX, 0.8, (255, 255, 255), 1, cv2.LINE_AA)
#            ardu = ("Time: " + str((ArducamSDK.Py_ArduCam_readSensorReg(handle, int(12644))[1])) + " ISO: " + str((ArducamSDK.Py_ArduCam_readSensorReg(handle, int(12586))[1])) + " lum: " + str((ArducamSDK.Py_ArduCam_readSensorReg(handle, int(12626))[1])) + "/" + str((ArducamSDK.Py_ArduCam_readSensorReg(handle, int(12546))[1])))
#            cv2.putText(image, ardu, (10, image.shape[0] - 40), cv2.FONT_HERSHEY_DUPLEX, 0.8, (255, 255, 255), 1, cv2.LINE_AA)

#            out.write(cv2.resize(image,(cfg['output_frame_width'],cfg['output_frame_height'])))

#            cv2.resize(image,(512,384))
#            try:
#                colorconversion = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
#            except:
#                colorconversion = image
#                pass
#            for i in range(2):
#                colorconversion = clahe.apply(colorconversion)

#            fh.post_image(colorconversion)
#            counter += 1

#            reprint(counter)
#            if counter == 500:
#                out.release()
#                reprint("Sending file " + str(filename))
#                threading.Thread(target=fh.post_files,args=[filename]).start()
#                counter = 0
#            ArducamSDK.Py_ArduCam_del(handle)
#        else:
#            time.sleep(0.001)

#################################################################################################################################################

# Context begins here (only def above)

#################################################################################################################################################

global running
running = True

with open("camera.yml", 'r') as stream: cfg = yaml.load(stream, Loader=yaml.FullLoader)

# For clarity in code
output_options = cfg['output']
frame_h = cfg['frame_height']
frame_w = cfg['frame_width']
remote_dir = output_options['remote_storage_drive']
record_dir = "recordings"
backup_dir = os.path.join(record_dir, "backup")
faulthandler.enable()
LoggingContext().init_logger(cfg)

if cfg["camera"] == "usb":
    from imutils.video import WebcamVideoStream
    camera = WebcamVideoStream(src=0)

elif cfg["camera"] == "arducam":
    import arducamout as ac
    import ArducamSDK

    ac.cf = currframe
    ac.camera_initFromFile("AR0134_960p_Color.json")
    ArducamSDK.Py_ArduCam_setMode(ac.handle, ArducamSDK.CONTINUOUS_MODE)

elif cfg["camera"] == "picam":
    from imutils.video import VideoStream
    camera = VideoStream(src=0, usePiCamera=True, resolution=(frame_w, frame_h), framerate=5)

else:
    raise AssertionError("The device has not been specified")

reprint("Camera type: " + cfg["camera"])

if cfg["optics_calibration"] == True:
    ret, mtx, dist, rvecs, tvecs = pickle.load(open('calib.pkl', 'rb'))

PreMovementCounter = cfg['PreMovementCounter']
PostMovementCounterReset = cfg['PostMovementCounterReset']
PostMovementCounter = PostMovementCounterReset




Buffer = collections.deque("", PreMovementCounter)
videobuffer = collections.deque("", 1)
avgthresh = collections.deque("", 5)
Buffertimestamp = collections.deque("", PreMovementCounter)
AvgArea = collections.deque("", 10)
Avgcnts = collections.deque("", 10)
Average = collections.deque("", 200)

#counter = 0
frame_number = 0
previousFrame = None
Recording = False
Motion = False
AvgContourArea = 0
RecordedMovie = []
BufferCopy = []
log = []
MotionTriggeredFrames = []
RecordedMovietimestamp = []
history = 10
varThreshold = 500
bShadowDetection = True
fgbg = cv2.createBackgroundSubtractorKNN(history, varThreshold, bShadowDetection)

pov = cv2.imread('dalek_POV.png', 0)
white = np.zeros([384, 512, 3], dtype="uint8")
white[:, :, :] = 255

if __name__ == "__main__":

    fh = FileHandler()
    fh.make_dir(record_dir)
    fh.make_dir(backup_dir)

    threads = []

    if cfg["camera"] == "arducam":
        threads.append(threading.Thread(target=ac.captureImage_thread))
#        threads.append(threading.Thread(target=ac.readImage_thread, args=[record_dir]))

    else:
        camera.start()
        reprint("The camera sensor will be initialized")
        time.sleep(cfg['camera_startup_delay'])
        threads.append(threading.Thread(target=captureImage_thread))

#    if cfg["detect_motion"] == True:
#        threads.append(threading.Thread(target=readImage_thread))

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()
