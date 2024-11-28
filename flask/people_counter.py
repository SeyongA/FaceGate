from tracker.centroidtracker import CentroidTracker
from tracker.trackableobject import TrackableObject
from itertools import zip_longest
from utils.mailer import Mailer
from imutils.video import FPS
import numpy as np
import threading
import datetime
import logging
import imutils
import time
import json
import csv
import cv2

# Setup logger
logging.basicConfig(level=logging.INFO, format="[INFO] %(message)s")
logger = logging.getLogger(__name__)

# Load configuration
with open("utils/config.json", "r") as file:
    config = json.load(file)

# Global variables for Flask integration
output_frame = None
lock = threading.Lock()

def send_mail():
    """Send email alerts."""
    Mailer().send(config["Email_Receive"])

def log_data(move_in, in_time, move_out, out_time):
    """Log counting data to a CSV file."""
    data = [move_in, in_time, move_out, out_time]
    export_data = zip_longest(*data, fillvalue="")
    with open('utils/data/logs/counting_data.csv', 'w', newline='') as myfile:
        wr = csv.writer(myfile, quoting=csv.QUOTE_ALL)
        if myfile.tell() == 0:  # Check if header rows are already existing
            wr.writerow(("Move In", "In Time", "Move Out", "Out Time"))
            wr.writerows(export_data)

def people_counter():
    """Main function for people counting."""
    global output_frame, lock

    CLASSES = ["background", "aeroplane", "bicycle", "bird", "boat",
               "bottle", "bus", "car", "cat", "chair", "cow", "diningtable",
               "dog", "horse", "motorbike", "person", "pottedplant", "sheep",
               "sofa", "train", "tvmonitor"]

    net = cv2.dnn.readNetFromCaffe("detector/MobileNetSSD_deploy.prototxt", 
                                   "detector/MobileNetSSD_deploy.caffemodel")

    logger.info("Starting video stream...")
    # video_stream = cv2.VideoCapture(0)  # Use default webcam
    video_stream = cv2.VideoCapture(r"C:\FaceGate\flask\utils\data\tests\test_1.mp4")


    ct = CentroidTracker(maxDisappeared=40, maxDistance=50)
    trackableObjects = {}
    W, H = None, None
    totalFrames = 0
    totalDown, totalUp = 0, 0
    move_in, in_time, move_out, out_time = [], [], [], []

    fps = FPS().start()

    while True:
        ret, frame = video_stream.read()
        if not ret:
            logger.error("Failed to grab frame.")
            break

        frame = imutils.resize(frame, width=500)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        if W is None or H is None:
            H, W = frame.shape[:2]

        status = "Waiting"
        rects = []

        if totalFrames % config.get("skip_frames", 30) == 0:
            status = "Detecting"
            blob = cv2.dnn.blobFromImage(frame, 0.007843, (W, H), 127.5)
            net.setInput(blob)
            detections = net.forward()

            for i in np.arange(0, detections.shape[2]):
                confidence = detections[0, 0, i, 2]
                if confidence > config.get("confidence", 0.4):
                    idx = int(detections[0, 0, i, 1])
                    if CLASSES[idx] != "person":
                        continue

                    box = detections[0, 0, i, 3:7] * np.array([W, H, W, H])
                    startX, startY, endX, endY = box.astype("int")
                    rects.append((startX, startY, endX, endY))

        objects = ct.update(rects)

        for objectID, centroid in objects.items():
            to = trackableObjects.get(objectID, None)
            if to is None:
                to = TrackableObject(objectID, centroid)
            else:
                y = [c[1] for c in to.centroids]
                direction = centroid[1] - np.mean(y)
                to.centroids.append(centroid)

                if not to.counted:
                    if direction < 0 and centroid[1] < H // 2:
                        totalUp += 1
                        move_out.append(totalUp)
                        out_time.append(datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
                        to.counted = True
                    elif direction > 0 and centroid[1] > H // 2:
                        totalDown += 1
                        move_in.append(totalDown)
                        in_time.append(datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
                        if len(move_in) - len(move_out) >= config["Threshold"]:
                            logger.info("Sending alert email...")
                            threading.Thread(target=send_mail, daemon=True).start()
                        to.counted = True

            trackableObjects[objectID] = to
            text = f"ID {objectID}"
            cv2.putText(frame, text, (centroid[0] - 10, centroid[1] - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
            cv2.circle(frame, (centroid[0], centroid[1]), 4, (255, 255, 255), -1)

        info = [("Up", totalUp), ("Down", totalDown), ("Status", status)]
        for (i, (k, v)) in enumerate(info):
            text = f"{k}: {v}"
            cv2.putText(frame, text, (10, H - ((i * 20) + 20)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

        with lock:
            output_frame = frame.copy()

        totalFrames += 1
        fps.update()

    fps.stop()
    video_stream.release()

def generate_frames():
    """Yield frames for Flask."""
    global output_frame, lock
    while True:
        with lock:
            if output_frame is None:
                continue
            _, buffer = cv2.imencode(".jpg", output_frame)
            frame = buffer.tobytes()

        yield (b"--frame\r\n"
               b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")
