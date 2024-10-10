from kivy.lang import Builder
from kivy.uix.widget import Widget
from kivy.graphics import Color, Ellipse
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.screenmanager import ScreenManager, Screen, SlideTransition
from kivy.properties import StringProperty, ListProperty, ObjectProperty, NumericProperty
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.core.window import Window
from kivy.clock import Clock
from kivymd.app import MDApp
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.label import MDLabel
from kivymd.uix.card import MDCard
from kivymd.uix.toolbar import MDTopAppBar
from kivymd.uix.screen import MDScreen
from kivymd.uix.button import MDIconButton
from datetime import datetime, timedelta
import calendar
import firebase_admin
from firebase_admin import credentials, db
import requests
from io import BytesIO
from kivy.core.image import Image as CoreImage
from kivy.graphics.texture import Texture
from kivymd.uix.dialog import MDDialog
from kivymd.uix.button import MDFlatButton
import os

def convert_to_12_hour_format(time_str):
    try:
        print(time_str)  # For debugging
        # Assuming the time is in "HH:MM:SS" format
        time_24hr = datetime.strptime(time_str, "%H:%M:%S")
        return time_24hr.strftime("%I:%M %p")  # Convert to 12-hour format with AM/PM
    except ValueError:
        return None

# Initialize Firebase
service_account_key_path = "serviceAccountKey.json"
if not firebase_admin._apps:
    cred = credentials.Certificate(service_account_key_path)
    firebase_admin.initialize_app(cred, {
        'databaseURL': 'https://facialrecognitiondb-default-rtdb.firebaseio.com/',
        'storageBucket': 'facialrecognitiondb.appspot.com'
    })

class CircularImage(Widget):
    source = ObjectProperty(None)
    color = ListProperty([1, 1, 1, 1])

    def __init__(self, **kwargs):
        super(CircularImage, self).__init__(**kwargs)
        self.bind(pos=self.update_canvas, size=self.update_canvas, source=self.update_canvas, color=self.update_canvas)

    def update_canvas(self, *args):
        self.canvas.clear()
        if not self.source or (isinstance(self.source, str) and not os.path.exists(self.source)):
            print(f"Image not found: {self.source}")  # Debugging line
            return  # Optionally, provide a default image here if desired
        with self.canvas:
            Color(*self.color)
            Ellipse(pos=self.pos, size=self.size)
            Color(1, 1, 1, 1)
            
            # Check if source is a string (path) to avoid TypeError
            if isinstance(self.source, str):
                self.source = CoreImage(self.source).texture
                
            Ellipse(pos=(self.pos[0] + dp(2), self.pos[1] + dp(2)),
                    size=(self.size[0] - dp(4), self.size[1] - dp(4)),
                    texture=self.source)


class CircularDateLabel(Label):
    def __init__(self, text, is_highlighted=False, attendance_status=None, time_info=None, **kwargs):
        super(CircularDateLabel, self).__init__(**kwargs)
        self.text = text
        self.is_highlighted = is_highlighted
        self.attendance_status = attendance_status
        self.time_info = time_info
        self.bind(pos=self.update_canvas, size=self.update_canvas)
        self._dialog = None

    def update_canvas(self, *args):
        self.canvas.before.clear()
        with self.canvas.before:
            if self.attendance_status == 'present':
                Color(0, 1, 0, 1)  # Green for present
            elif self.attendance_status == 'absent':
                Color(1, 0, 0, 1)  # Red for absent
            else:
                Color(1, 1, 1, 1)  # White background
            Ellipse(pos=self.pos, size=self.size)

        self.color = (1, 1, 1, 1) if self.attendance_status else (0.3, 0.3, 0.3, 1)

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self.show_date_dialog()
            return True
        return super(CircularDateLabel, self).on_touch_down(touch)

    def show_date_dialog(self):
        formatted_time = convert_to_12_hour_format(self.time_info) if self.time_info else 'No time data available'
        
        if not self._dialog:
            self._dialog = MDDialog(
                title="You Entered:",
                text=f"Time: {formatted_time}",
                size_hint=(0.8, 0.3),
                buttons=[
                    MDFlatButton(text="CLOSE", on_release=self.close_dialog)
                ]
            )
        self._dialog.open()

        
    def close_dialog(self, instance):
        self._dialog.dismiss()

class CalendarWidget(MDBoxLayout):
    current_date = ObjectProperty(datetime.now())
    cell_size = NumericProperty(dp(40))

    def __init__(self, **kwargs):
        super(CalendarWidget, self).__init__(**kwargs)
        self.orientation = 'vertical'
        self.spacing = dp(10)
        self.padding = dp(16), dp(0), dp(16), dp(0)
        self.size_hint_y = None
        self.bind(minimum_height=self.setter('height'))
        self.attendance_data = {}
        Clock.schedule_once(self.create_calendar)
        Window.bind(on_resize=self.on_window_resize)

    def set_attendance_data(self, attendance_data):
        self.attendance_data = attendance_data
        self.create_calendar()

    def create_calendar(self, *args):
        self.clear_widgets()

        self.cell_size = (Window.width - dp(32)) / 7

        header = MDBoxLayout(orientation='horizontal', size_hint_y=None, height=dp(50))
        left_arrow = MDIconButton(icon="chevron-left", on_release=self.previous_month)
        right_arrow = MDIconButton(icon="chevron-right", on_release=self.next_month)
        month_year_label = MDLabel(
            text=f"{self.current_date.strftime('%B %Y')}",
            halign='center',
            theme_text_color="Primary",
            font_style="H6"
        )
        header.add_widget(left_arrow)
        header.add_widget(month_year_label)
        header.add_widget(right_arrow)
        self.add_widget(header)

        calendar_grid = GridLayout(cols=7, spacing=dp(2), size_hint_y=None)
        calendar_grid.bind(minimum_height=calendar_grid.setter('height'))

        for day in ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"]:
            weekday_label = MDLabel(
                text=day,
                halign='center',
                theme_text_color="Secondary",
                font_style="Caption",
                size_hint=(None, None),
                size=(self.cell_size, self.cell_size * 0.5)
            )
            calendar_grid.add_widget(weekday_label)

        month_calendar = calendar.monthcalendar(self.current_date.year, self.current_date.month)
        for week in month_calendar:
            for day in week:
                if day == 0:
                    calendar_grid.add_widget(Widget(size_hint=(None, None), size=(self.cell_size, self.cell_size)))
                else:
                    is_highlighted = (day == self.current_date.day and
                                      self.current_date.month == datetime.now().month and
                                      self.current_date.year == datetime.now().year)
                    
                    attendance_status , time_info= self.get_attendance_status(day)
                    
                    date_label = CircularDateLabel(
                        text=str(day),
                        is_highlighted=is_highlighted,
                        attendance_status=attendance_status,
                        time_info=time_info,
                        size_hint=(None, None),
                        size=(self.cell_size, self.cell_size),
                        font_size=self.cell_size * 0.4
                    )
                    calendar_grid.add_widget(date_label)

        self.add_widget(calendar_grid)

    def get_attendance_status(self, day):
        year = str(self.current_date.year)
        month = f"{self.current_date.month:02d}"
        day_str = f"{day:02d}"
        
        if year in self.attendance_data and month in self.attendance_data[year]:
            if day_str in self.attendance_data[year][month]:
                attendance_info = self.attendance_data[year][month][day_str]
                status = attendance_info.get('status', None)
                time_info = attendance_info.get('time', None)  # Fetch the time info
                return status, time_info
        return None, None

    def previous_month(self, *args):
        self.current_date = self.current_date.replace(day=1) - timedelta(days=1)
        self.create_calendar()

    def next_month(self, *args):
        next_month = self.current_date.replace(day=28) + timedelta(days=4)
        self.current_date = next_month.replace(day=1)
        self.create_calendar()

    def on_window_resize(self, window, width, height):
        Clock.schedule_once(self.create_calendar)

class AttendanceScreen(MDScreen):
    def __init__(self, **kwargs):
        super(AttendanceScreen, self).__init__(**kwargs)
        self.name_label = None
        self.subject_label = None
        self._setup_ui()
        
    def update_fields(self, school_name, type_of, role, username):
        self.fields = {
            "SchoolName": school_name,
            "TypeOf": type_of,
            "role": role,
            "userName": username,
        }
        print(type_of, school_name, role, username)
        Clock.schedule_once(lambda dt: self.fetch_firebase_data(type_of, school_name, role, username))

    def fetch_firebase_data(self, type_of, school_name, role, username):
        ref = db.reference(f'{type_of}/{school_name}/{role}s/{username}')
        data = ref.get()
        print("Data",data)
        if data:
            name = username
            subject = "science"
            image_url = data.get('image_url', '')
            attendance_data = data.get('attendance', {})
            Clock.schedule_once(lambda dt: self.update_profile_info(name, subject, image_url, attendance_data))

    def update_profile_info(self, name, subject, image_url, attendance_data):
        if self.name_label and self.subject_label:
            self.name_label.text = f"Name: {name}"
            self.subject_label.text = f"Subject: {subject}"
            if image_url:
                Clock.schedule_once(lambda dt: self.update_profile_image(image_url))
            self.calendar_widget.set_attendance_data(attendance_data)
        else:
            print("Labels not initialized yet")

    def update_profile_image(self, image_url):
        def load_image(dt):
            try:
                response = requests.get(image_url)
                response.raise_for_status()
                img_data = BytesIO(response.content)
                img = CoreImage(img_data, ext="png")
                self.profile_image.source = img.texture
                self.profile_image.canvas.ask_update()
            except requests.exceptions.RequestException as e:
                print(f"Error loading image: {e}")
                self.profile_image.source = "Teacher.png"

        Clock.schedule_once(load_image)

    def on_enter(self, *args):
        super().on_enter(*args)
        if hasattr(self, 'fields'):
            self.fetch_firebase_data(
                self.fields['TypeOf'],
                self.fields['SchoolName'],
                self.fields['role'],
                self.fields['userName']
            )

    def _setup_ui(self):
        self.clear_widgets()

        main_layout = MDBoxLayout(orientation='vertical', spacing=dp(10), padding=(dp(0), dp(0), dp(0), dp(0)))

        top_bar = MDTopAppBar(
            title="About Attendance",
            left_action_items=[["arrow-left", lambda x: self.go_back()]],
            pos_hint={"top": 1},
            elevation=0
        )
        main_layout.add_widget(top_bar)

        scroll_content = MDBoxLayout(orientation='vertical', spacing=dp(10), padding=(dp(0), dp(0), dp(0), dp(0)),
                                     size_hint_y=None)
        scroll_content.bind(minimum_height=scroll_content.setter('height'))

        scrollview = ScrollView(size_hint=(1, 1))
        scrollview.add_widget(scroll_content)

        profile_card = MDCard(orientation='vertical', size_hint=(None, None),
                              size=(Window.width * 0.9, dp(200)),
                              pos_hint={"center_x": 0.5})
        self.profile_image = CircularImage(size_hint=(None, None), size=(dp(120), dp(120)),
                                           pos_hint={"center_x": 0.5}, color=[1, 0.5, 0, 1])
        self.profile_image.source = "Teacher.png"
        profile_card.add_widget(self.profile_image)

        self.name_label = MDLabel(text="Name: Loading...", halign="center", theme_text_color="Primary", size_hint_y=None,
                                  height=self.name_label_size())
        self.subject_label = MDLabel(text="Subject: Loading...", halign="center", theme_text_color="Primary",
                                     size_hint_y=None, height=self.subject_label_size())
        profile_card.add_widget(self.name_label)
        profile_card.add_widget(self.subject_label)

        scroll_content.add_widget(profile_card)
        self.calendar_widget = CalendarWidget()
        scroll_content.add_widget(self.calendar_widget)

        main_layout.add_widget(scrollview)
        self.add_widget(main_layout)

    def go_back(self):
        self.manager.transition = SlideTransition(direction='right')
        self.manager.current = 'school_teacher_myAttendance'

    def name_label_size(self):
        return dp(40)

    def subject_label_size(self):
        return dp(30)

class MainApp(MDApp):
    def build(self):
        sm = ScreenManager()
        sm.add_widget(AttendanceScreen(name="AttendanceScreen"))
        return sm

if __name__ == '__main__':
    MainApp().run()
