import requests
from kivy.core.image import Image as CoreImage
from io import BytesIO
from kivy.metrics import dp
from kivy.uix.screenmanager import SlideTransition, ScreenManager
from kivymd.app import MDApp
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDRaisedButton
from kivymd.uix.label import MDLabel
from kivymd.uix.screen import MDScreen
from kivymd.uix.toolbar import MDTopAppBar
from kivymd.uix.card import MDCard
from kivy.graphics import Color, Ellipse
from kivy.uix.widget import Widget
from kivy.clock import Clock
from kivy.network.urlrequest import UrlRequest
from kivy.uix.scrollview import ScrollView
import urllib.parse
import random
from FRSregisteration.FRSregister import RegisterWithFace
from FacialRecognition import FacialRecognition
from aboutAttendance import AttendanceScreen
import os
import firebase_admin
from firebase_admin import credentials, initialize_app
from kivy.core.window import Window

class CircularImage(Widget):
    def __init__(self, source, **kwargs):
        super(CircularImage, self).__init__(**kwargs)
        self.source = source
        self.texture = CoreImage(source).texture
        self.size_hint = (None, None)
        self.size = (dp(150), dp(150))
        self.bind(pos=self.update_canvas, size=self.update_canvas)
        self.update_canvas()

    def update_canvas(self, *args):
        self.canvas.clear()
        with self.canvas:
            Color(1, 1, 1, 1)
            Ellipse(pos=self.pos, size=self.size, texture=self.texture)

class myAttendanceTech(MDScreen):
    def __init__(self, **kwargs):
        super(myAttendanceTech, self).__init__(**kwargs)

        self.fields = {
            "schoolName": "GPTOBVP",
            "typeOf": "School",
            "role": "Teacher",
            "userName": "Raju garu"
        }

        # Main layout
        self.layout = MDBoxLayout(orientation='vertical', spacing=dp(10))

        # Top app bar
        self.top_bar = MDTopAppBar(
            title="My Attendance",
            left_action_items=[["arrow-left", lambda x: self.go_back()]],
            pos_hint={"top": 1},
        )
        self.layout.add_widget(self.top_bar)

        # Scrollable content
        self.scroll_view = ScrollView()
        self.scrollable_content = MDBoxLayout(orientation='vertical', spacing=dp(10), padding=dp(10), size_hint_y=None)
        self.scrollable_content.bind(minimum_height=self.scrollable_content.setter('height'))
        self.scroll_view.add_widget(self.scrollable_content)

        # Top layout for profile card and register button
        self.top_layout = MDBoxLayout(orientation='vertical', spacing=dp(10), padding=dp(10), size_hint_y=None)
        self.top_layout.bind(minimum_height=self.top_layout.setter('height'))

        # Profile image and name card
        self.profile_card = MDCard(
            size_hint=(None, None),
            size=(dp(150), dp(200)),
            pos_hint={'center_x': 0.5},
            elevation=0,
            orientation='vertical'
        )

        self.profile_image = CircularImage(
            source='./FRSLogo.png',
            pos_hint={'center_x': 0.5, 'center_y': 0.5}
        )

        self.profile_card.add_widget(self.profile_image)

        self.profile_label = MDLabel(
            text='User',
            halign='center'
        )
        self.profile_card.add_widget(self.profile_label)

        self.top_layout.add_widget(self.profile_card)

        # Register button
        self.register_button = MDRaisedButton(
            text="Register",
            size_hint=(None, None),
            size=(dp(100), dp(40)),
            pos_hint={'center_x': 0.5},
            on_release=self.register
        )
        self.top_layout.add_widget(self.register_button)

        self.scrollable_content.add_widget(self.top_layout)

        # Content layout
        self.content_layout = MDBoxLayout(orientation='vertical', padding=dp(10), spacing=dp(20), size_hint_y=None)
        self.content_layout.bind(minimum_height=self.content_layout.setter('height'))
        self.scrollable_content.add_widget(self.content_layout)

        self.layout.add_widget(self.scroll_view)

        self.add_widget(self.layout)

    def update_fields(self, school_name, type_of, role, username):
        self.fields["typeOf"] = type_of
        self.fields["schoolName"] = school_name
        self.fields["role"] = role
        self.fields["userName"] = username
        self.update_profile_label()
        self.update_title()
        self.fetch_user_data()

    def update_title(self):
        if self.fields["userName"]:
            self.top_bar.title = f"{self.fields['userName']}'s Attendance"
        else:
            self.top_bar.title = "My Attendance"

    def update_profile_label(self):
        if self.fields["userName"]:
            self.profile_label.text = self.fields["userName"]
        else:
            self.profile_label.text = "User"

    def fetch_user_data(self):
        if all(self.fields.values()):
            encoded_school_name = urllib.parse.quote(self.fields['schoolName'])
            encoded_type_of = urllib.parse.quote(self.fields['typeOf'])
            encoded_role = urllib.parse.quote(self.fields['role'])
            encoded_username = urllib.parse.quote(self.fields['userName'])
            
            url = f"https://facialrecognitiondb-default-rtdb.firebaseio.com/{encoded_type_of}/{encoded_school_name}/{encoded_role}s/{encoded_username}.json"

            def on_success(req, result):
                if result:
                    if result.get('registration_status') == True:
                        self.top_layout.remove_widget(self.register_button)
                        if 'image_url' in result:
                            self.update_profile_image(result['image_url'])
                        self.add_attendance_ui()
                    self.update_ui_with_data(result)

            def on_failure(req, result):
                print(f"Failed to fetch user data: {result}")

            def on_error(req, error):
                print(f"Error fetching user data: {error}")

            UrlRequest(url, on_success=on_success, on_failure=on_failure, on_error=on_error)

    def update_ui_with_data(self, data):
        if 'name' in data:
            self.profile_label.text = data['name']
        # Add more UI updates as needed
    
    def update_profile_image(self, image_url):
        def load_image(dt):
            try:
                response = requests.get(image_url)
                response.raise_for_status()  # Check for HTTP errors
                img_data = BytesIO(response.content)
                img = CoreImage(img_data, ext="jpg")
                self.profile_image.texture = img.texture
                self.profile_image.update_canvas()
            except requests.exceptions.HTTPError as http_err:
                if http_err.response.status_code == 403:
                    print("Error: Forbidden. Check bucket permissions and CORS settings.")
                else:
                    print(f"HTTP error occurred: {http_err}")
            except Exception as err:
                print(f"Other error occurred: {err}")

        Clock.schedule_once(load_image)


    def add_attendance_ui(self):
        # Clear existing content
        self.content_layout.clear_widgets()

        # FRS button
        frs_button = MDRaisedButton(
            text="FRS",
            size_hint=(None, None),
            size=(dp(100), dp(40)),
            pos_hint={'center_x': 0.5},
            on_release=self.on_frs_press
        )
        self.content_layout.add_widget(frs_button)

        # Attendance button
        attendance_button = MDRaisedButton(
            text="Attendance",
            size_hint=(None, None),
            size=(dp(300), dp(40)),
            pos_hint={'center_x': 0.5},
            on_release=self.on_attendance_press
        )
        self.content_layout.add_widget(attendance_button)

    def on_frs_press(self, instance):
        screen = self.manager.get_screen('school_teacher_FacialRecognition')
        screen.update_fields(self.fields["schoolName"], self.fields["typeOf"], self.fields["role"], self.fields["userName"])
        self.manager.transition = SlideTransition(direction="right")
        self.manager.current = 'school_teacher_FacialRecognition'

    def on_attendance_press(self, instance):
        screen = self.manager.get_screen('school_teacher_aboutAttendance')
        screen.update_fields(self.fields["schoolName"], self.fields["typeOf"], self.fields["role"], self.fields["userName"])
        self.manager.transition = SlideTransition(direction="right")
        self.manager.current = 'school_teacher_aboutAttendance'

    def go_back(self):
        self.manager.transition = SlideTransition(direction="right")
        self.manager.current = 'school_teacher'

    def register(self, instance):
        screen = self.manager.get_screen('school_teacher_frsRegister')
        screen.update_fields(self.fields["schoolName"], self.fields["typeOf"], self.fields["role"],
                             self.fields["userName"])
        self.manager.transition = SlideTransition(direction="right")
        self.manager.current = 'school_teacher_frsRegister'

    def refresh_data(self):
        self.fetch_user_data()

    def on_enter(self):
        self.refresh_data()

class AttendanceApp(MDApp):
    def __init__(self, **kwargs):
        super(AttendanceApp, self).__init__(**kwargs)

        # Determine the path to your service account key JSON file
        service_account_key_path = os.path.join(os.getcwd(), "serviceAccountKey.json")

        # Initialize Firebase only once
        if not firebase_admin._apps:
            cred = credentials.Certificate(service_account_key_path)
            initialize_app(cred, {
                'databaseURL': 'https://facialrecognitiondb-default-rtdb.firebaseio.com/',
                'storageBucket': 'gs://facialrecognitiondb.appspot.com'
            })
            
            
    def build(self):
        self.title = 'Facial Recognition System'
        self.theme_cls.primary_palette = "Blue"
        self.theme_cls.theme_style = "Light"

        # Set the window size for all mobiles (this is optional and for demonstration purposes)
        Window.size = (360, 640)
        
        sm = ScreenManager()
        attendance_screen = myAttendanceTech(name='school_teacher_myAttendance')
        sm.add_widget(attendance_screen)
        
        attendance_screen.update_fields("GPTOBVP", "School", "Teacher", "Raju garu")
        
        sm.add_widget(RegisterWithFace(name='school_teacher_frsRegister'))
        sm.add_widget(FacialRecognition(name='school_teacher_FacialRecognition'))
        sm.add_widget(AttendanceScreen(name='school_teacher_aboutAttendance'))
        
        return sm


if __name__ == '__main__':
    AttendanceApp().run()