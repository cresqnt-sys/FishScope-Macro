import time
import threading
import pyautogui
import keyboard
from PIL import ImageGrab
import ctypes
import autoit
import json
import os
import sys
from PyQt6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout,
                            QWidget, QPushButton, QLabel, QFrame, QScrollArea,
                            QMessageBox)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject, QPoint
from PyQt6.QtGui import QFont, QCursor, QPainter, QPen, QColor

pyautogui.FAILSAFE = False

class MouseAutomation:
    def __init__(self):
        self.toggle = False
        self.running = False
        self.thread = None
        self.config_file = "fishscopeconfig.json"

        self.screen_width, self.screen_height = pyautogui.size()
        print(f"Screen resolution: {self.screen_width}x{self.screen_height}")

        self.coordinates = {
            'fish_button': (850, 830),
            'white_diamond': (1176, 836),
            'reel_bar': (757, 762, 1161, 782),
            'completed_border': (1139, 762),
            'close_button': (1113, 342),
            'first_item': (825, 408),
            'sell_button': (595, 806),
            'confirm_button': (805, 618),
            'mouse_idle_position': (self.screen_width // 2, self.screen_height // 2)
        }

        self.load_calibration()

    def save_calibration(self):
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.coordinates, f, indent=2)
            print("Calibration auto-saved successfully!")
        except Exception as e:
            print(f"Error saving calibration: {e}")

    def load_calibration(self):
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    saved_coords = json.load(f)
                    self.coordinates.update(saved_coords)
                print("Calibration loaded successfully!")
            else:
                print("No saved calibration found, using defaults")
        except Exception as e:
            print(f"Error loading calibration: {e}")

    def print_current_coordinates(self):
        print("\nCurrent coordinates being used:")
        for key, coord in self.coordinates.items():
            print(f"  {key}: {coord}")
        print()

    def get_mouse_position(self):
        return pyautogui.position()

    def debug_pixel_color(self, x, y):
        single_color = self.get_pixel_color(x, y)
        avg_color = self.get_average_pixel_color(x, y, radius=1)
        is_white_single = self.is_white_pixel(single_color)
        is_white_avg = self.is_white_pixel(avg_color)

        print(f"Pixel at ({x}, {y}):")
        print(f"  Single pixel: {single_color} - Is white: {is_white_single}")
        print(f"  Average area: {avg_color} - Is white: {is_white_avg}")
        return avg_color

    def find_white_pixels_in_area(self, center_x, center_y, search_radius=50):
        print(f"Searching for white pixels around ({center_x}, {center_y}) within {search_radius} pixels...")

        x1 = max(0, center_x - search_radius)
        y1 = max(0, center_y - search_radius)
        x2 = min(self.screen_width, center_x + search_radius)
        y2 = min(self.screen_height, center_y + search_radius)

        screenshot = ImageGrab.grab(bbox=(x1, y1, x2, y2))
        width, height = screenshot.size

        white_pixels = []

        for y in range(0, height, 5):
            for x in range(0, width, 5):
                pixel = screenshot.getpixel((x, y))
                if self.is_white_pixel(pixel, tolerance=15):
                    actual_x = x1 + x
                    actual_y = y1 + y
                    white_pixels.append((actual_x, actual_y))

        print(f"Found {len(white_pixels)} white pixels in the area:")
        for i, (wx, wy) in enumerate(white_pixels[:10]):
            print(f"  {i+1}. ({wx}, {wy})")

        if len(white_pixels) > 10:
            print(f"  ... and {len(white_pixels) - 10} more")

        return white_pixels

    def debug_area_around_coordinate(self, coord_name, radius=20):
        if coord_name in self.coordinates:
            x, y = self.coordinates[coord_name]
            print(f"\nDebugging area around {coord_name} at ({x}, {y}):")

            for dy in range(-radius, radius + 1, 10):
                for dx in range(-radius, radius + 1, 10):
                    test_x, test_y = x + dx, y + dy
                    if 0 <= test_x < self.screen_width and 0 <= test_y < self.screen_height:
                        color = self.get_pixel_color(test_x, test_y)
                        is_white = self.is_white_pixel(color, tolerance=15)
                        if is_white:
                            print(f"  WHITE pixel found at ({test_x}, {test_y}): {color}")
        else:
            print(f"Coordinate '{coord_name}' not found")

    def get_pixel_color(self, x, y):
        screenshot = ImageGrab.grab(bbox=(x, y, x+1, y+1))
        return screenshot.getpixel((0, 0))

    def is_white_pixel(self, color, tolerance=10):
        r, g, b = color[:3]
        return all(c >= (255 - tolerance) for c in [r, g, b])

    def get_average_pixel_color(self, x, y, radius=2):
        x1, y1 = max(0, x - radius), max(0, y - radius)
        x2, y2 = x + radius + 1, y + radius + 1

        screenshot = ImageGrab.grab(bbox=(x1, y1, x2, y2))
        width, height = screenshot.size

        total_r, total_g, total_b = 0, 0, 0
        pixel_count = 0

        for py in range(height):
            for px in range(width):
                pixel = screenshot.getpixel((px, py))
                total_r += pixel[0]
                total_g += pixel[1]
                total_b += pixel[2]
                pixel_count += 1

        if pixel_count > 0:
            avg_r = total_r // pixel_count
            avg_g = total_g // pixel_count
            avg_b = total_b // pixel_count
            return (avg_r, avg_g, avg_b)

        return (0, 0, 0)

    def find_pixel_color(self, x1, y1, x2, y2, target_color, tolerance=1):
        screenshot = ImageGrab.grab(bbox=(x1, y1, x2, y2))
        width, height = screenshot.size

        for y in range(height):
            for x in range(width):
                pixel = screenshot.getpixel((x, y))
                if self.color_match(pixel, target_color, tolerance):
                    return (x1 + x, y1 + y)
        return None

    def color_match(self, color1, color2, tolerance):
        return all(abs(c1 - c2) <= tolerance for c1, c2 in zip(color1, color2))

    def mouse_automation_loop(self):
        while self.running and self.toggle:
            if not self.toggle:
                break

            fish_x, fish_y = self.coordinates['fish_button']
            autoit.mouse_move(fish_x, fish_y, 3)
            time.sleep(0.3)
            autoit.mouse_click("left")
            time.sleep(0.3)

            idle_x, idle_y = self.coordinates['mouse_idle_position']
            pyautogui.moveTo(idle_x, idle_y, duration=0.5, tween=pyautogui.easeInOutQuad)

            while True:
                if not self.toggle:
                    return

                check_x, check_y = self.coordinates['white_diamond']

                color = self.get_average_pixel_color(check_x, check_y, radius=1)

                if self.is_white_pixel(color, tolerance=15):
                    pyautogui.moveTo(idle_x, idle_y, duration=0.5, tween=pyautogui.easeInOutQuad)
                    break

                time.sleep(0.1)

            start_time = time.time()
            while True:
                if not self.toggle:
                    break
                if (time.time() - start_time) > 9:
                    break

                search_area = self.coordinates['reel_bar']
                found_pos = self.find_pixel_color(*search_area, (109, 198, 164), 1)

                if found_pos is None:
                    pyautogui.click()
                    border_x, border_y = self.coordinates['completed_border']
                    color = self.get_pixel_color(border_x, border_y)

            time.sleep(0.3)

            close_x, close_y = self.coordinates['close_button']
            autoit.mouse_move(close_x, close_y, 3)
            time.sleep(0.3)
            autoit.mouse_click("left")
            time.sleep(0.3)

            item_x, item_y = self.coordinates['first_item']
            autoit.mouse_move(item_x, item_y, 3)
            time.sleep(0.3)
            autoit.mouse_click("left")
            time.sleep(0.3)

            sell_x, sell_y = self.coordinates['sell_button']
            autoit.mouse_move(sell_x, sell_y, 3)
            time.sleep(0.3)
            autoit.mouse_click("left")
            time.sleep(0.3)

            confirm_x, confirm_y = self.coordinates['confirm_button']
            autoit.mouse_move(confirm_x, confirm_y, 3)
            time.sleep(0.3)
            autoit.mouse_click("left")
            time.sleep(0.3)

            pyautogui.moveTo(idle_x, idle_y, duration=0.5, tween=pyautogui.easeInOutQuad)
            time.sleep(0.5)

    def start_automation(self):
        if not self.toggle:
            self.toggle = True
            self.running = True
            self.thread = threading.Thread(target=self.mouse_automation_loop)
            self.thread.daemon = True
            self.thread.start()

    def stop_automation(self):
        self.toggle = False
        self.running = False
        if self.thread:
            self.thread.join(timeout=1)

class CalibrationOverlay(QWidget):
    coordinate_selected = pyqtSignal(int, int)
    calibration_cancelled = pyqtSignal()

    def __init__(self, message="Click to calibrate coordinate"):
        super().__init__()
        self.message = message
        self.mouse_pos = QPoint(0, 0)
        self.click_feedback_timer = QTimer()
        self.click_feedback_timer.timeout.connect(self.hide_click_feedback)
        self.show_click_feedback = False
        self.click_pos = QPoint(0, 0)

        self.setup_overlay()

    def setup_overlay(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        screen = QApplication.primaryScreen().geometry()
        self.setGeometry(screen)

        self.setMouseTracking(True)

        self.setCursor(Qt.CursorShape.CrossCursor)

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        painter.fillRect(self.rect(), QColor(128, 128, 128, 120))

        center_x = self.width() // 2
        center_y = self.height() // 2

        box_width = 700
        box_height = 220
        box_x = center_x - box_width // 2
        box_y = center_y - box_height // 2

        painter.fillRect(box_x, box_y, box_width, box_height, QColor(0, 0, 0, 220))

        painter.setPen(QPen(QColor(255, 255, 255), 3))
        painter.drawRect(box_x, box_y, box_width, box_height)

        painter.setPen(QColor(255, 255, 255))
        painter.setFont(QFont("Arial", 26, QFont.Weight.Bold))
        text_rect = painter.fontMetrics().boundingRect(self.message)
        text_x = center_x - text_rect.width() // 2
        text_y = center_y - 40
        painter.drawText(text_x, text_y, self.message)

        painter.setFont(QFont("Arial", 16))
        instruction = "Click anywhere on the screen to set coordinate"
        inst_rect = painter.fontMetrics().boundingRect(instruction)
        inst_x = center_x - inst_rect.width() // 2
        inst_y = center_y + 10
        painter.setPen(QColor(200, 200, 200))
        painter.drawText(inst_x, inst_y, instruction)

        painter.setFont(QFont("Arial", 14))
        esc_text = "Press ESC to cancel"
        esc_rect = painter.fontMetrics().boundingRect(esc_text)
        esc_x = center_x - esc_rect.width() // 2
        esc_y = center_y + 40
        painter.setPen(QColor(180, 180, 180))
        painter.drawText(esc_x, esc_y, esc_text)

        coord_text = f"Mouse Position: ({self.mouse_pos.x()}, {self.mouse_pos.y()})"
        painter.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        coord_rect = painter.fontMetrics().boundingRect(coord_text)
        coord_x = center_x - coord_rect.width() // 2
        coord_y = center_y + 80

        painter.fillRect(coord_x - 15, coord_y - 25, coord_rect.width() + 30, 35, QColor(0, 100, 200, 200))
        painter.setPen(QPen(QColor(255, 255, 255), 2))
        painter.drawRect(coord_x - 15, coord_y - 25, coord_rect.width() + 30, 35)

        painter.setPen(QColor(255, 255, 255))
        painter.drawText(coord_x, coord_y, coord_text)

        if self.show_click_feedback:
            local_pos = self.mapFromGlobal(self.click_pos)

            painter.setPen(QPen(QColor(0, 255, 0), 5))
            painter.drawEllipse(local_pos.x() - 25, local_pos.y() - 25, 50, 50)

            painter.setPen(QPen(QColor(255, 255, 255), 3))
            painter.drawLine(local_pos.x() - 20, local_pos.y(), local_pos.x() + 20, local_pos.y())
            painter.drawLine(local_pos.x(), local_pos.y() - 20, local_pos.x(), local_pos.y() + 20)

    def mouseMoveEvent(self, event):
        self.mouse_pos = event.globalPosition().toPoint()
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            click_x = event.globalPosition().toPoint().x()
            click_y = event.globalPosition().toPoint().y()

            self.click_pos = event.globalPosition().toPoint()
            self.show_click_feedback = True
            self.update()

            self.click_feedback_timer.start(200)

            self.selected_coords = (click_x, click_y)

    def hide_click_feedback(self):
        self.click_feedback_timer.stop()
        self.show_click_feedback = False

        x, y = self.selected_coords
        self.coordinate_selected.emit(x, y)
        self.close()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.calibration_cancelled.emit()
            self.close()

    def showEvent(self, event):
        super().showEvent(event)
        self.setFocus()
        self.activateWindow()
        self.raise_()

class CalibrationUI(QMainWindow):
    def __init__(self, automation):
        super().__init__()
        self.automation = automation

        self.calibrating = False
        self.current_calibration = None
        self.reel_bar_step = 1
        self.reel_bar_coords = []

        self.coord_labels = {
            'fish_button': 'Fish Button - Click to start fishing',
            'white_diamond': 'White Diamond - Pixel that turns white when fish is caught',
            'reel_bar': 'Reel Bar - The Reel progress bar',
            'completed_border': 'Completed Border - A pixel of the completed screen border',
            'close_button': 'Close Button - Close the sucuessfully caught fish',
            'first_item': 'First Item - Click the first item',
            'sell_button': 'Sell Button - Click to sell item',
            'confirm_button': 'Confirm Button - Confirm the sale',
            'mouse_idle_position': 'Mouse Idle Position - Where mouse will normally be. Must be in a place without UI.'
        }

        self.coord_labels_widgets = {}
        self.setup_ui()
        self.apply_dark_theme()

    def apply_dark_theme(self):
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1e1e1e;
                color: #ffffff;
            }
            QLabel {
                color: #ffffff;
                background-color: transparent;
            }
            QPushButton {
                background-color: #4a4a4a;
                color: white;
                border: 1px solid #666666;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #5a5a5a;
            }
            QPushButton:pressed {
                background-color: #3a3a3a;
            }
            QFrame {
                background-color: #2d2d2d;
                border: 1px solid #444444;
                border-radius: 4px;
            }
            QScrollArea {
                background-color: #1e1e1e;
                border: none;
            }
        """)

    def setup_ui(self):
        self.setWindowTitle("FishScope")
        self.setFixedSize(550, 750)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 15, 15, 15)

        title_label = QLabel("FishScope")
        title_font = QFont("Arial", 24, QFont.Weight.Bold)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("color: #ffffff; margin: 10px;")
        main_layout.addWidget(title_label)

        hotkey_frame = QFrame()
        hotkey_layout = QVBoxLayout(hotkey_frame)
        hotkey_layout.setContentsMargins(15, 10, 15, 10)

        hotkey_title = QLabel("Hotkeys:")
        hotkey_title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        hotkey_layout.addWidget(hotkey_title)

        f1_label = QLabel("F1 - Start Macro")
        f1_label.setStyleSheet("color: #00ff00; margin-left: 20px;")
        hotkey_layout.addWidget(f1_label)

        f2_label = QLabel("F2 - Stop Macro")
        f2_label.setStyleSheet("color: #ff4444; margin-left: 20px;")
        hotkey_layout.addWidget(f2_label)

        main_layout.addWidget(hotkey_frame)

        control_layout = QHBoxLayout()
        control_layout.setSpacing(10)

        self.start_btn = QPushButton("Start Macro (F1)")
        self.start_btn.clicked.connect(self.automation.start_automation)
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #00aa00;
                color: white;
                font-weight: bold;
                padding: 12px 20px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #00cc00;
            }
        """)
        control_layout.addWidget(self.start_btn)

        self.stop_btn = QPushButton("Stop Macro (F2)")
        self.stop_btn.clicked.connect(self.automation.stop_automation)
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #aa0000;
                color: white;
                font-weight: bold;
                padding: 12px 20px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #cc0000;
            }
        """)
        control_layout.addWidget(self.stop_btn)

        main_layout.addLayout(control_layout)

        calib_label = QLabel("Coordinate Calibration")
        calib_font = QFont("Arial", 14, QFont.Weight.Bold)
        calib_label.setFont(calib_font)
        calib_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        calib_label.setStyleSheet("margin: 20px 0 10px 0;")
        main_layout.addWidget(calib_label)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFixedHeight(350)

        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setSpacing(5)

        for coord_name, description in self.coord_labels.items():
            self.create_calibration_row(scroll_layout, coord_name, description)

        scroll_area.setWidget(scroll_widget)
        main_layout.addWidget(scroll_area)

        info_layout = QVBoxLayout()
        info_layout.setSpacing(5)

        auto_save_label = QLabel("Settings are automatically saved to fishscopeconfig.json")
        auto_save_label.setStyleSheet("color: #888888; font-size: 10px; text-align: center;")
        auto_save_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_layout.addWidget(auto_save_label)

        reset_layout = QHBoxLayout()
        reset_layout.addStretch()

        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.clicked.connect(self.reset_to_defaults)
        reset_btn.setStyleSheet("""
            QPushButton {
                background-color: #cc6600;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                font-size: 10px;
            }
            QPushButton:hover {
                background-color: #ee8800;
            }
        """)
        reset_layout.addWidget(reset_btn)
        reset_layout.addStretch()

        info_layout.addLayout(reset_layout)
        main_layout.addLayout(info_layout)

        credits_layout = QHBoxLayout()
        credits_layout.setContentsMargins(0, 20, 0, 0)

        creator_label = QLabel("Created by: cresqnt")
        creator_label.setStyleSheet("color: #888888; font-size: 10px;")
        credits_layout.addWidget(creator_label)

        discord_label = QLabel('<a href="https://discord.gg/6cuCu6ymkX" style="color: #7289da; text-decoration: none;">Discord for help: .gg/6cuCu6ymkX</a>')
        discord_label.setStyleSheet("color: #7289da; font-size: 10px;")
        discord_label.setOpenExternalLinks(True)
        credits_layout.addWidget(discord_label)

        credits_layout.addStretch()

        idea_label = QLabel("Auto Sell Idea: x2_c")
        idea_label.setStyleSheet("color: #888888; font-size: 10px;")
        credits_layout.addWidget(idea_label)

        main_layout.addLayout(credits_layout)

    def create_calibration_row(self, parent_layout, coord_name, description):
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background-color: #2d2d2d;
                border: 1px solid #444444;
                border-radius: 4px;
                margin: 2px;
            }
        """)

        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(10, 8, 10, 8)
        frame_layout.setSpacing(5)

        # Description
        desc_label = QLabel(description)
        desc_label.setFont(QFont("Arial", 9))
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #ffffff; background-color: transparent;")
        frame_layout.addWidget(desc_label)

        # Current coordinates
        coord_text = self.get_coord_text(coord_name)
        coord_label = QLabel(coord_text)
        coord_label.setFont(QFont("Arial", 8))
        coord_label.setStyleSheet("color: #cccccc; background-color: transparent;")
        frame_layout.addWidget(coord_label)

        # Calibrate button
        calib_btn = QPushButton("📍 Calibrate")
        calib_btn.clicked.connect(lambda: self.start_calibration(coord_name))
        calib_btn.setFixedWidth(120)
        calib_btn.setStyleSheet("""
            QPushButton {
                background-color: #0066cc;
                color: white;
                border: 1px solid #0088ff;
                padding: 8px 12px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 10px;
            }
            QPushButton:hover {
                background-color: #0088ff;
                border: 1px solid #00aaff;
            }
            QPushButton:pressed {
                background-color: #004499;
            }
        """)
        frame_layout.addWidget(calib_btn)

        parent_layout.addWidget(frame)

        # Store references for updating
        self.coord_labels_widgets[coord_name] = coord_label

    def get_coord_text(self, coord_name):
        coord = self.automation.coordinates[coord_name]
        if coord_name == 'reel_bar':
            return f"Current: ({coord[0]}, {coord[1]}) to ({coord[2]}, {coord[3]})"
        else:
            return f"Current: ({coord[0]}, {coord[1]})"

    def start_calibration(self, coord_name):
        if self.calibrating:
            return

        self.calibrating = True
        self.current_calibration = coord_name

        # Hide the main window during calibration for better focus
        self.hide()

        # Create overlay window with improved messaging
        if coord_name == 'reel_bar':
            display_name = self.coord_labels[coord_name].split(' - ')[0]
            message = f"{display_name} - Step 1: TOP-LEFT corner"
            self.reel_bar_step = 1
        else:
            # Get a cleaner name for display
            display_name = self.coord_labels[coord_name].split(' - ')[0]
            message = f"Calibrating: {display_name}"

        self.overlay = CalibrationOverlay(message)
        self.overlay.coordinate_selected.connect(self.on_calibration_click)
        self.overlay.calibration_cancelled.connect(self.cancel_calibration)

        # Show the overlay
        self.overlay.show()

    def on_calibration_click(self, x, y):
        if self.current_calibration == 'reel_bar':
            if self.reel_bar_step == 1:
                # Store top-left coordinates
                self.reel_bar_coords = [x, y]
                self.reel_bar_step = 2

                # Close current overlay
                self.overlay.close()

                # Show second overlay for bottom-right with improved messaging
                display_name = self.coord_labels['reel_bar'].split(' - ')[0]
                message = f"{display_name} - Step 2: BOTTOM-RIGHT corner"
                self.overlay = CalibrationOverlay(message)
                self.overlay.coordinate_selected.connect(self.on_calibration_click)
                self.overlay.calibration_cancelled.connect(self.cancel_calibration)
                self.overlay.show()
                return
            else:
                # Complete reel bar calibration with bottom-right
                self.automation.coordinates['reel_bar'] = (
                    self.reel_bar_coords[0], self.reel_bar_coords[1], x, y
                )
        else:
            # Regular coordinate calibration
            self.automation.coordinates[self.current_calibration] = (x, y)

        # Close overlay and complete calibration
        self.overlay.close()
        self.complete_calibration()

    def complete_calibration(self):
        self.calibrating = False

        # Update the coordinate label
        coord_label = self.coord_labels_widgets[self.current_calibration]
        coord_label.setText(self.get_coord_text(self.current_calibration))

        # Auto-save the calibration
        self.automation.save_calibration()

        # Get the display name for the success message
        display_name = self.coord_labels[self.current_calibration].split(' - ')[0]

        self.current_calibration = None

        # Show the main window again
        self.show()
        self.raise_()  # Bring window to front
        self.activateWindow()  # Make it the active window

        # Show a brief success message
        msg = QMessageBox(self)
        msg.setWindowTitle("Calibration Complete")
        msg.setText(f"{display_name} calibrated successfully!\n\nSettings have been automatically saved.")
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setStyleSheet("""
            QMessageBox {
                background-color: #2d2d2d;
                color: white;
            }
            QMessageBox QPushButton {
                background-color: #00aa00;
                color: white;
                border: 1px solid #00cc00;
                padding: 8px 16px;
                border-radius: 4px;
                min-width: 80px;
                font-weight: bold;
            }
            QMessageBox QPushButton:hover {
                background-color: #00cc00;
            }
        """)
        msg.exec()

    def cancel_calibration(self):
        self.calibrating = False
        self.current_calibration = None

        # Close overlay if it exists
        if hasattr(self, 'overlay') and self.overlay:
            self.overlay.close()

        # Show the main window again
        self.show()
        self.raise_()  # Bring window to front
        self.activateWindow()  # Make it the active window

    def reset_to_defaults(self):
        # Confirm reset
        msg = QMessageBox()
        msg.setWindowTitle("Reset to Defaults")
        msg.setText("Are you sure you want to reset all coordinates to default values?\nThis will overwrite your current calibration.")
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg.setDefaultButton(QMessageBox.StandardButton.No)
        msg.setStyleSheet("""
            QMessageBox {
                background-color: #2d2d2d;
                color: white;
            }
            QMessageBox QPushButton {
                background-color: #4a4a4a;
                color: white;
                border: 1px solid #666666;
                padding: 6px 12px;
                border-radius: 3px;
                min-width: 60px;
            }
        """)

        if msg.exec() == QMessageBox.StandardButton.Yes:
            # Reset to default coordinates
            self.automation.coordinates = {
                'fish_button': (850, 830),
                'white_diamond': (1176, 836),
                'reel_bar': (757, 762, 1161, 782),
                'completed_border': (1139, 762),
                'close_button': (1113, 342),
                'first_item': (825, 408),
                'sell_button': (595, 806),
                'confirm_button': (805, 618),
                'mouse_idle_position': (self.automation.screen_width // 2, self.automation.screen_height // 2)
            }

            # Auto-save the reset coordinates
            self.automation.save_calibration()

            # Update all coordinate labels
            for coord_name in self.coord_labels.keys():
                coord_label = self.coord_labels_widgets[coord_name]
                coord_label.setText(self.get_coord_text(coord_name))

            # Show confirmation
            success_msg = QMessageBox()
            success_msg.setWindowTitle("Reset Complete")
            success_msg.setText("All coordinates have been reset to defaults and auto-saved!")
            success_msg.setStyleSheet("""
                QMessageBox {
                    background-color: #2d2d2d;
                    color: white;
                }
                QMessageBox QPushButton {
                    background-color: #4a4a4a;
                    color: white;
                    border: 1px solid #666666;
                    padding: 6px 12px;
                    border-radius: 3px;
                    min-width: 60px;
                }
            """)
            success_msg.exec()

    def closeEvent(self, event):
        self.automation.stop_automation()
        event.accept()

def main():
    app = QApplication(sys.argv)

    # Set application properties
    app.setApplicationName("FishScope")
    app.setApplicationVersion("1.0")
    app.setOrganizationName("cresqnt")

    automation = MouseAutomation()
    ui = CalibrationUI(automation)

    # Set up hotkeys
    keyboard.add_hotkey('f1', automation.start_automation)
    keyboard.add_hotkey('f2', automation.stop_automation)

    print("FishScope Mouse Automation with PyQt6 GUI")
    print("F1: Start automation")
    print("F2: Stop automation")

    ui.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()