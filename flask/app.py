from flask import Flask, render_template, Response, jsonify
import cv2
import imutils
from tracker.centroidtracker import CentroidTracker
from tracker.trackableobject import TrackableObject
import numpy as np
import datetime
import time

app = Flask(__name__)

# 비디오 파일 경로 또는 웹캠 설정
video_path = r"C:\FaceGate\flask\utils\data\tests\test_1.mp4"  # 비디오 파일 경로
video_stream = cv2.VideoCapture(video_path)  # 영상 파일 스트림 초기화

# MobileNet SSD 모델 로드
prototxt_path = "detector/MobileNetSSD_deploy.prototxt"
model_path = "detector/MobileNetSSD_deploy.caffemodel"
net = cv2.dnn.readNetFromCaffe(prototxt_path, model_path)

# 클래스 레이블 초기화
CLASSES = ["background", "aeroplane", "bicycle", "bird", "boat",
           "bottle", "bus", "car", "cat", "chair", "cow", "diningtable",
           "dog", "horse", "motorbike", "person", "pottedplant", "sheep",
           "sofa", "train", "tvmonitor"]

# Centroid Tracker 및 변수 초기화
ct = CentroidTracker(maxDisappeared=40, maxDistance=50)
trackableObjects = {}
detected_times = []  # 두 명 이상 탐지된 시간 기록

# 두 명 이상 탐지 상태를 위한 타이머 변수
detection_start_time = None  # 두 명 이상 상태가 시작된 시점
is_recorded = False  # 동일 상태에서 중복 기록 방지
detection_duration_threshold = 3  # 지속 시간 기준 (초)

def generate_frames():
    global video_stream, net, ct, trackableObjects, detected_times, detection_start_time, is_recorded

    while True:
        success, frame = video_stream.read()
        if not success:
            # 비디오 파일 끝났을 경우 다시 시작
            video_stream.set(cv2.CAP_PROP_POS_FRAMES, 0)
            continue

        # 프레임 크기 조정
        frame = imutils.resize(frame, width=600)
        (H, W) = frame.shape[:2]

        # MobileNet SSD로 객체 탐지
        blob = cv2.dnn.blobFromImage(frame, 0.007843, (W, H), 127.5)
        net.setInput(blob)
        detections = net.forward()

        rects = []

        # 탐지 결과 반복 처리
        for i in np.arange(0, detections.shape[2]):
            confidence = detections[0, 0, i, 2]
            if confidence > 0.4:  # 신뢰도가 0.4 이상인 경우만
                idx = int(detections[0, 0, i, 1])
                if CLASSES[idx] != "person":
                    continue

                # 경계 상자 계산
                box = detections[0, 0, i, 3:7] * np.array([W, H, W, H])
                (startX, startY, endX, endY) = box.astype("int")
                rects.append((startX, startY, endX, endY))

                # 사람 표시를 위해 사각형 그리기
                cv2.rectangle(frame, (startX, startY), (endX, endY), (0, 255, 0), 2)
                cv2.putText(frame, "Person", (startX, startY - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

        # Centroid Tracker로 객체 추적
        objects = ct.update(rects)

        # 현재 화면에 있는 사람 수를 계산
        current_count = len(objects)

        # 두 명 이상이 화면에 있을 때만 기록
        if current_count >= 2:
            if detection_start_time is None:
                detection_start_time = time.time()  # 두 명 이상 상태 시작 시간 기록

            # 두 명 이상 상태가 지속되었는지 확인
            elapsed_time = time.time() - detection_start_time
            if elapsed_time >= detection_duration_threshold and not is_recorded:
                current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                detected_times.append(current_time)
                is_recorded = True  # 상태가 기록되었음을 표시
        else:
            # 두 명 미만 상태로 전환되면 타이머와 기록 플래그 초기화
            detection_start_time = None
            is_recorded = False

        # 프레임을 JPEG로 변환
        _, buffer = cv2.imencode('.jpg', frame)
        frame = buffer.tobytes()

        # HTTP 스트리밍
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@app.route('/video_feed')
def video_feed():
    """비디오 스트리밍 라우트"""
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/detections')
def detections():
    """감지된 시간 데이터 반환"""
    return jsonify(detected_times)

@app.route('/')
def index():
    """기본 페이지"""
    return render_template('index.html', detections=detected_times)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
