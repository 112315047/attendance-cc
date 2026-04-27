import cv2
import sys
import os
import urllib.request
import ssl
import numpy as np

# URLs for OpenCV's official face detection and recognition AI models
DETECTOR_URL = "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
RECOGNIZER_URL = "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx"
DETECTOR_MODEL = "face_detection_yunet.onnx"
RECOGNIZER_MODEL = "face_recognition_sface.onnx"

def download_model(url, filename):
    if not os.path.exists(filename):
        print(f"Downloading AI model {filename} (this is a one-time setup)...")
        # Bypass SSL verification issues to prevent corporate proxies/PostgreSQL from blocking the download
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        try:
            with urllib.request.urlopen(url, context=ctx) as response, open(filename, 'wb') as out_file:
                out_file.write(response.read())
            print(f"Successfully downloaded {filename}")
        except Exception as e:
            print(f"Failed to download {filename}: {e}")
            sys.exit(1)

def main():
    # Fix environment variables that might block downloads
    os.environ.pop("CURL_CA_BUNDLE", None)
    os.environ.pop("REQUESTS_CA_BUNDLE", None)

    # 1. Download the required AI models if missing
    download_model(DETECTOR_URL, DETECTOR_MODEL)
    download_model(RECOGNIZER_URL, RECOGNIZER_MODEL)

    print("Initializing AI models...")
    # Initialize the YuNet face detector
    detector = cv2.FaceDetectorYN.create(
        model=DETECTOR_MODEL,
        config="",
        input_size=(320, 320), # Will dynamically adjust to camera resolution
        score_threshold=0.8,
        nms_threshold=0.3,
        top_k=5000
    )

    # Initialize the SFace face recognizer
    recognizer = cv2.FaceRecognizerSF.create(
        model=RECOGNIZER_MODEL,
        config=""
    )

    print("Initializing camera...")
    video_capture = cv2.VideoCapture(0)
    if not video_capture.isOpened():
        print("Error: Could not open webcam.")
        sys.exit(1)

    reference_feature = None

    print("\n" + "="*40)
    print("Step 1: Capture Reference Face")
    print("Look at the camera and press 's' to save your face.")
    print("Press 'q' to quit.")
    print("="*40)

    # Step 1: Capture Reference
    while True:
        ret, frame = video_capture.read()
        if not ret or frame is None:
            continue

        height, width, _ = frame.shape
        detector.setInputSize((width, height))

        # Show the camera feed
        cv2.imshow('Camera - Press "s" to save reference face, "q" to quit', frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('s'):
            # Detect faces
            status, faces = detector.detect(frame)
            if faces is not None and len(faces) > 0:
                face = faces[0] # Take the first detected face
                
                # Align and crop the face for the recognizer
                aligned_face = recognizer.alignCrop(frame, face)
                
                # Extract the 128D feature vector
                reference_feature = recognizer.feature(aligned_face)
                print("Reference face captured and encoded successfully!")
                break
            else:
                print("No face detected. Please ensure your face is visible and try again.")
        elif key == ord('q'):
            video_capture.release()
            cv2.destroyAllWindows()
            sys.exit(0)

    cv2.destroyAllWindows()

    print("\n" + "="*40)
    print("Step 2: Capture Test Face for Comparison")
    print("Look at the camera and press 'c' to capture and compare.")
    print("Press 'q' to quit.")
    print("="*40)

    # Step 2: Compare
    while True:
        ret, frame = video_capture.read()
        if not ret or frame is None:
            continue

        height, width, _ = frame.shape
        detector.setInputSize((width, height))

        cv2.imshow('Camera - Press "c" to compare, "q" to quit', frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('c'):
            status, faces = detector.detect(frame)
            if faces is not None and len(faces) > 0:
                face = faces[0]
                aligned_face = recognizer.alignCrop(frame, face)
                test_feature = recognizer.feature(aligned_face)
                
                print("\nComparing faces...")
                # Compare the two faces using Cosine Similarity
                # OpenCV SFace uses 0.363 as the standard threshold for matching identities
                score = recognizer.match(reference_feature, test_feature, cv2.FaceRecognizerSF_FR_COSINE)
                
                if score >= 0.363:
                    print(f">>> Result: Match! It is the same person. (Confidence Score: {score:.3f}) <<<")
                else:
                    print(f">>> Result: Not Match. Different person. (Confidence Score: {score:.3f}) <<<")
                break
            else:
                print("No face detected in the test image. Please try again.")
        elif key == ord('q'):
            break

    # Clean up
    video_capture.release()
    cv2.destroyAllWindows()
    print("\nDone.")

if __name__ == "__main__":
    main()
