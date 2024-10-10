import firebase_admin
from firebase_admin import credentials, db, storage
import io
from datetime import datetime
from kivy.metrics import dp
from kivy.uix.screenmanager import SlideTransition, ScreenManager
from kivymd.app import MDApp
from kivymd.toast import toast
from kivymd.uix.screen import MDScreen
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDRaisedButton
from kivymd.uix.label import MDLabel
from kivymd.uix.toolbar import MDTopAppBar
from kivy.uix.camera import Camera
from kivy.clock import Clock
from kivy.graphics.texture import Texture
from kivy.graphics import Color, Rectangle, Ellipse, Line, StencilPush, StencilUse, StencilPop, StencilUnUse
from kivy.core.window import Window
from PIL import Image as PILImage
import cv2
import numpy as np

# Firebase setup
SERVICE_ACCOUNT_FILE = "serviceAccountKey.json"
cred = credentials.Certificate(SERVICE_ACCOUNT_FILE)
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://facialrecognitiondb-default-rtdb.firebaseio.com/',
    'storageBucket': 'facialrecognitiondb.appspot.com'
})
bucket = storage.bucket()


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
            Rectangle(texture=self.texture, pos=self.pos, size=self.size)
            StencilUnUse()
            StencilPop()
            Color(0, 0.7, 1, 1)
            border_width = dp(4)
            Line(circle=(self.center_x, self.center_y, min(self.width, self.height) / 2), width=border_width)

    def on_texture(self, *args):
        self._update_canvas()


class RegisterWithFace(MDScreen):
    def update_fields(self, school_name, type_of, role, username):
        self.fields = {
            "SchoolName": school_name,
            "TypeOf": type_of,
            "role": role,
            "userName": username
        }

    def __init__(self, **kwargs):
        super(RegisterWithFace, self).__init__(**kwargs)
        self.fields = {"SchoolName": None, "TypeOf": None, "role": None, "userName": None}
        self.layout = MDBoxLayout(orientation='vertical', spacing=dp(10), padding=dp(20))
        self.top_bar = MDTopAppBar(
            title="Face Registration",
            left_action_items=[["arrow-left", lambda x: self.go_back()]],
            pos_hint={"top": 1},
            elevation=10
        )
        self.add_widget(self.top_bar)
        self.camera = None
        self.instructions = MDLabel(
            text="Please position your face within the camera frame",
            halign="center",
            size_hint_y=None,
            height=dp(100)
        )
        self.register_button = MDRaisedButton(
            text="Capture",
            pos_hint={'center_x': 0.5},
            size_hint=(None, None),
            size=(dp(200), dp(50)),
            padding=dp(10),
            on_release=self.capture_and_register
        )
        self.layout.add_widget(self.instructions)
        self.layout.add_widget(self.register_button)
        self.add_widget(self.layout)
        self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

        with self.canvas.before:
            Color(0.9, 0.9, 0.9, 1)
            self.rect = Rectangle(size=self.size, pos=self.pos)
        self.bind(size=self._update_rect, pos=self._update_rect)

    def _update_rect(self, instance, value):
        self.rect.pos = instance.pos
        self.rect.size = instance.size

    def on_enter(self):
        self.start_camera()

    def on_leave(self):
        self.stop_camera()

    def start_camera(self):
        if not self.camera:
            self.camera = CircularCamera(play=True, resolution=(640, 480))
            self.camera.size_hint = (None, None)
            self.camera.size = (dp(300), dp(300))
            self.camera.pos_hint = {'center_x': 0.5, 'center_y': 0.6}
            self.layout.add_widget(self.camera, index=1)
        else:
            self.camera.play = True
        Clock.schedule_interval(self.update_camera, 1.0 / 30.0)

    def stop_camera(self):
        if self.camera:
            Clock.unschedule(self.update_camera)
            self.camera.play = False
            self.layout.remove_widget(self.camera)
            self.camera = None

    def go_back(self):
        self.stop_camera()
        screen = self.manager.get_screen('school_teacher_myAttendance')
        screen.update_fields(self.fields["SchoolName"], self.fields["TypeOf"], self.fields["role"],
                             self.fields["userName"])
        self.manager.transition = SlideTransition(direction="right")
        self.manager.current = 'school_teacher_myAttendance'

    def update_camera(self, dt):
        if self.camera and self.camera.texture:
            texture = self.camera.texture
            size = texture.size
            pixels = texture.pixels
            pil_image = PILImage.frombytes(mode='RGBA', size=size, data=pixels)
            opencv_image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGBA2BGR)
            faces = self.face_cascade.detectMultiScale(opencv_image, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))

            if len(faces) > 0:
                self.instructions.text = "Face detected. You can now capture the image."
                self.register_button.disabled = False
                self.register_button.md_bg_color = self.theme_cls.primary_color
            else:
                self.instructions.text = "No face detected. Please ensure your face is visible in the camera frame."
                self.register_button.disabled = True
                self.register_button.md_bg_color = self.theme_cls.disabled_hint_text_color

    def capture_and_register(self, instance):
        if not self.camera:
            self.instructions.text = "Camera is not initialized. Please try again."
            return

        texture = self.camera.texture
        size = texture.size
        pixels = texture.pixels
        pil_image = PILImage.frombytes(mode='RGBA', size=size, data=pixels)
        opencv_image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGBA2BGR)
        faces = self.face_cascade.detectMultiScale(opencv_image, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))

        if len(faces) == 0:
            self.instructions.text = "No face detected. Please try again."
            return

        # Turn off the camera immediately after capturing the image
        self.stop_camera()

        pil_image = PILImage.fromarray(cv2.cvtColor(opencv_image, cv2.COLOR_BGR2RGB))
        buffer = io.BytesIO()
        pil_image.save(buffer, format='JPEG', quality=85)  # Save as JPEG with 85% quality
        jpg_data = buffer.getvalue()

        try:
            typeof = self.fields['TypeOf']
            schoolName = self.fields["SchoolName"]
            role = self.fields["role"]
            username = self.fields["userName"]
            blob = bucket.blob(f'{typeof}/{schoolName}/{role}/{username}/face_registrationIMG.jpg')  # Changed extension to .jpg
            blob.upload_from_string(jpg_data, content_type='image/jpeg')  # Changed content type to image/jpeg
            blob.make_public()
            image_url = blob.public_url
            current_time = datetime.utcnow().isoformat()
            registration_data = {
                "timestamp": current_time,
                "image_url": image_url,
                "registration_status": True
            }
            ref = db.reference(f'{typeof}/{schoolName}/{role}s/{username}')
            ref.update(registration_data)

            self.instructions.text = "Registration successful!"
            toast("Registration successful!")

            Clock.schedule_once(self.return_to_attendance_screen, 2)

        except Exception as e:
            print(f"Error occurred: {str(e)}")
            self.instructions.text = f"Error: {str(e)}"

    def return_to_attendance_screen(self, dt):
        screen = self.manager.get_screen('school_teacher_myAttendance')
        screen.update_fields(self.fields["SchoolName"], self.fields["TypeOf"], self.fields["role"],
                             self.fields["userName"])
        self.manager.transition = SlideTransition(direction="right")
        self.manager.current = 'school_teacher_myAttendance'


class SchoolTeacherMyAttendance(MDScreen):
    def update_fields(self, school_name, type_of, role, username):
        self.school_name = school_name
        self.type_of = type_of
        self.role = role
        self.username = username


class RegisterWithFaceApp(MDApp):
    def build(self):
        sm = ScreenManager()
        sm.add_widget(RegisterWithFace(name='register_with_face'))
        sm.add_widget(SchoolTeacherMyAttendance(name='school_teacher_myAttendance'))
        return sm


if __name__ == '__main__':
    RegisterWithFaceApp().run()