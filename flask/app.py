from flask import Flask, render_template, Response, jsonify
from flask_socketio import SocketIO, emit
import cv2
import imutils
import numpy as np
import datetime
import time
from collections import deque

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# 클래스 정의
CLASSES = ["background", "aeroplane", "bicycle", "bird", "boat",
           "bottle", "bus", "car", "cat", "chair", "cow", "diningtable",
           "dog", "horse", "motorbike", "person", "pottedplant", "sheep",
           "sofa", "train", "tvmonitor"]

# 전역 변수 초기화
class DetectionState:
    def __init__(self):
        self.current_count = 0
        self.detection_log = deque(maxlen=100)  # 최근 100개의 기록만 유지
        self.last_detection_time = None
        self.detection_cooldown = 5  # 같은 이벤트 기록 사이의 최소 시간(초)
        self.is_currently_detecting = False
        self.hourly_data = [0] * 24  # 시간별 최대 감지 수

state = DetectionState()

def init_camera():
    """카메라 초기화 함수"""
    try:
        cam = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        if cam.isOpened():
            cam.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            cam.set(cv2.CAP_PROP_FPS, 30)
            ret, frame = cam.read()
            if ret:
                print("카메라 초기화 성공")
                return cam
            
        print("카메라 초기화 실패")
        if cam is not None:
            cam.release()
    except Exception as e:
        print(f"카메라 초기화 에러: {e}")
    return None

# 카메라 초기화
video_stream = init_camera()
if video_stream is None:
    raise ValueError("카메라를 찾을 수 없습니다")

# 모델 초기화
try:
    net = cv2.dnn.readNetFromCaffe(
        "detector/MobileNetSSD_deploy.prototxt",
        "detector/MobileNetSSD_deploy.caffemodel"
    )
    print("모델 로드 성공")
except Exception as e:
    raise ValueError(f"모델 로드 실패: {e}")

def add_detection_log(count):
    """감지 로그 추가 함수"""
    current_time = time.time()
    
    # 첫 감지이거나 마지막 감지로부터 일정 시간이 지났을 때만 기록
    if (state.last_detection_time is None or 
        current_time - state.last_detection_time >= state.detection_cooldown):
        
        log_entry = {
            'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'count': count,
            'status': '다수 인원 감지' if count >= 2 else '정상'
        }
        
        state.detection_log.appendleft(log_entry)
        state.last_detection_time = current_time
        
        # 웹소켓으로 새로운 감지 정보 전송
        socketio.emit('new_detection', log_entry)

        # 시간별 데이터 업데이트
        current_hour = datetime.datetime.now().hour
        state.hourly_data[current_hour] = max(state.hourly_data[current_hour], count)

def draw_detection_box(frame, box, confidence):
    """감지된 객체에 박스 그리기"""
    (startX, startY, endX, endY) = box
    
    # 박스 그리기
    cv2.rectangle(frame, (startX, startY), (endX, endY), (0, 255, 0), 2)
    
    # 반투명한 오버레이 추가
    overlay = frame.copy()
    cv2.rectangle(overlay, (startX, startY - 30), (endX, startY), (0, 255, 0), -1)
    cv2.addWeighted(overlay, 0.3, frame, 0.7, 0, frame)
    
    # 신뢰도 텍스트 추가
    confidence_text = f"{confidence * 100:.0f}%"
    cv2.putText(frame, confidence_text, (startX + 5, startY - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)

def generate_frames():
    """프레임 생성 및 객체 감지 함수"""
    global video_stream
    
    try:
        while True:
            # 카메라 연결 확인
            if not video_stream.isOpened():
                print("카메라 재연결 시도")
                video_stream = init_camera()
                if video_stream is None:
                    print("카메라 재연결 실패")
                    time.sleep(5)  # 재시도 전 대기
                    continue

            success, frame = video_stream.read()
            if not success:
                print("프레임 읽기 실패")
                continue

            # 프레임 크기 조정
            frame = imutils.resize(frame, width=800)
            (H, W) = frame.shape[:2]

            # 이미지 전처리
            blob = cv2.dnn.blobFromImage(
                frame, 
                scalefactor=1.0/255.0,
                size=(300, 300),
                mean=(127.5, 127.5, 127.5),
                swapRB=True
            )

            # 객체 감지 수행
            net.setInput(blob)
            detections = net.forward()
            
            # 감지된 사람 수 카운트 및 박스 정보 저장
            person_count = 0
            boxes = []
            confidences = []

            # 감지 결과 처리
            for i in range(detections.shape[2]):
                confidence = detections[0, 0, i, 2]

                if confidence > 0.5:
                    class_id = int(detections[0, 0, i, 1])
                    
                    if class_id == CLASSES.index('person'):
                        person_count += 1
                        box = detections[0, 0, i, 3:7] * np.array([W, H, W, H])
                        (startX, startY, endX, endY) = box.astype("int")
                        
                        if startX >= 0 and startY >= 0 and endX <= W and endY <= H:
                            boxes.append((startX, startY, endX, endY))
                            confidences.append(float(confidence))

            # 상태 업데이트
            state.current_count = person_count
            if person_count >= 2:
                if not state.is_currently_detecting:
                    add_detection_log(person_count)
                    state.is_currently_detecting = True
            else:
                state.is_currently_detecting = False

            # 객체 표시
            for box, confidence in zip(boxes, confidences):
                draw_detection_box(frame, box, confidence)

            # 전체 감지 인원 표시
            cv2.putText(frame, f"Detected: {person_count}", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

            # 실시간 데이터 전송
            socketio.emit('update_data', {
                'current_count': person_count,
                'hourly_data': state.hourly_data,
                'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })

            # 프레임 인코딩
            _, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()

            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

    except Exception as e:
        print(f"Error in generate_frames: {e}")
        if video_stream is not None:
            video_stream.release()

@app.route('/')
def index():
    """메인 페이지"""
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    """비디오 스트림 제공"""
    return Response(generate_frames(),
                   mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/get_logs')
def get_logs():
    """감지 로그 데이터 제공"""
    return jsonify(list(state.detection_log))

@app.route('/get_current_state')
def get_current_state():
    """현재 상태 데이터 제공"""
    return jsonify({
        'current_count': state.current_count,
        'hourly_data': state.hourly_data,
        'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })

@socketio.on('connect')
def handle_connect():
    """클라이언트 연결 시 현재 상태 전송"""
    print('Client connected')
    emit('update_data', {
        'current_count': state.current_count,
        'hourly_data': state.hourly_data,
        'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })

@app.route('/reset_logs', methods=['POST'])
def reset_logs():
    """감지 로그 초기화"""
    state.detection_log.clear()
    state.hourly_data = [0] * 24
    state.last_detection_time = None
    state.is_currently_detecting = False
    socketio.emit('logs_reset')  # 프론트엔드에 초기화 알림
    return jsonify({"status": "success"})

if __name__ == '__main__':
    try:
        socketio.run(app, host='0.0.0.0', port=5000, debug=False)
    finally:
        if video_stream is not None:
            video_stream.release()