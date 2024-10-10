from kivy.uix.image import Image
from kivy.graphics.texture import Texture
from kivy.clock import Clock
from kivymd.app import MDApp
from kivymd.uix.screen import MDScreen
from kivymd.uix.button import MDRaisedButton
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.label import MDLabel
from kivymd.uix.toolbar import MDTopAppBar
from kivy.metrics import dp
from kivy.uix.screenmanager import ScreenManager, SlideTransition
from kivy.uix.camera import Camera
from kivy.graphics import Color, Ellipse, Line, StencilPush, StencilUse, StencilPop, StencilUnUse, Rectangle
from kivy.core.window import Window
import face_recognition
import firebase_admin
from firebase_admin import credentials, initialize_app, storage, db
import cv2
import numpy as np
from PIL import Image as PILImage
import os
import requests
from io import BytesIO
from kivymd.toast import toast
import dlib
from threading import Thread

class CircularCamera(Camera):
    def __init__(self, **kwargs):
        super(CircularCamera, self).__init__(**kwargs)
        self.bind(size=self._update_canvas)
        Window.bind(on_resize=self.on_window_resize)

    def on_window_resize(self, instance, width, height):
        self.size = (min(width, height) * 0.8, min(width, height) * 0.8)
        self.pos_hint = {'center_x': 0.5, 'center_y': 0.6}

    def _update_canvas(self, *args):
        self.canvas.clear()
        with self.canvas:
            StencilPush()
            Color(1, 1, 1, 1)
            Ellipse(pos=self.pos, size=self.size)
            StencilUse()
            Color(1, 1, 1, 1)
            self._draw_texture_in_circle()
            StencilUnUse()
            StencilPop()
            Color(0, 0.7, 1, 1)
            border_width = dp(4)
            Line(circle=(self.center_x, self.center_y, min(self.width, self.height) / 2), width=border_width)

    def _draw_texture_in_circle(self):
        if self.texture:
            Rectangle(texture=self.texture, pos=self.pos, size=self.size)

    def on_texture(self, *args):
        self._update_canvas()

class FacialRecognition(MDScreen):
    def __init__(self, **kwargs):
        super(FacialRecognition, self).__init__(**kwargs)
        self.camera = None
        self.face_detector = dlib.get_frontal_face_detector()
        self.predictor = dlib.shape_predictor("./shape_predictor_68_face_landmarks.dat")

        # Define blink thresholds and counters
        self.blink_threshold = 0.3
        self.consecutive_frames = 2
        self.blink_counter = 0
        self.total_blinks = 0
        self.frames_without_blink = 0

        self.frame_counter = 0
        self._setup_ui()
        
    def update_fields(self, school_name, type_of, role, username):
        self.fields = {
            "SchoolName": school_name,
            "TypeOf": type_of,
            "role": role,
            "userName": username,
        }   
        print(type_of, school_name, role, username)

    def _setup_ui(self):
        self.layout = MDBoxLayout(orientation='vertical', spacing=dp(10), padding=dp(20))

        self.top_bar = MDTopAppBar(
            title="Facial Recognition",
            left_action_items=[["arrow-left", lambda x: self.go_back()]],
            pos_hint={"top": 1},
            elevation=10
        )
        self.add_widget(self.top_bar)

        self.camera_layout = MDBoxLayout(size_hint=(1, 0.7))
        self.layout.add_widget(self.camera_layout)

        self.status_label = MDLabel(
            text="Place your face in the frame",
            halign="center",
            size_hint_y=None,
            height=dp(50)
        )
        self.layout.add_widget(self.status_label)

        self.recognize_button = MDRaisedButton(
            text="Recognize",
            pos_hint={'center_x': 0.5},
            size_hint=(None, None),
            size=(dp(200), dp(50)),
            on_release=self.perform_frs,
            disabled=True
        )
        self.layout.add_widget(self.recognize_button)

        self.add_widget(self.layout)

    def go_back(self):
        self.stop_camera()
        self.manager.transition = SlideTransition(direction="right")
        self.manager.current = 'school_teacher_myAttendance'

    def start_camera(self):
        if not self.camera:
            self.camera = CircularCamera(play=True, resolution=(640, 480))
            self.camera.size_hint = (None, None)
            self.camera.size = (dp(300), dp(300))
            self.camera.pos_hint = {'center_x': 0.5, 'center_y': 0.5}
            self.camera_layout.add_widget(self.camera)
        else:
            self.camera.play = True
        Clock.schedule_interval(self.update_camera, 1.0 / 30.0)

    def stop_camera(self):
        if self.camera:
            Clock.unschedule(self.update_camera)
            self.camera.play = False
            self.camera_layout.remove_widget(self.camera)
            self.camera = None

    def eye_aspect_ratio(self, eye):
        A = np.linalg.norm(eye[1] - eye[5])
        B = np.linalg.norm(eye[2] - eye[4])
        C = np.linalg.norm(eye[0] - eye[3])
        ear = (A + B) / (2.0 * C)
        return ear

    def detect_blink(self, gray, rect):
        shape = self.predictor(gray, rect)
        shape_np = np.array([[p.x, p.y] for p in shape.parts()])

        left_eye = shape_np[36:42]
        right_eye = shape_np[42:48]

        left_ear = self.eye_aspect_ratio(left_eye)
        right_ear = self.eye_aspect_ratio(right_eye)
        avg_ear = (left_ear + right_ear) / 2.0

        if avg_ear < self.blink_threshold:
            self.blink_counter += 1
        else:
            if self.blink_counter >= self.consecutive_frames:
                self.total_blinks += 1
            self.blink_counter = 0

        return avg_ear, self.blink_counter > self.consecutive_frames
    
    def update_camera(self, dt):
        if self.camera and self.camera.texture:
            # Get the current frame from the camera
            frame = self.get_frame()
            if frame is not None:
                # Convert the frame to grayscale for face detection and blink detection
                gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

                # Detect faces in the grayscale frame
                rects = self.face_detector(gray_frame, 0)

                # If any face is detected
                if rects:
                    self.status_label.text = "Face detected. Checking conditions..."

                    blink_detected = False
                    # Iterate through all detected faces (rects)
                    for rect in rects:
                        _, blink_detected = self.detect_blink(gray_frame, rect)
                        if blink_detected:
                            self.frames_without_blink = 0
                            self.status_label.text = "Blink detected. Proceeding with face recognition."
                            self.recognize_button.disabled = False
                            self.recognize_button.md_bg_color = self.theme_cls.primary_color
                            break
                        else:
                            self.frames_without_blink += 1

                    # Anti-spoofing check (if no blinks detected after several frames)
                    if not blink_detected:
                        if self.frames_without_blink > 30:
                            self.status_label.text = "Anti-spoofing check failed. No blinks detected."
                            self.recognize_button.disabled = True
                            self.recognize_button.md_bg_color = self.theme_cls.disabled_hint_text_color
                        return

                    # Get the coordinates of the first detected face
                    rect = rects[0]
                    (x, y, w, h) = (rect.left(), rect.top(), rect.width(), rect.height())

                    # Calculate the center of the detected face
                    face_center_x = x + w // 2
                    face_center_y = y + h // 2

                    # Calculate the center of the camera frame
                    frame_center_x = frame.shape[1] // 2
                    frame_center_y = frame.shape[0] // 2

                    # Define tolerance for face positioning
                    tolerance = 50

                    # Check if the face is centered within the tolerance range
                    if abs(face_center_x - frame_center_x) > tolerance or abs(face_center_y - frame_center_y) > tolerance:
                        self.status_label.text = "Please adjust your position so your face is centered in the frame."
                        self.recognize_button.disabled = True
                        self.recognize_button.md_bg_color = self.theme_cls.disabled_hint_text_color
                        return

                    # Calculate average brightness of the frame (used for lighting conditions)
                    avg_brightness = np.mean(gray_frame)

                    # Check for poor lighting conditions
                    if avg_brightness < 50:
                        self.status_label.text = "Lighting is too dark. Please move to a brighter area or turn on a light."
                        self.recognize_button.disabled = True
                        self.recognize_button.md_bg_color = self.theme_cls.disabled_hint_text_color
                        return
                    elif avg_brightness > 200:
                        self.status_label.text = "Lighting is too bright. Please reduce the lighting or move to a shaded area."
                        self.recognize_button.disabled = True
                        self.recognize_button.md_bg_color = self.theme_cls.disabled_hint_text_color
                        return

                    # If everything is fine, update the status and enable the recognition button
                    self.status_label.text = "Face detected. You can now capture the image."
                    self.recognize_button.disabled = False
                    self.recognize_button.md_bg_color = self.theme_cls.primary_color

                # If no face is detected
                else:
                    self.status_label.text = "No face detected. Please ensure your face is visible in the camera frame."
                    self.recognize_button.disabled = True
                    self.recognize_button.md_bg_color = self.theme_cls.disabled_hint_text_color


    def get_frame(self):
        if not self.camera or not self.camera.texture:
            return None
        try:
            texture = self.camera.texture
            size = texture.size
            pixels = texture.pixels

            mode = 'RGBA' if len(pixels) == size[0] * size[1] * 4 else 'RGB'
            pil_image = PILImage.frombytes(mode=mode, size=size, data=pixels)
            opencv_image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGBA2BGR)

            return opencv_image
        except Exception as e:
            print(f"Error getting frame from camera: {str(e)}")
            return None

    def on_enter(self):
        self.start_camera()

    def on_leave(self):
        self.stop_camera()

    def perform_frs(self, instance):
        # Retrieve the user information fields
        typeof = self.fields['TypeOf']
        schoolName = self.fields["SchoolName"]
        role = self.fields["role"]
        username = self.fields["userName"]

        try:
            # Fetch user data from the database using Firebase reference
            ref = db.reference(f'{typeof}/{schoolName}/{role}s/{username}')
            user_data = ref.get()
            
            if user_data is None:
                raise ValueError("User data not found in the database")
            
            stored_img_url = user_data.get('image_url')
            if stored_img_url is None:
                raise ValueError("Image URL not found in user data")

            # Download the image from the URL
            response = requests.get(stored_img_url)
            image_data = BytesIO(response.content)
            stored_image = PILImage.open(image_data).convert('RGB')

            # Convert the stored image to OpenCV format
            opencv_image = cv2.cvtColor(np.array(stored_image), cv2.COLOR_RGB2BGR)

            # Convert the image to RGB format for face recognition
            rgb_image = cv2.cvtColor(opencv_image, cv2.COLOR_BGR2RGB)
            
            # Detect face locations in the stored image
            face_locations = face_recognition.face_locations(rgb_image, model="hog")
            if len(face_locations) == 0:
                raise ValueError("No face found in the stored image")

            # Get the face encoding of the stored image
            stored_face_encoding = face_recognition.face_encodings(rgb_image, face_locations)[0]
            
            # Get the current frame from the camera
            current_frame = self.get_frame()
            rgb_current_frame = cv2.cvtColor(current_frame, cv2.COLOR_BGR2RGB)

            # Detect face locations in the current frame
            current_face_locations = face_recognition.face_locations(rgb_current_frame, model="hog")
            if len(current_face_locations) == 0:
                self.status_label.text = "No face detected in the current frame."
                return

            # Get the face encoding of the current frame
            current_face_encoding = face_recognition.face_encodings(rgb_current_frame, current_face_locations)[0]

            # Compare the stored face encoding with the current face encoding
            matches = face_recognition.compare_faces([stored_face_encoding], current_face_encoding, tolerance=0.6)
            
            if matches[0]:
                # If the face matches, update the status and mark attendance
                self.status_label.text = "Face recognition successful! You are authorized."
                print("Face recognition successful! You are authorized.")
                
                # Get the current date and time for attendance
                from datetime import datetime
                now = datetime.now()
                year = now.strftime("%Y")
                month = now.strftime("%m")
                day = now.strftime("%d")
                current_time = now.strftime("%H:%M:%S")

                # Update the attendance in the database
                attendance_ref = db.reference(f'{typeof}/{schoolName}/{role}s/{username}/attendance/{year}/{month}/{day}')
                attendance_ref.set({
                    'status': 'present',
                    'time': current_time
                })
                
                print(f"Attendance marked for {username} on {year}-{month}-{day}.")
                toast('Attendance Marked')
                
                # Stop the camera and navigate to the attendance screen
                self.stop_camera()
                self.manager.transition = SlideTransition(direction="right")
                self.manager.current = 'school_teacher_myAttendance'
            else:
                # If the face does not match, update the status and show failure message
                self.status_label.text = "Face recognition failed. You are not authorized."
                print("Face recognition failed. You are not authorized.")
        
        except Exception as e:
            # Catch and display any errors encountered during the process
            self.status_label.text = f"Error: {str(e)}"
            print(f"Error in face recognition: {str(e)}")


class FaceRecognitionApp(MDApp):
    def build(self):
        self.screen_manager = ScreenManager()
        self.facial_recognition_screen = FacialRecognition(name='facial_recognition')
        self.screen_manager.add_widget(self.facial_recognition_screen)
        return self.screen_manager

    def update_fields(self, school_name, type_of, role, username):
        self.facial_recognition_screen.update_fields(school_name, type_of, role, username)

if __name__ == '__main__':
    FaceRecognitionApp().run()