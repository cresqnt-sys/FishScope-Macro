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
                            QMessageBox, QGroupBox, QComboBox)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject, QPoint
from PyQt6.QtGui import QFont, QCursor, QPainter, QPen, QColor, QIcon
from updater import AutoUpdater

pyautogui.FAILSAFE = False

class MouseAutomation:
    def __init__(self):
        self.toggle = False
        self.running = False
        self.thread = None
        self.config_file = "fishscopeconfig.json"

        # Get screen dimensions using multiple methods for better compatibility
        self.screen_width, self.screen_height = self.get_screen_dimensions()
        print(f"Detected screen dimensions: {self.screen_width}x{self.screen_height}")
        self.coordinates = {
            'fish_button': (850, 830),
            'white_diamond': (1176, 836),
            'reel_bar': (757, 762, 1161, 782),
            'completed_border': (1139, 762),
            'close_button': (1113, 342),
            'first_item': (827, 401),
            'sell_button': (589, 801),
            'confirm_button': (802, 620),
            'mouse_idle_position': (self.screen_width // 2, self.screen_height // 2),
            'shaded_area': (955, 767)
        }

        self.shaded_color = (109, 198, 164)

        self.load_calibration()

    def get_screen_dimensions(self):
        """Get screen dimensions using multiple methods for better compatibility"""
        try:
            # Try using Windows API for virtual screen (all monitors)
            user32 = ctypes.windll.user32
            # Get virtual screen dimensions (covers all monitors)
            virtual_width = user32.GetSystemMetrics(78)  # SM_CXVIRTUALSCREEN
            virtual_height = user32.GetSystemMetrics(79)  # SM_CYVIRTUALSCREEN
            if virtual_width > 0 and virtual_height > 0:
                return (virtual_width, virtual_height)

            # Fallback to primary screen
            screensize = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
            if screensize[0] > 0 and screensize[1] > 0:
                return screensize
        except:
            pass

        try:
            # Fallback to pyautogui
            return pyautogui.size()
        except:
            # Final fallback to common resolution
            return (1920, 1080)



    def save_calibration(self):
        try:
            config_data = {
                'coordinates': self.coordinates,
                'shaded_color': self.shaded_color,
                'config_version': '1.0'
            }
            with open(self.config_file, 'w') as f:
                json.dump(config_data, f, indent=2)
        except Exception:
            pass

    def load_calibration(self):
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    saved_data = json.load(f)

                if isinstance(saved_data, dict) and 'coordinates' in saved_data:
                    for key, coord in saved_data['coordinates'].items():
                        if key in self.coordinates:
                            if key == 'reel_bar' and len(coord) == 4:
                                self.coordinates[key] = coord
                            elif len(coord) == 2:
                                self.coordinates[key] = coord

                    if 'shaded_color' in saved_data:
                        self.shaded_color = tuple(saved_data['shaded_color'])
                else:
                    # Legacy format support
                    for key, coord in saved_data.items():
                        if key in self.coordinates:
                            if key == 'reel_bar' and len(coord) == 4:
                                self.coordinates[key] = coord
                            elif len(coord) == 2:
                                self.coordinates[key] = coord

        except Exception:
            pass



    def get_mouse_position(self):
        return pyautogui.position()







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

        # Check every pixel for better detection
        for y in range(height):
            for x in range(width):
                pixel = screenshot.getpixel((x, y))
                if self.color_match(pixel, target_color, tolerance):
                    return (x1 + x, y1 + y)
        return None

    def find_pixel_color_enhanced(self, x1, y1, x2, y2, target_color, tolerance=5):
        """Enhanced color detection using pixel search"""
        screenshot = ImageGrab.grab(bbox=(x1, y1, x2, y2))
        width, height = screenshot.size

        # Search every pixel for color matching
        for y in range(height):
            for x in range(width):
                pixel = screenshot.getpixel((x, y))
                if self.color_match(pixel, target_color, tolerance):
                    return (x1 + x, y1 + y)

        return None

    def color_match(self, color1, color2, tolerance):
        return all(abs(c1 - c2) <= tolerance for c1, c2 in zip(color1, color2))

    def detect_current_shaded_color(self):
        """Detect the current shaded color from the calibrated shaded area location."""
        shaded_x, shaded_y = self.coordinates['shaded_area']
        current_shaded_color = self.get_average_pixel_color(shaded_x, shaded_y, radius=2)

        return current_shaded_color

    def mouse_automation_loop(self):
        first_loop = True

        while self.running and self.toggle:
            if not self.toggle:
                break

            # Get idle position for mouse management
            idle_x, idle_y = self.coordinates['mouse_idle_position']

            # Move to fish button and click (faster timing)
            fish_x, fish_y = self.coordinates['fish_button']
            autoit.mouse_move(fish_x, fish_y, 3)
            time.sleep(0.1)  # Reduced from 0.3
            autoit.mouse_click("left")
            # Move to idle area immediately after click
            autoit.mouse_move(idle_x, idle_y, 3)
            time.sleep(0.15)  # Reduced from 0.3

            # Auto-sell (skip on first loop, faster timing)
            if not first_loop:
                # Click first item
                item_x, item_y = self.coordinates['first_item']
                autoit.mouse_move(item_x, item_y, 3)
                time.sleep(0.1)  # Reduced from 0.3
                autoit.mouse_click("left")
                autoit.mouse_move(idle_x, idle_y, 3)  # Move to idle
                time.sleep(0.15)  # Reduced from 0.3

                # Click sell button
                sell_x, sell_y = self.coordinates['sell_button']
                autoit.mouse_move(sell_x, sell_y, 3)
                time.sleep(0.1)  # Reduced from 0.3
                autoit.mouse_click("left")
                autoit.mouse_move(idle_x, idle_y, 3)  # Move to idle
                time.sleep(0.15)  # Reduced from 0.3

                # Click confirm button
                confirm_x, confirm_y = self.coordinates['confirm_button']
                autoit.mouse_move(confirm_x, confirm_y, 3)
                time.sleep(0.1)  # Reduced from 0.3
                autoit.mouse_click("left")
                autoit.mouse_move(idle_x, idle_y, 3)  # Move to idle
                time.sleep(0.15)  # Reduced from 0.3
            else:
                first_loop = False

            # Initialize bar color variable
            bar_color = None

            # Wait for white pixel
            while True:
                if not self.toggle:
                    return

                check_x, check_y = self.coordinates['white_diamond']
                color = self.get_pixel_color(check_x, check_y)

                # Use tolerance-based white detection instead of exact match
                if self.is_white_pixel(color, tolerance=15):  # More flexible white detection
                    # Move mouse to idle position (using calibrated coordinate)
                    autoit.mouse_move(idle_x, idle_y, 3)
                    time.sleep(0.05)  # 50ms delay

                    # Sample bar color from calibrated shaded area
                    shaded_x, shaded_y = self.coordinates['shaded_area']
                    bar_color = self.get_pixel_color(shaded_x, shaded_y)

                    break

                time.sleep(0.1)  # 100ms delay

            # Bar clicking loop with 9-second timeout
            start_time = time.time()
            while True:
                if not self.toggle:
                    break
                if (time.time() - start_time) > 9:  # 9000ms timeout
                    break

                # PixelSearch equivalent - search for bar color in reel area
                search_area = self.coordinates['reel_bar']
                found_pos = self.find_pixel_color_enhanced(*search_area, bar_color, tolerance=5)

                if found_pos is not None:
                    # Color found - don't click
                    pass
                else:
                    # Color not found - click
                    autoit.mouse_click("left")

                # No delay between checks - continuous loop

            time.sleep(0.3)  # 300ms delay

            # Close the catch screen (faster)
            close_x, close_y = self.coordinates['close_button']
            autoit.mouse_move(close_x, close_y, 3)
            time.sleep(0.2)  # Reduced from 0.7
            autoit.mouse_click("left")
            # Move to idle area immediately after click
            autoit.mouse_move(idle_x, idle_y, 3)
            time.sleep(0.15)  # Reduced from 0.3

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

        # Get the virtual desktop geometry to cover all screens
        app = QApplication.instance()
        desktop = app.primaryScreen().virtualGeometry()
        self.setGeometry(desktop)

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

        # Show current mouse position
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

            # Draw outer circle (green)
            painter.setPen(QPen(QColor(0, 255, 0), 5))
            painter.drawEllipse(local_pos.x() - 25, local_pos.y() - 25, 50, 50)

            # Draw precise crosshair (white) - ensure it's perfectly centered
            painter.setPen(QPen(QColor(255, 255, 255), 3))
            center_x = local_pos.x()
            center_y = local_pos.y()
            painter.drawLine(center_x - 20, center_y, center_x + 20, center_y)
            painter.drawLine(center_x, center_y - 20, center_x, center_y + 20)

            # Draw center dot for precise targeting
            painter.setPen(QPen(QColor(255, 0, 0), 2))
            painter.drawEllipse(center_x - 2, center_y - 2, 4, 4)

    def mouseMoveEvent(self, event):
        # Use QCursor.pos() for more reliable global position detection
        self.mouse_pos = QCursor.pos()
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # Use QCursor.pos() for more reliable global position detection
            global_pos = QCursor.pos()
            click_x = global_pos.x()
            click_y = global_pos.y()

            self.click_pos = global_pos
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

        # Initialize auto updater
        self.auto_updater = AutoUpdater(self)

        self.coord_labels = {
            'fish_button': 'Fish Button - Click to start fishing',
            'white_diamond': 'White Diamond - Pixel that turns white when fish is caught',
            'shaded_area': 'Shaded Area - Pixel location to sample bar color from (should be on the reel bar)',
            'reel_bar': 'Reel Bar - The Reel progress bar',
            'completed_border': 'Completed Border - A pixel of the completed screen border',
            'close_button': 'Close Button - Close the sucuessfully caught fish',
            'first_item': 'First Item - Click the first item',
            'sell_button': 'Sell Button - Click to sell item',
            'confirm_button': 'Confirm Button - Confirm the sale',
            'mouse_idle_position': 'Mouse Idle Position - Where mouse will normally be. Must be in a place without UI.'
        }

        self.coord_labels_widgets = {}

        # Premade calibrations
        self.premade_calibrations = {
            "1920x1080 | Windowed": {
                'fish_button': (851, 801),
                'white_diamond': (1177, 803),
                'reel_bar': (758, 729, 1159, 744),
                'completed_border': (1135, 745),
                'close_button': (1108, 336),
                'first_item': (830, 407),
                'sell_button': (592, 774),
                'confirm_button': (789, 615),
                'mouse_idle_position': (975, 210),
                'shaded_area': (947, 732)
            },
            "1920x1080 | Full Screen": {
                'fish_button': (852, 837),
                'white_diamond': (1176, 837),
                'reel_bar': (757, 762, 1162, 781),
                'completed_border': (1139, 763),
                'close_button': (1113, 344),
                'first_item': (834, 409),
                'sell_button': (590, 805),
                'confirm_button': (807, 629),
                'mouse_idle_position': (1365, 805),
                'shaded_area': (946, 765)
            },
            "2560x1440 | Windowed": {
                'fish_button': (1149, 1089),
                'white_diamond': (1536, 1093),
                'reel_bar': (1042, 1000, 1515, 1026),
                'completed_border': (1479, 959),
                'close_button': (1455, 491),
                'first_item': (1101, 546),
                'sell_button': (779, 1054),
                'confirm_button': (1054, 827),
                'mouse_idle_position': (1281, 1264),
                'shaded_area': (1271, 1008)
            },
            "1366x768 | Full Screen": {
                'fish_button': (594, 588),
                'white_diamond': (866, 592),
                'reel_bar': (513, 529, 855, 545),
                'completed_border': (839, 577),
                'close_button': (817, 211),
                'first_item': (591, 287),
                'sell_button': (420, 570),
                'confirm_button': (567, 443),
                'mouse_idle_position': (1115, 381),
                'shaded_area': (664, 531)
            }
        }

        self.setup_ui()
        self.apply_clean_theme()

    def apply_clean_theme(self):
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1a1a1a;
                color: #e0e0e0;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QLabel {
                color: #e0e0e0;
                background-color: transparent;
            }
            QPushButton {
                background-color: #2d2d2d;
                color: #e0e0e0;
                border: 1px solid #404040;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: 500;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #3a3a3a;
                border-color: #555555;
            }
            QPushButton:pressed {
                background-color: #252525;
                border-color: #606060;
            }
            QFrame {
                background-color: #2d2d2d;
                border: 1px solid #404040;
                border-radius: 8px;
            }
            QScrollArea {
                background-color: #1a1a1a;
                border: 1px solid #404040;
                border-radius: 6px;
            }
            QScrollArea QWidget {
                background-color: #2d2d2d;
            }
            QGroupBox {
                font-weight: 600;
                font-size: 14px;
                color: #e0e0e0;
                border: 2px solid #404040;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px 0 8px;
                background-color: #1a1a1a;
            }
        """)

    def setup_ui(self):
        self.setWindowTitle("FishScope Macro")
        self.setFixedSize(600, 900)

        # Set application icon
        if os.path.exists("icon.ico"):
            self.setWindowIcon(QIcon("icon.ico"))

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 15, 15, 15)

        # Header Section - More compact
        header_layout = QVBoxLayout()
        header_layout.setSpacing(4)

        title_label = QLabel("FishScope Macro")
        title_font = QFont("Segoe UI", 18, QFont.Weight.Bold)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("color: #ffffff; margin: 4px 0;")
        header_layout.addWidget(title_label)

        subtitle_label = QLabel('<a href="https://www.roblox.com/games/1980495071/Donations-D" style="color: #4a9eff; text-decoration: none;">Feel free to donate</a>')
        subtitle_font = QFont("Segoe UI", 8)
        subtitle_label.setFont(subtitle_font)
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle_label.setStyleSheet("color: #888888; margin-bottom: 6px;")
        subtitle_label.setOpenExternalLinks(True)
        header_layout.addWidget(subtitle_label)

        main_layout.addLayout(header_layout)

        # Control Section - More compact
        control_group = QGroupBox("Macro Controls")
        control_layout = QVBoxLayout(control_group)
        control_layout.setSpacing(8)
        control_layout.setContentsMargins(12, 15, 12, 12)

        # Hotkey info - More compact
        hotkey_info_layout = QHBoxLayout()
        hotkey_info_layout.setSpacing(15)

        f1_label = QLabel("F1 - Start")
        f1_label.setStyleSheet("color: #28a745; font-weight: 500; font-size: 11px;")
        hotkey_info_layout.addWidget(f1_label)

        f2_label = QLabel("F2 - Stop")
        f2_label.setStyleSheet("color: #dc3545; font-weight: 500; font-size: 11px;")
        hotkey_info_layout.addWidget(f2_label)

        hotkey_info_layout.addStretch()
        control_layout.addLayout(hotkey_info_layout)

        # Control buttons - More compact
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)

        self.start_btn = QPushButton("Start Macro")
        self.start_btn.clicked.connect(self.automation.start_automation)
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                font-weight: 600;
                padding: 10px 20px;
                font-size: 13px;
                border: none;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #218838;
            }
            QPushButton:pressed {
                background-color: #1e7e34;
            }
        """)
        button_layout.addWidget(self.start_btn)

        self.stop_btn = QPushButton("Stop Macro")
        self.stop_btn.clicked.connect(self.automation.stop_automation)
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #dc3545;
                color: white;
                font-weight: 600;
                padding: 10px 20px;
                font-size: 13px;
                border: none;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #c82333;
            }
            QPushButton:pressed {
                background-color: #bd2130;
            }
        """)
        button_layout.addWidget(self.stop_btn)

        control_layout.addLayout(button_layout)
        main_layout.addWidget(control_group)

        # Premade Calibrations Section - More compact
        premade_group = QGroupBox("Premade Calibrations")
        premade_layout = QVBoxLayout(premade_group)
        premade_layout.setContentsMargins(12, 15, 12, 12)
        premade_layout.setSpacing(8)

        premade_info = QLabel("Select a premade calibration to quickly set up coordinates")
        premade_info.setStyleSheet("color: #888888; font-size: 11px; margin-bottom: 6px;")
        premade_layout.addWidget(premade_info)

        # Premade calibrations selector - More compact
        premade_selector_layout = QHBoxLayout()
        premade_selector_layout.setSpacing(10)

        premade_label = QLabel("Configuration:")
        premade_label.setStyleSheet("color: #e0e0e0; font-weight: 500;")
        premade_selector_layout.addWidget(premade_label)

        self.premade_combo = QComboBox()
        self.premade_combo.addItem("Select a premade calibration...")
        for config_name in self.premade_calibrations.keys():
            self.premade_combo.addItem(config_name)
        self.premade_combo.setStyleSheet("""
            QComboBox {
                background-color: #2d2d2d;
                color: #e0e0e0;
                border: 1px solid #555555;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 11px;
                min-width: 180px;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid #e0e0e0;
                margin-right: 5px;
            }
            QComboBox QAbstractItemView {
                background-color: #2d2d2d;
                color: #e0e0e0;
                border: 1px solid #555555;
                selection-background-color: #4a9eff;
            }
        """)
        premade_selector_layout.addWidget(self.premade_combo)

        apply_premade_btn = QPushButton("Apply")
        apply_premade_btn.clicked.connect(self.apply_premade_calibration)
        apply_premade_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                font-weight: 600;
                padding: 6px 14px;
                font-size: 11px;
                border: none;
                border-radius: 6px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #218838;
            }
            QPushButton:pressed {
                background-color: #1e7e34;
            }
        """)
        premade_selector_layout.addWidget(apply_premade_btn)
        premade_selector_layout.addStretch()

        premade_layout.addLayout(premade_selector_layout)
        main_layout.addWidget(premade_group)

        # Calibration Section - More compact
        calibration_group = QGroupBox("Coordinate Calibration")
        calibration_layout = QVBoxLayout(calibration_group)
        calibration_layout.setContentsMargins(12, 15, 12, 12)
        calibration_layout.setSpacing(6)

        calib_info = QLabel("Click 'Calibrate' for each coordinate to set up automation points")
        calib_info.setStyleSheet("color: #888888; font-size: 11px; margin-bottom: 6px;")
        calibration_layout.addWidget(calib_info)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setSpacing(3)
        scroll_layout.setContentsMargins(4, 4, 4, 4)

        for coord_name, description in self.coord_labels.items():
            self.create_calibration_row(scroll_layout, coord_name, description)

        # Set minimum size to ensure all content is scrollable
        # 10 items * ~50px per item + margins = ~520px minimum height
        scroll_widget.setMinimumHeight(520)

        scroll_area.setWidget(scroll_widget)
        calibration_layout.addWidget(scroll_area)
        main_layout.addWidget(calibration_group)

        # Settings Section - More compact
        settings_group = QGroupBox("Settings")
        settings_layout = QVBoxLayout(settings_group)
        settings_layout.setContentsMargins(12, 15, 12, 12)
        settings_layout.setSpacing(8)

        auto_save_label = QLabel("Settings are automatically saved to fishscopeconfig.json")
        auto_save_label.setStyleSheet("color: #888888; font-size: 12px;")
        auto_save_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        settings_layout.addWidget(auto_save_label)

        # Settings buttons layout
        settings_buttons_layout = QHBoxLayout()
        settings_buttons_layout.setSpacing(12)
        settings_buttons_layout.addStretch()

        # Check for updates button
        update_btn = QPushButton("Check for Updates")
        update_btn.clicked.connect(self.check_for_updates)
        update_btn.setStyleSheet("""
            QPushButton {
                background-color: #17a2b8;
                color: white;
                font-weight: 600;
                padding: 8px 16px;
                font-size: 12px;
                border: none;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #138496;
            }
            QPushButton:pressed {
                background-color: #0f6674;
            }
        """)
        settings_buttons_layout.addWidget(update_btn)

        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.clicked.connect(self.reset_to_defaults)
        reset_btn.setStyleSheet("""
            QPushButton {
                background-color: #fd7e14;
                color: white;
                font-weight: 600;
                padding: 8px 16px;
                font-size: 12px;
                border: none;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #e8650e;
            }
            QPushButton:pressed {
                background-color: #d15a0a;
            }
        """)
        settings_buttons_layout.addWidget(reset_btn)
        settings_buttons_layout.addStretch()

        settings_layout.addLayout(settings_buttons_layout)
        main_layout.addWidget(settings_group)

        # Footer Section - More compact
        footer_layout = QHBoxLayout()
        footer_layout.setContentsMargins(0, 10, 0, 0)
        footer_layout.setSpacing(12)

        creator_label = QLabel("Created by: cresqnt")
        creator_label.setStyleSheet("color: #888888; font-size: 11px;")
        footer_layout.addWidget(creator_label)

        discord_label = QLabel('<a href="https://discord.gg/6cuCu6ymkX" style="color: #4a9eff; text-decoration: none;">Discord for help: .gg/6cuCu6ymkX</a>')
        discord_label.setStyleSheet("color: #4a9eff; font-size: 9px;")
        discord_label.setOpenExternalLinks(True)
        footer_layout.addWidget(discord_label)

        footer_layout.addStretch()

        idea_label = QLabel("Auto Sell Idea: x2_c")
        idea_label.setStyleSheet("color: #888888; font-size: 11px;")
        footer_layout.addWidget(idea_label)

        main_layout.addLayout(footer_layout)

    def create_calibration_row(self, parent_layout, coord_name, description):
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background-color: #3a3a3a;
                border: 1px solid #555555;
                border-radius: 6px;
                margin: 2px;
            }
        """)

        frame_layout = QHBoxLayout(frame)
        frame_layout.setContentsMargins(8, 6, 8, 6)
        frame_layout.setSpacing(10)

        # Left side - Description and coordinates
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)

        # Description
        desc_label = QLabel(description)
        desc_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Medium))
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #e0e0e0; background-color: transparent;")
        info_layout.addWidget(desc_label)

        # Current coordinates
        coord_text = self.get_coord_text(coord_name)
        coord_label = QLabel(coord_text)
        coord_label.setFont(QFont("Segoe UI", 8))
        coord_label.setStyleSheet("color: #aaaaaa; background-color: transparent;")
        info_layout.addWidget(coord_label)

        frame_layout.addLayout(info_layout)
        frame_layout.addStretch()

        # Right side - Calibrate button
        calib_btn = QPushButton("Calibrate")
        calib_btn.clicked.connect(lambda: self.start_calibration(coord_name))
        calib_btn.setFixedWidth(85)
        calib_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a9eff;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 5px;
                font-weight: 600;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #357abd;
            }
            QPushButton:pressed {
                background-color: #2c5aa0;
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
                # Complete reel bar calibration with bottom-right coordinates
                self.automation.coordinates['reel_bar'] = (
                    self.reel_bar_coords[0], self.reel_bar_coords[1], x, y
                )
        else:
            # Regular coordinate calibration
            self.automation.coordinates[self.current_calibration] = (x, y)

        # Close overlay
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

    def apply_premade_calibration(self, config_name=None):
        """Apply the selected premade calibration."""
        if config_name:
            selected_text = config_name
        else:
            selected_text = self.premade_combo.currentText()

        if selected_text == "Select a premade calibration..." or selected_text not in self.premade_calibrations:
            msg = QMessageBox(self)
            msg.setWindowTitle("No Selection")
            msg.setText("Please select a premade calibration from the dropdown.")
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.setStyleSheet("""
                QMessageBox {
                    background-color: #2d2d2d;
                    color: white;
                }
                QMessageBox QPushButton {
                    background-color: #fd7e14;
                    color: white;
                    border: 1px solid #e8650e;
                    padding: 8px 16px;
                    border-radius: 4px;
                    min-width: 80px;
                    font-weight: bold;
                }
                QMessageBox QPushButton:hover {
                    background-color: #e8650e;
                }
            """)
            msg.exec()
            return

        # Skip confirmation if called programmatically
        if not config_name:
            # Confirm application
            msg = QMessageBox(self)
            msg.setWindowTitle("Apply Premade Calibration")
            msg.setText(f"Are you sure you want to apply the '{selected_text}' calibration?\n\nThis will overwrite your current coordinate settings.")
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

            if msg.exec() != QMessageBox.StandardButton.Yes:
                return

        # Apply the premade calibration
        premade_coords = self.premade_calibrations[selected_text]

        # Update coordinates directly
        for coord_name, coord_value in premade_coords.items():
            if coord_name in self.automation.coordinates:
                self.automation.coordinates[coord_name] = coord_value

        # Update all coordinate labels in the UI
        for coord_name in self.coord_labels_widgets:
            coord_label = self.coord_labels_widgets[coord_name]
            coord_label.setText(self.get_coord_text(coord_name))

        # Auto-save the calibration
        self.automation.save_calibration()

        # Reset combo box selection if called from UI
        if not config_name:
            self.premade_combo.setCurrentIndex(0)

        # Show success message
        success_msg = QMessageBox(self)
        success_msg.setWindowTitle("Calibration Applied")
        success_msg.setText(f"'{selected_text}' calibration has been applied successfully!\n\nSettings have been automatically saved.")
        success_msg.setIcon(QMessageBox.Icon.Information)
        success_msg.setStyleSheet("""
            QMessageBox {
                background-color: #2d2d2d;
                color: white;
            }
            QMessageBox QPushButton {
                background-color: #28a745;
                color: white;
                border: 1px solid #218838;
                padding: 8px 16px;
                border-radius: 4px;
                min-width: 80px;
                font-weight: bold;
            }
            QMessageBox QPushButton:hover {
                background-color: #218838;
            }
        """)
        success_msg.exec()

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
                'first_item': (827, 401),
                'sell_button': (589, 801),
                'confirm_button': (802, 620),
                'mouse_idle_position': (self.automation.screen_width // 2, self.automation.screen_height // 2),
                'shaded_area': (955, 767)  # Default bar color sampling location
            }

            # Reset to default shaded color
            self.automation.shaded_color = (109, 198, 164)

            # Auto-save the reset coordinates
            self.automation.save_calibration()

            # Update all coordinate labels
            self.update_all_coordinate_labels()

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

    def update_all_coordinate_labels(self):
        """Update all coordinate labels to reflect current coordinates."""
        for coord_name in self.coord_labels.keys():
            if coord_name in self.coord_labels_widgets:
                coord_label = self.coord_labels_widgets[coord_name]
                coord_label.setText(self.get_coord_text(coord_name))

    def set_1080p_windowed_config(self):
        """Set configuration to 1080p windowed mode"""
        self.apply_premade_calibration("1920x1080 | Windowed")

    def check_for_updates(self):
        """Manually check for updates"""
        self.auto_updater.check_for_updates(silent=False)

    def closeEvent(self, event):
        self.automation.stop_automation()
        event.accept()

def main():
    app = QApplication(sys.argv)

    # Set application properties
    app.setApplicationName("FishScope")
    app.setApplicationVersion("1.0")
    app.setOrganizationName("cresqnt")

    # Set application icon
    if os.path.exists("icon.ico"):
        app.setWindowIcon(QIcon("icon.ico"))

    automation = MouseAutomation()
    ui = CalibrationUI(automation)

    # Set up hotkeys
    keyboard.add_hotkey('f1', automation.start_automation)
    keyboard.add_hotkey('f2', automation.stop_automation)



    ui.show()

    # Check for updates on startup (silent mode - only show if update available)
    QTimer.singleShot(2000, lambda: ui.auto_updater.check_for_updates(silent=True))

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
