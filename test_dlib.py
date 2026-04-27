import cv2
import dlib
import face_recognition

video_capture = cv2.VideoCapture(0)
ret, frame = video_capture.read()
video_capture.release()

if ret:
    cv2.imwrite("test_temp.jpg", frame)
    img = dlib.load_rgb_image("test_temp.jpg")
    print("Image loaded by dlib successfully")

    try:
        locs = face_recognition.face_locations(img)
        print("Success! locs:", locs)
    except Exception as e:
        print("Failed:", e)
else:
    print("Could not read frame")
