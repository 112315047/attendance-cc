# Smart Attendance Tracker

A cloud-native, modern web application that uses highly accurate facial recognition to identify users and automate attendance tracking. 

## ✨ Features

- **High-Accuracy Facial Recognition**: Powered by AWS Rekognition to securely and quickly identify faces.
- **Cloud Database Integration**: Secure, scalable storage of user data and attendance records using AWS DynamoDB.
- **Interactive Web Dashboard**: A beautiful, dynamic UI built with HTML/CSS/JS for registering users, scanning faces, and viewing attendance logs in real-time.
- **Auto-Scanning Mode**: Supports continuous webcam scanning for hands-free, seamless attendance marking at a kiosk or entryway.
- **Admin Controls**: Manage enrolled users and reset attendance logs directly from the dashboard.

---

## 🏗 Architecture

- **Backend**: Python, Flask
- **Frontend**: HTML5, Vanilla CSS, Vanilla JavaScript
- **AI / Computer Vision**: AWS Rekognition
- **Database**: AWS DynamoDB

---

## 🚀 Setup & Installation

### Prerequisites
1. **Python 3.8+** installed on your machine.
2. **AWS Account** with configured credentials. You must have your AWS access keys set up on your machine (usually in `~/.aws/credentials`) with permissions for `Rekognition` and `DynamoDB`.

### 1. Install Dependencies
Ensure you have the required Python packages installed in your environment:
```bash
pip install flask boto3 Pillow numpy opencv-python
```

### 2. Initialize AWS Resources
Before running the application for the first time, you must initialize the cloud infrastructure. Run the following setup scripts to create your DynamoDB tables and Rekognition face collection:

```bash
# Creates the 'attendance_collection' in AWS Rekognition
python create_collection.py

# Creates the 'Users' table in AWS DynamoDB
python create_table.py

# Creates the 'Attendance' table in AWS DynamoDB
python create_attendance.py
```

### 3. Run the Application
Start the Flask development server:
```bash
python app.py
```

Once the server is running, open your web browser and navigate to:
**`http://localhost:5000`**

---

## 📁 Project Structure

- **`app.py`**: The core Flask backend that routes API requests, communicates with AWS, and serves the frontend.
- **`create_collection.py`**: Script to initialize the AWS Rekognition collection.
- **`create_table.py` / `create_attendance.py`**: Scripts to initialize DynamoDB tables.
- **`templates/dashboard.html`**: The main HTML layout.
- **`static/`**: Contains all styling (`styles.css`) and client-side logic (`dashboard.js`, `script.js`).
- **`face_compare.py` / `test_dlib.py`**: Legacy scripts used for previous local ONNX/OpenCV-based face detection implementations.

---

## 💡 Usage Guide

1. **Register User**: Click on the "Register" section, enter the user's Name and Roll Number, and take a picture using the webcam to enroll them into the cloud database.
2. **Mark Attendance**: Go to the "Mark Attendance" section. You can either capture a single frame or toggle **Auto Scan** for continuous recognition.
3. **View Logs**: The dashboard will display a real-time list of today's attendance logs, matched names, and confidence scores.
