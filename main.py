import sys
import time
import random
from datetime import datetime, timedelta
import threading
import simpleaudio as sa
import math
import pygame
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                            QLabel, QPushButton, QTimeEdit, QComboBox, QSpinBox, 
                            QListWidget, QListWidgetItem, QMessageBox, QFileDialog)
from PyQt5.QtCore import Qt, QTime, QTimer, pyqtSignal, QObject, QPoint, QRect
from PyQt5.QtGui import QPainter, QColor, QPen, QBrush, QPainterPath, QLinearGradient

# Initialize pygame mixer
pygame.mixer.init()

class AlarmSignals(QObject):
    alarm_triggered = pyqtSignal(str)

class Alarm:
    def __init__(self, time, sound, snooze_duration=5, enabled=True):
        self.time = time  # datetime object
        self.sound = sound
        self.snooze_duration = snooze_duration  # in minutes
        self.enabled = enabled
        self.snoozed_until = None
        self.is_playing = False
        self.signals = AlarmSignals()
        self.last_triggered_minute = None
        
    def snooze(self):
        if self.is_playing:
            self.is_playing = False
            self.snoozed_until = datetime.now() + timedelta(minutes=self.snooze_duration)
            return True
        return False
    
    def stop(self):
        self.is_playing = False
        self.snoozed_until = None
        self.last_triggered_minute = datetime.now().strftime("%H:%M")
        
    def check_and_trigger(self):
        now = datetime.now()
        current_time = now.strftime("%H:%M")
        alarm_time = self.time.strftime("%H:%M")
        current_minute = now.strftime("%H:%M")
        
        # Check if alarm should trigger
        if self.enabled and current_time == alarm_time and not self.is_playing:
            # Don't trigger again in the same minute
            if self.last_triggered_minute != current_minute:
                if self.snoozed_until is None or now >= self.snoozed_until:
                    self.is_playing = True
                    self.last_triggered_minute = current_minute
                    self.signals.alarm_triggered.emit(self.sound)
                    return True
        return False
    
    def __str__(self):
        return f"{self.time.strftime('%H:%M')} - {self.sound} (Snooze: {self.snooze_duration}m)"

class AnalogClock(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(200, 200)  # Set minimum size for the clock
        
        # Default colors (will be updated by theme)
        self.face_color = QColor(255, 255, 255)
        self.hour_hand_color = QColor(0, 0, 0)
        self.minute_hand_color = QColor(0, 0, 0)
        self.second_hand_color = QColor(255, 0, 0)
        self.marker_color = QColor(0, 0, 0)
        
        # Start timer to update clock every second
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(1000)
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Calculate clock center and radius
        rect = self.rect()
        center = rect.center()
        radius = min(rect.width(), rect.height()) // 2 - 10
        
        # Draw clock face
        painter.setPen(QPen(self.marker_color, 2))
        painter.setBrush(QBrush(self.face_color))
        painter.drawEllipse(center, radius, radius)
        
        # Draw hour marks
        painter.setPen(QPen(self.marker_color, 2))
        for i in range(12):
            angle = i * 30  # 360 / 12 = 30 degrees per hour
            x1 = center.x() + int((radius - 10) * math.sin(math.radians(angle)))
            y1 = center.y() - int((radius - 10) * math.cos(math.radians(angle)))
            x2 = center.x() + int(radius * math.sin(math.radians(angle)))
            y2 = center.y() - int(radius * math.cos(math.radians(angle)))
            painter.drawLine(x1, y1, x2, y2)
        
        # Get current time
        current_time = QTime.currentTime()
        hour = current_time.hour() % 12
        minute = current_time.minute()
        second = current_time.second()
        
        # Draw hour hand
        hour_angle = (hour + minute / 60.0) * 30  # 360 / 12 = 30 degrees per hour
        hour_length = radius * 0.5
        hour_x = center.x() + int(hour_length * math.sin(math.radians(hour_angle)))
        hour_y = center.y() - int(hour_length * math.cos(math.radians(hour_angle)))
        painter.setPen(QPen(self.hour_hand_color, 4))
        painter.drawLine(center, QPoint(hour_x, hour_y))
        
        # Draw minute hand
        minute_angle = minute * 6  # 360 / 60 = 6 degrees per minute
        minute_length = radius * 0.7
        minute_x = center.x() + int(minute_length * math.sin(math.radians(minute_angle)))
        minute_y = center.y() - int(minute_length * math.cos(math.radians(minute_angle)))
        painter.setPen(QPen(self.minute_hand_color, 3))
        painter.drawLine(center, QPoint(minute_x, minute_y))
        
        # Draw second hand
        second_angle = second * 6  # 360 / 60 = 6 degrees per second
        second_length = radius * 0.8
        second_x = center.x() + int(second_length * math.sin(math.radians(second_angle)))
        second_y = center.y() - int(second_length * math.cos(math.radians(second_angle)))
        painter.setPen(QPen(self.second_hand_color, 2))
        painter.drawLine(center, QPoint(second_x, second_y))
        
        # Draw center point
        painter.setPen(QPen(self.marker_color, 1))
        painter.setBrush(QBrush(self.marker_color))
        painter.drawEllipse(center, 5, 5)

class AlarmClock(QMainWindow):
    def __init__(self):
        super().__init__()
        self.alarms = []
        self.sound_options = {
            "Samsung Alarm": "SamsungAlarm.mp3",
            "iPhone Alarm": "IphoneAlarm.mp3",
            "Motivational Quote 1": "MotivationalQuote1.mp3",
            "Motivational Quote 2": "MotivationalQuote2.mp3",
            "Custom Sound": None  # Placeholder for custom sound
        }
        self.current_playing_alarm = None
        self.play_thread = None
        self.custom_sound_path = None
        self.current_theme = "midnight"  # Changed default to midnight
        
        self.init_ui()
        
        # Start the alarm checker
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.check_alarms)
        self.timer.start(1000)  # Check every second
        
    def init_ui(self):
        self.setWindowTitle("Advanced Alarm Clock")
        self.setGeometry(300, 300, 600, 600)  # Made taller to accommodate the analog clock
        
        # Main layout
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        
        # Add theme toggle button at the top
        theme_layout = QHBoxLayout()
        theme_label = QLabel("Theme:")
        theme_layout.addWidget(theme_label)
        
        self.theme_combo = QComboBox()
        self.theme_combo.addItem("🌅 Sunrise Theme")
        self.theme_combo.addItem("🌙 Midnight Theme")
        self.theme_combo.setCurrentIndex(1)  # Set midnight theme as default
        self.theme_combo.currentIndexChanged.connect(self.change_theme)
        theme_layout.addWidget(self.theme_combo)
        
        theme_widget = QWidget()
        theme_widget.setLayout(theme_layout)
        main_layout.insertWidget(0, theme_widget)  # Add at the top
        
        # Add analog clock
        self.analog_clock = AnalogClock()
        main_layout.addWidget(self.analog_clock)
        
        # Current time display
        self.time_label = QLabel("00:00:00")
        self.time_label.setAlignment(Qt.AlignCenter)
        self.time_label.setStyleSheet("font-size: 48px; font-weight: bold;")
        main_layout.addWidget(self.time_label)
        
        # Update time every second
        self.time_timer = QTimer(self)
        self.time_timer.timeout.connect(self.update_time)
        self.time_timer.start(1000)
        self.update_time()
        
        # Alarm creation section
        alarm_section = QWidget()
        alarm_layout = QHBoxLayout(alarm_section)
        
        # Time selection
        self.time_edit = QTimeEdit()
        self.time_edit.setDisplayFormat("HH:mm")
        self.time_edit.setTime(QTime.currentTime())
        alarm_layout.addWidget(self.time_edit)
        
        # Sound selection with custom option
        sound_section = QWidget()
        sound_layout = QHBoxLayout(sound_section)
        
        self.sound_combo = QComboBox()
        for sound in self.sound_options.keys():
            self.sound_combo.addItem(sound)
        self.sound_combo.currentTextChanged.connect(self.on_sound_changed)
        sound_layout.addWidget(self.sound_combo)
        
        # Add browse button for custom sounds
        self.browse_btn = QPushButton("Browse...")
        self.browse_btn.clicked.connect(self.browse_sound)
        self.browse_btn.setVisible(False)  # Only show when "Custom Sound" is selected
        sound_layout.addWidget(self.browse_btn)
        
        alarm_layout.addWidget(sound_section)
        
        # Snooze duration
        snooze_layout = QHBoxLayout()
        snooze_layout.addWidget(QLabel("Snooze (min):"))
        self.snooze_spin = QSpinBox()
        self.snooze_spin.setRange(1, 30)
        self.snooze_spin.setValue(5)
        snooze_layout.addWidget(self.snooze_spin)
        
        snooze_widget = QWidget()
        snooze_widget.setLayout(snooze_layout)
        alarm_layout.addWidget(snooze_widget)
        
        # Add alarm button
        self.add_btn = QPushButton("Add Alarm")
        self.add_btn.clicked.connect(self.add_alarm)
        alarm_layout.addWidget(self.add_btn)
        
        main_layout.addWidget(alarm_section)
        
        # Alarm list
        self.alarm_list = QListWidget()
        self.alarm_list.setSelectionMode(QListWidget.SingleSelection)
        main_layout.addWidget(self.alarm_list)
        
        # Control buttons
        btn_layout = QHBoxLayout()
        
        self.remove_btn = QPushButton("Remove Alarm")
        self.remove_btn.clicked.connect(self.remove_alarm)
        btn_layout.addWidget(self.remove_btn)
        
        self.test_btn = QPushButton("Test Sound")
        self.test_btn.clicked.connect(self.test_sound)
        btn_layout.addWidget(self.test_btn)
        
        control_widget = QWidget()
        control_widget.setLayout(btn_layout)
        main_layout.addWidget(control_widget)
        
        # Alarm control section (visible when alarm is triggered)
        self.alarm_control = QWidget()
        alarm_control_layout = QVBoxLayout(self.alarm_control)
        
        self.current_alarm_label = QLabel("Alarm!")
        self.current_alarm_label.setStyleSheet("font-size: 24px; font-weight: bold; color: red;")
        alarm_control_layout.addWidget(self.current_alarm_label)
        
        # Add puzzle section
        self.puzzle_widget = QWidget()
        puzzle_layout = QHBoxLayout(self.puzzle_widget)
        
        self.puzzle_label = QLabel("Solve to stop: ")
        puzzle_layout.addWidget(self.puzzle_label)
        
        self.puzzle_answer = QSpinBox()
        self.puzzle_answer.setRange(-100, 100)
        puzzle_layout.addWidget(self.puzzle_answer)
        
        self.check_answer_btn = QPushButton("Check")
        self.check_answer_btn.clicked.connect(self.check_puzzle_answer)
        puzzle_layout.addWidget(self.check_answer_btn)
        
        alarm_control_layout.addWidget(self.puzzle_widget)
        
        # Button row
        button_row = QWidget()
        button_layout = QHBoxLayout(button_row)
        
        self.snooze_btn = QPushButton("Snooze")
        self.snooze_btn.clicked.connect(self.snooze_alarm)
        button_layout.addWidget(self.snooze_btn)
        
        alarm_control_layout.addWidget(button_row)
        
        self.alarm_control.setVisible(False)
        main_layout.addWidget(self.alarm_control)
        
        self.setCentralWidget(main_widget)
        
        # Apply default theme
        self.apply_theme("midnight")  # Changed default to midnight
        
    def update_time(self):
        current_time = datetime.now().strftime("%H:%M:%S")
        self.time_label.setText(current_time)
    
    def on_sound_changed(self, sound_name):
        # Show or hide browse button based on selection
        if sound_name == "Custom Sound":
            self.browse_btn.setVisible(True)
        else:
            self.browse_btn.setVisible(False)
    
    def browse_sound(self):
        # Open file dialog to select sound file
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Sound File", "", 
            "Sound Files (*.mp3 *.wav *.ogg);;All Files (*)"
        )
        
        if file_path:
            self.custom_sound_path = file_path
            self.sound_options["Custom Sound"] = file_path
            
            # Extract just the filename for display
            file_name = file_path.split("/")[-1]
            self.sound_combo.setItemText(self.sound_combo.currentIndex(), f"Custom: {file_name}")
    
    def add_alarm(self):
        time_value = self.time_edit.time()
        sound_name = self.sound_combo.currentText()
        
        # Get the sound file path
        if "Custom:" in sound_name:
            sound_file = self.custom_sound_path
        else:
            sound_file = self.sound_options[sound_name]
            
        # Check if a custom sound is selected but not set
        if sound_name == "Custom Sound" and not self.custom_sound_path:
            QMessageBox.warning(self, "No Sound Selected", 
                               "Please select a custom sound file first.")
            return
            
        snooze_duration = self.snooze_spin.value()
        
        # Create datetime object for today with the selected time
        now = datetime.now()
        alarm_time = datetime(now.year, now.month, now.day, 
                             time_value.hour(), time_value.minute())
        
        # If the time is in the past, set it for tomorrow
        if alarm_time < now:
            alarm_time += timedelta(days=1)
        
        # Create and add the alarm
        alarm = Alarm(alarm_time, sound_file, snooze_duration)
        alarm.signals.alarm_triggered.connect(self.trigger_alarm)
        self.alarms.append(alarm)
        
        # Add to list widget
        item = QListWidgetItem(str(alarm))
        self.alarm_list.addItem(item)
        
        QMessageBox.information(self, "Alarm Added", 
                               f"Alarm set for {alarm_time.strftime('%H:%M')}")
    
    def remove_alarm(self):
        selected_items = self.alarm_list.selectedItems()
        if not selected_items:
            return
            
        selected_index = self.alarm_list.row(selected_items[0])
        self.alarm_list.takeItem(selected_index)
        removed_alarm = self.alarms.pop(selected_index)
        
        # If this is the currently playing alarm, stop it
        if self.current_playing_alarm == removed_alarm:
            self.stop_alarm()
    
    def test_sound(self):
        sound_name = self.sound_combo.currentText()
        sound_file = self.sound_options[sound_name]
        
        # Play the sound in a separate thread
        if self.play_thread is None or not self.play_thread.is_alive():
            self.play_thread = threading.Thread(target=self.play_test_sound, args=(sound_file,))
            self.play_thread.daemon = True
            self.play_thread.start()
    
    def play_test_sound(self, sound_file):
        try:
            pygame.mixer.music.load(sound_file)
            pygame.mixer.music.play()
            # Wait for the sound to finish
            while pygame.mixer.music.get_busy():
                time.sleep(0.1)
        except Exception as e:
            print(f"Error playing test sound: {e}")
    
    def check_alarms(self):
        for alarm in self.alarms:
            if alarm.check_and_trigger():
                break  # Only trigger one alarm at a time
    
    def trigger_alarm(self, sound_file):
        # Find the alarm that triggered
        for alarm in self.alarms:
            if alarm.is_playing and alarm.sound == sound_file:
                self.current_playing_alarm = alarm
                break
        
        # Generate a new puzzle
        self.generate_puzzle()
        
        # Show alarm controls
        self.alarm_control.setVisible(True)
        self.current_alarm_label.setText(f"Alarm: {sound_file}")
        
        # Play the sound in a separate thread
        if self.play_thread is None or not self.play_thread.is_alive():
            self.play_thread = threading.Thread(target=self.play_alarm_sound, args=(sound_file,))
            self.play_thread.daemon = True
            self.play_thread.start()
    
    def play_alarm_sound(self, sound_file):
        try:
            pygame.mixer.music.load(sound_file)
            while self.current_playing_alarm and self.current_playing_alarm.is_playing:
                pygame.mixer.music.play()
                # Wait for the sound to finish
                while pygame.mixer.music.get_busy() and self.current_playing_alarm and self.current_playing_alarm.is_playing:
                    time.sleep(0.1)
                time.sleep(0.5)  # Small pause between repetitions
        except Exception as e:
            print(f"Error playing sound: {e}")
            # Don't try to show a message box from a non-main thread
            # Instead, emit a signal to show the message on the main thread
            self.current_playing_alarm.stop()
    
    def generate_puzzle(self):
        # Generate two random numbers between 1 and 20
        self.num1 = random.randint(1, 20)
        self.num2 = random.randint(1, 20)
        
        # Randomly choose operation (addition or subtraction)
        self.operation = random.choice(['+', '-'])
        
        # Calculate the correct answer
        if self.operation == '+':
            self.correct_answer = self.num1 + self.num2
        else:
            self.correct_answer = self.num1 - self.num2
        
        # Update the puzzle label
        self.puzzle_label.setText(f"Solve to stop: {self.num1} {self.operation} {self.num2} = ")
        
        # Reset the answer field
        self.puzzle_answer.setValue(0)
    
    def check_puzzle_answer(self):
        user_answer = self.puzzle_answer.value()
        
        if user_answer == self.correct_answer:
            # Correct answer - stop the alarm
            self.stop_alarm()
            QMessageBox.information(self, "Puzzle Solved", "Correct! Alarm stopped.")
        else:
            # Wrong answer - generate a new puzzle
            QMessageBox.warning(self, "Wrong Answer", "Incorrect! Try again with a new puzzle.")
            self.generate_puzzle()
    
    def snooze_alarm(self):
        # Snooze doesn't require solving the puzzle
        if self.current_playing_alarm:
            self.current_playing_alarm.snooze()
            snooze_time = datetime.now() + timedelta(minutes=self.current_playing_alarm.snooze_duration)
            QMessageBox.information(self, "Alarm Snoozed", 
                                  f"Alarm snoozed until {snooze_time.strftime('%H:%M')}")
            self.alarm_control.setVisible(False)
            self.current_playing_alarm = None
    
    def stop_alarm(self):
        if self.current_playing_alarm:
            self.current_playing_alarm.stop()
            pygame.mixer.music.stop()  # Make sure to stop the sound
            self.alarm_control.setVisible(False)
            self.current_playing_alarm = None
    
    def closeEvent(self, event):
        # Clean up before closing
        self.timer.stop()
        self.time_timer.stop()
        self.analog_clock.timer.stop()  # Stop the analog clock timer
        event.accept()
    
    def change_theme(self, index):
        if index == 0:
            self.apply_theme("sunrise")
        else:
            self.apply_theme("midnight")
    
    def apply_theme(self, theme_name):
        self.current_theme = theme_name
        
        if theme_name == "sunrise":
            # 🌅 Sunrise Theme - Warmer, less pink gradient with rounded elements
            self.setStyleSheet("""
                QMainWindow, QWidget {
                    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                      stop:0 #ffecd1, stop:0.5 #ffcad4, stop:1 #f7d6e0);
                    color: #5e4c5a;
                }
                QLabel {
                    color: #5e4c5a;
                    background-color: transparent;
                    font-family: 'Arial Rounded MT Bold', 'Arial', sans-serif;
                }
                QPushButton {
                    background-color: #f8a978;
                    color: #5e4c5a;
                    border: none;
                    border-radius: 12px;
                    padding: 10px 18px;
                    font-weight: bold;
                    font-family: 'Arial Rounded MT Bold', 'Arial', sans-serif;
                    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                }
                QPushButton:hover {
                    background-color: #f9c784;
                    transform: translateY(-2px);
                }
                QPushButton:pressed {
                    background-color: #e88a54;
                    transform: translateY(1px);
                }
                QTimeEdit, QSpinBox {
                    background-color: #fff1e6;
                    border: 2px solid #f8a978;
                    border-radius: 10px;
                    padding: 6px;
                    color: #5e4c5a;
                    font-family: 'Arial Rounded MT Bold', 'Arial', sans-serif;
                    selection-background-color: #f8a978;
                }
                QComboBox {
                    background-color: #fff1e6;
                    border: 2px solid #f8a978;
                    border-radius: 10px;
                    padding: 6px;
                    color: #5e4c5a;
                    font-family: 'Arial Rounded MT Bold', 'Arial', sans-serif;
                    selection-background-color: #f8a978;
                    min-height: 25px;
                }
                QComboBox::drop-down {
                    subcontrol-origin: padding;
                    subcontrol-position: right center;
                    width: 25px;
                    border-left: none;
                    border-top-right-radius: 10px;
                    border-bottom-right-radius: 10px;
                }
                QComboBox::down-arrow {
                    image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTQiIGhlaWdodD0iOCIgdmlld0JveD0iMCAwIDE0IDgiIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PHBhdGggZD0iTTEgMUw3IDdMMTMgMSIgc3Ryb2tlPSIjZjhhOTc4IiBzdHJva2Utd2lkdGg9IjIiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCIvPjwvc3ZnPg==);
                    width: 14px;
                    height: 8px;
                }
                QComboBox QAbstractItemView {
                    background-color: #fff1e6;
                    border: 2px solid #f8a978;
                    border-radius: 10px;
                    selection-background-color: #f9c784;
                    selection-color: #5e4c5a;
                    outline: none;
                }
                QListWidget {
                    background-color: rgba(255, 241, 230, 0.7);
                    border: 2px solid #f8a978;
                    border-radius: 12px;
                    padding: 5px;
                    alternate-background-color: rgba(255, 202, 212, 0.3);
                    font-family: 'Arial Rounded MT Bold', 'Arial', sans-serif;
                }
                QListWidget::item {
                    border-radius: 8px;
                    padding: 5px;
                    margin: 2px;
                }
                QListWidget::item:selected {
                    background-color: #f8a978;
                    color: #5e4c5a;
                }
                #time_label {
                    color: #e88a54;
                    font-size: 48px;
                    font-weight: bold;
                    background-color: transparent;
                    font-family: 'Arial Rounded MT Bold', 'Arial', sans-serif;
                    text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.1);
                }
            """)
            # Update analog clock colors for sunrise theme
            self.analog_clock.face_color = QColor(255, 241, 230, 200)
            self.analog_clock.hour_hand_color = QColor(94, 76, 90)
            self.analog_clock.minute_hand_color = QColor(94, 76, 90)
            self.analog_clock.second_hand_color = QColor(232, 138, 84)
            self.analog_clock.marker_color = QColor(94, 76, 90)
            
        else:  # midnight theme
            # 🌙 Midnight Theme - Cute starry night with glowing elements
            self.setStyleSheet("""
                QMainWindow, QWidget {
                    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                      stop:0 #0f1c2e, stop:0.5 #1a2a43, stop:1 #0f1c2e);
                    color: #e0fbfc;
                }
                QLabel {
                    color: #e0fbfc;
                    background-color: transparent;
                    font-family: 'Arial Rounded MT Bold', 'Arial', sans-serif;
                }
                QPushButton {
                    background-color: #1e3a5f;
                    color: #5edfff;
                    border: 2px solid #5edfff;
                    border-radius: 12px;
                    padding: 10px 18px;
                    font-weight: bold;
                    font-family: 'Arial Rounded MT Bold', 'Arial', sans-serif;
                    box-shadow: 0 0 10px rgba(94, 223, 255, 0.5);
                }
                QPushButton:hover {
                    background-color: #2a4a7f;
                    border: 2px solid #98f5ff;
                    box-shadow: 0 0 15px rgba(94, 223, 255, 0.7);
                }
                QPushButton:pressed {
                    background-color: #0c2c54;
                    box-shadow: 0 0 5px rgba(94, 223, 255, 0.3);
                }
                QTimeEdit, QSpinBox {
                    background-color: #1e3a5f;
                    border: 2px solid #5edfff;
                    border-radius: 10px;
                    padding: 6px;
                    color: #e0fbfc;
                    font-family: 'Arial Rounded MT Bold', 'Arial', sans-serif;
                    selection-background-color: #5edfff;
                    selection-color: #0f1c2e;
                }
                QComboBox {
                    background-color: #1e3a5f;
                    border: 2px solid #5edfff;
                    border-radius: 10px;
                    padding: 6px;
                    color: #e0fbfc;
                    font-family: 'Arial Rounded MT Bold', 'Arial', sans-serif;
                    selection-background-color: #5edfff;
                    min-height: 25px;
                }
                QComboBox::drop-down {
                    subcontrol-origin: padding;
                    subcontrol-position: right center;
                    width: 25px;
                    border-left: none;
                    border-top-right-radius: 10px;
                    border-bottom-right-radius: 10px;
                }
                QComboBox::down-arrow {
                    image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTQiIGhlaWdodD0iOCIgdmlld0JveD0iMCAwIDE0IDgiIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PHBhdGggZD0iTTEgMUw3IDdMMTMgMSIgc3Ryb2tlPSIjNWVkZmZmIiBzdHJva2Utd2lkdGg9IjIiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCIvPjwvc3ZnPg==);
                    width: 14px;
                    height: 8px;
                }
                QComboBox QAbstractItemView {
                    background-color: #1e3a5f;
                    border: 2px solid #5edfff;
                    border-radius: 10px;
                    selection-background-color: #5edfff;
                    selection-color: #0f1c2e;
                    outline: none;
                }
                QListWidget {
                    background-color: #1e3a5f;
                    border: 2px solid #5edfff;
                    border-radius: 12px;
                    padding: 5px;
                    color: #e0fbfc;
                    alternate-background-color: #2a4a7f;
                    font-family: 'Arial Rounded MT Bold', 'Arial', sans-serif;
                }
                QListWidget::item {
                    border-radius: 8px;
                    padding: 5px;
                    margin: 2px;
                }
                QListWidget::item:selected {
                    background-color: #5edfff;
                    color: #0f1c2e;
                }
                #time_label {
                    color: #5edfff;
                    font-size: 48px;
                    font-weight: bold;
                    background-color: transparent;
                    font-family: 'Arial Rounded MT Bold', 'Arial', sans-serif;
                    text-shadow: 0 0 10px rgba(94, 223, 255, 0.7);
                }
            """)
            # Update analog clock colors for midnight theme
            self.analog_clock.face_color = QColor(30, 58, 95)
            self.analog_clock.hour_hand_color = QColor(224, 251, 252)
            self.analog_clock.minute_hand_color = QColor(224, 251, 252)
            self.analog_clock.second_hand_color = QColor(94, 223, 255)
            self.analog_clock.marker_color = QColor(224, 251, 252)
        
        # Set ID for time label to apply specific styling
        self.time_label.setObjectName("time_label")
        
        # Update the analog clock
        self.analog_clock.update()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AlarmClock()
    window.show()
    sys.exit(app.exec_())
