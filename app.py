import os
import sys
import base64
import urllib.request
import ssl
import numpy as np
import cv2
import boto3
from decimal import Decimal
from datetime import datetime
from flask import Flask, request, jsonify, render_template

# ------------------------------------------------------------------
# 1. SETUP: DOWNLOAD ONNX MODELS IF MISSING
# ------------------------------------------------------------------
DETECTOR_URL = "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
RECOGNIZER_URL = "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx"
DETECTOR_MODEL = "face_detection_yunet.onnx"
RECOGNIZER_MODEL = "face_recognition_sface.onnx"

def download_model(url, filename):
    if not os.path.exists(filename):
        print(f"Downloading {filename}...")
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        try:
            with urllib.request.urlopen(url, context=ctx) as response, open(filename, 'wb') as out_file:
                out_file.write(response.read())
        except Exception as e:
            print(f"Error downloading {filename}: {e}")
            sys.exit(1)

os.environ.pop("CURL_CA_BUNDLE", None)
os.environ.pop("REQUESTS_CA_BUNDLE", None)

download_model(DETECTOR_URL, DETECTOR_MODEL)
download_model(RECOGNIZER_URL, RECOGNIZER_MODEL)

# ------------------------------------------------------------------
# 2. INITIALIZE FLASK, OPENCV & DYNAMODB
# ------------------------------------------------------------------
app = Flask(__name__)

detector = cv2.FaceDetectorYN.create(
    model=DETECTOR_MODEL,
    config="",
    input_size=(320, 320),
    score_threshold=0.8,
    nms_threshold=0.3,
    top_k=5000
)

recognizer = cv2.FaceRecognizerSF.create(model=RECOGNIZER_MODEL, config="")

# Initialize AWS DynamoDB
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
table = dynamodb.Table('Users')
attendance_table = dynamodb.Table('Attendance')

# ------------------------------------------------------------------
# 3. HELPER FUNCTIONS
# ------------------------------------------------------------------
def decode_base64_image(base64_string):
    try:
        if "," in base64_string:
            base64_string = base64_string.split(",")[1]
            
        img_data = base64.b64decode(base64_string)
        np_arr = np.frombuffer(img_data, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        return img
    except Exception:
        return None

def process_face(img):
    height, width, _ = img.shape
    detector.setInputSize((width, height))
    
    status, faces = detector.detect(img)
    
    if faces is None or len(faces) == 0:
        return None, None, "No face detected"
    
    if len(faces) > 1:
        return None, None, "Multiple faces detected"
        
    face = faces[0]
    box = [int(x) for x in face[:4]] # x, y, width, height
    
    aligned_face = recognizer.alignCrop(img, face)
    feature = recognizer.feature(aligned_face)
    
    return feature, box, None

# ------------------------------------------------------------------
# 4. API ENDPOINTS
# ------------------------------------------------------------------

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    if not data or 'name' not in data or 'roll' not in data or 'image' not in data:
        return jsonify({"error": "Missing required fields"}), 400
        
    name = data['name']
    roll = data['roll']
    base64_image = data['image']
    
    img = decode_base64_image(base64_image)
    if img is None:
        return jsonify({"error": "Invalid image"}), 400
        
    feature, box, error = process_face(img)
    if error:
        return jsonify({"error": error}), 400
        
    feature_list = [Decimal(str(x)) for x in feature.flatten().tolist()]
    
    table.put_item(
        Item={
            'roll': str(roll),
            'name': str(name),
            'feature': feature_list
        }
    )
    
    return jsonify({"status": "registered", "box": box})

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data or 'image' not in data:
        return jsonify({"error": "Missing required field"}), 400
        
    base64_image = data['image']
    auto_mark = data.get('auto_mark', False) # True if auto-scanning
    
    img = decode_base64_image(base64_image)
    if img is None:
        return jsonify({"error": "Invalid image"}), 400
        
    test_feature, box, error = process_face(img)
    if error:
        return jsonify({"error": error}), 400
        
    best_match = None
    matched_roll = None
    best_score = 0.0
    MATCH_THRESHOLD = 0.363 
    
    try:
        response = table.scan()
        users = response.get('Items', [])
    except Exception as e:
        return jsonify({"error": "Failed to fetch from database", "details": str(e)}), 500
    
    for user_data in users:
        ref_feature = np.array([float(x) for x in user_data["feature"]], dtype=np.float32).reshape(1, -1)
        score = recognizer.match(ref_feature, test_feature, cv2.FaceRecognizerSF_FR_COSINE)
        
        if score >= MATCH_THRESHOLD and score > best_score:
            best_score = score
            best_match = user_data["name"]
            matched_roll = user_data.get("roll", "Unknown")
            
    if best_match:
        if auto_mark:
            now = datetime.now()
            current_date = now.strftime('%Y-%m-%d')
            current_time = now.strftime('%H:%M:%S')

            try:
                attendance_record = attendance_table.get_item(Key={'roll': matched_roll, 'date': current_date})
                if 'Item' in attendance_record:
                    return jsonify({
                        "status": "duplicate",
                        "name": best_match,
                        "message": "Already marked today",
                        "box": box,
                        "confidence": float(best_score)
                    })
                
                attendance_table.put_item(
                    Item={
                        'roll': matched_roll,
                        'date': current_date,
                        'name': best_match,
                        'timestamp': current_time,
                        'status': 'present'
                    }
                )
                
                return jsonify({
                    "status": "success", 
                    "name": best_match,
                    "timestamp": current_time,
                    "confidence": float(best_score),
                    "box": box
                })
                
            except Exception as e:
                return jsonify({"error": "Attendance logging failed", "details": str(e)}), 500
        else:
            # Just verify, don't mark
            return jsonify({
                "status": "success", 
                "name": best_match,
                "confidence": float(best_score),
                "box": box
            })
            
    else:
        return jsonify({"status": "fail", "box": box})

@app.route('/users', methods=['GET'])
def get_users():
    try:
        response = table.scan()
        users = response.get('Items', [])
        safe_users = [{"roll": u.get("roll"), "name": u.get("name")} for u in users]
        return jsonify(safe_users)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/user/<roll>', methods=['DELETE'])
def delete_user(roll):
    try:
        table.delete_item(Key={'roll': str(roll)})
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/reset_attendance', methods=['POST'])
def reset_attendance():
    try:
        scan = attendance_table.scan()
        with attendance_table.batch_writer() as batch:
            for each in scan.get('Items', []):
                batch.delete_item(Key={'roll': each['roll'], 'date': each['date']})
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/attendance', methods=['GET'])
def get_attendance():
    try:
        response = attendance_table.scan()
        records = response.get('Items', [])
        records.sort(key=lambda x: f"{x.get('date')} {x.get('timestamp')}", reverse=True)
        return jsonify(records)
    except Exception as e:
        return jsonify({"error": "Failed to fetch attendance records"}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
