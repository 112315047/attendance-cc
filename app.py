import os
import sys
import base64
import io
import numpy as np
import boto3
from decimal import Decimal
from datetime import datetime
from flask import Flask, request, jsonify, render_template
from PIL import Image

# ------------------------------------------------------------------
# 1. INITIALIZE FLASK & AWS (Rekognition + DynamoDB)
# ------------------------------------------------------------------
app = Flask(__name__)

# Initialize AWS Clients
rekognition = boto3.client('rekognition', region_name='us-east-1')
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')

COLLECTION_ID = 'attendance_collection'
table = dynamodb.Table('Users')
attendance_table = dynamodb.Table('Attendance')

# ------------------------------------------------------------------
# 2. HELPER FUNCTIONS
# ------------------------------------------------------------------
def decode_base64_image(base64_string):
    try:
        if "," in base64_string:
            base64_string = base64_string.split(",")[1]
            
        img_data = base64.b64decode(base64_string)
        image = Image.open(io.BytesIO(img_data))
        width, height = image.size
        
        # Rekognition requires jpeg or png byte arrays
        img_byte_arr = io.BytesIO()
        image.convert('RGB').save(img_byte_arr, format='JPEG')
        return img_byte_arr.getvalue(), width, height
    except Exception as e:
        print(f"Error decoding image: {e}")
        return None, None, None

# ------------------------------------------------------------------
# 3. API ENDPOINTS
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
    
    img_bytes, width, height = decode_base64_image(base64_image)
    if img_bytes is None:
        return jsonify({"error": "Invalid image"}), 400
        
    try:
        response = rekognition.index_faces(
            CollectionId=COLLECTION_ID,
            Image={'Bytes': img_bytes},
            ExternalImageId=str(roll),
            MaxFaces=1,
            QualityFilter="AUTO",
            DetectionAttributes=['DEFAULT']
        )
        
        if len(response['FaceRecords']) == 0:
            return jsonify({"error": "No face detected or quality too low"}), 400
            
        face_record = response['FaceRecords'][0]
        face_id = face_record['Face']['FaceId']
        bbox = face_record['Face']['BoundingBox']
        box = [
            int(bbox['Left'] * width),
            int(bbox['Top'] * height),
            int(bbox['Width'] * width),
            int(bbox['Height'] * height)
        ]
        
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    
    # Save to DynamoDB
    table.put_item(
        Item={
            'roll': str(roll),
            'name': str(name),
            'faceId': face_id
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
    
    img_bytes, width, height = decode_base64_image(base64_image)
    if img_bytes is None:
        return jsonify({"error": "Invalid image"}), 400
        
    try:
        response = rekognition.search_faces_by_image(
            CollectionId=COLLECTION_ID,
            Image={'Bytes': img_bytes},
            MaxFaces=1,
            FaceMatchThreshold=85.0
        )
        
        if len(response['FaceMatches']) == 0:
            # Let's detect face to return bounding box at least
            detect_res = rekognition.detect_faces(Image={'Bytes': img_bytes})
            if len(detect_res['FaceDetails']) > 0:
                bbox = detect_res['FaceDetails'][0]['BoundingBox']
                box = [
                    int(bbox['Left'] * width),
                    int(bbox['Top'] * height),
                    int(bbox['Width'] * width),
                    int(bbox['Height'] * height)
                ]
                return jsonify({"status": "fail", "box": box})
            else:
                return jsonify({"error": "No face detected"}), 400
                
        match = response['FaceMatches'][0]
        matched_roll = match['Face']['ExternalImageId']
        best_score = match['Similarity'] / 100.0 # to match previous 0-1 scale format
        
        bbox = response['SearchedFaceBoundingBox']
        box = [
            int(bbox['Left'] * width),
            int(bbox['Top'] * height),
            int(bbox['Width'] * width),
            int(bbox['Height'] * height)
        ]
        
    except Exception as e:
        if 'No faces in image' in str(e):
            return jsonify({"error": "No face detected"}), 400
        return jsonify({"error": str(e)}), 400
        
    best_match = None
    try:
        user_record = table.get_item(Key={'roll': matched_roll})
        if 'Item' in user_record:
            best_match = user_record['Item']['name']
        else:
            best_match = "Unknown"
    except Exception as e:
        return jsonify({"error": "Failed to fetch from database", "details": str(e)}), 500
            
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
        # Get faceId from dynamoDB first
        user_record = table.get_item(Key={'roll': str(roll)})
        if 'Item' in user_record and 'faceId' in user_record['Item']:
            face_id = user_record['Item']['faceId']
            # Delete from Rekognition
            rekognition.delete_faces(
                CollectionId=COLLECTION_ID,
                FaceIds=[face_id]
            )
            
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
    # Running locally without HTTPS to prevent browser warnings.
    # Localhost automatically allows webcam access without HTTPS.
    app.run(debug=True, host='0.0.0.0', port=5000)
