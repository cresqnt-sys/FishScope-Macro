import time
import threading
import keyboard
from PIL import ImageGrab
import ctypes
import autoit
import json
import os
import sys
import concurrent.futures
from PyQt6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout,
                            QWidget, QPushButton, QLabel, QFrame, QScrollArea,
                            QMessageBox, QGroupBox, QComboBox, QCheckBox, QLineEdit, QSpinBox, QTabWidget)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject, QPoint
from PyQt6.QtGui import QFont, QCursor, QPainter, QPen, QColor, QIcon, QLinearGradient, QBrush
from updater import AutoUpdater
from auto_sell import AutoSellManager
import requests
import re
from datetime import datetime, timezone
from itertools import product
import pytesseract
import shutil
import cv2
from fuzzywuzzy import process
import logging
from pathlib import Path

# PyInstaller resource path helper
def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    
    return os.path.join(base_path, relative_path)

# Configure Tesseract OCR path
def setup_tesseract():
    """Setup Tesseract OCR by checking PATH and common installation directories"""
    try:
        # First check if tesseract is already available in PATH
        if shutil.which('tesseract'):
            print("Tesseract found in PATH")
            return True
    except Exception:
        pass
    
    # Common Tesseract installation paths
    if os.name == 'nt':  # Windows
        common_paths = [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            os.path.expanduser(r"~\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"),
            r"C:\tesseract\tesseract.exe",
            r"D:\Program Files\Tesseract-OCR\tesseract.exe",
            r"D:\Program Files (x86)\Tesseract-OCR\tesseract.exe"
        ]
    
    # Check each common path
    for path in common_paths:
        if os.path.exists(path):
            print(f"Found Tesseract at: {path}")
            pytesseract.pytesseract.tesseract_cmd = path
            
            # Test if the installation works
            try:
                from PIL import Image
                import numpy as np
                # Create a simple test image
                test_img = Image.new('RGB', (100, 30), color='white')
                pytesseract.image_to_string(test_img)
                print("Tesseract configuration successful")
                return True
            except Exception as e:
                print(f"Tesseract test failed for {path}: {e}")
                continue
    
    # If not found in common paths, try to find it in Program Files
    try:
        import glob
        program_files_paths = [
            r"C:\Program Files\*esseract*\tesseract.exe",
            r"C:\Program Files (x86)\*esseract*\tesseract.exe"
        ]
        
        for pattern in program_files_paths:
            matches = glob.glob(pattern)
            for match in matches:
                if os.path.exists(match):
                    print(f"Found Tesseract at: {match}")
                    pytesseract.pytesseract.tesseract_cmd = match
                    
                    # Test if the installation works
                    try:
                        from PIL import Image
                        test_img = Image.new('RGB', (100, 30), color='white')
                        pytesseract.image_to_string(test_img)
                        print("Tesseract configuration successful")
                        return True
                    except Exception as e:
                        print(f"Tesseract test failed for {match}: {e}")
                        continue
    except Exception:
        pass
    
    print("Warning: Tesseract OCR not found in PATH or common installation directories.")
    print("Please install Tesseract OCR or ensure it's in your PATH.")
    print("Download from: https://github.com/UB-Mannheim/tesseract/wiki")
    return False

# Initialize Tesseract configuration
setup_tesseract()

# Import the external macro scripts
try:
    from autoalign import auto_align_camera
    from fishinglocation import run_macro as run_fishing_location_macro, macro_actions as fishing_location_actions
    from shoppath import run_macro as run_shop_path_macro, macro_actions as shop_path_actions
    EXTERNAL_SCRIPTS_AVAILABLE = True
    print("External macro scripts loaded successfully")
except ImportError as e:
    EXTERNAL_SCRIPTS_AVAILABLE = False
    print(f"Warning: Could not import external macro scripts: {e}")

try:
    import win32gui
    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False

def generate_ao_variants(name):
    ambiguous_positions = [i for i, c in enumerate(name.lower()) if c in ('a', 'o')]
    variants = []
    options = [('a', 'o')] * len(ambiguous_positions)
    for combo in product(*options):
        name_list = list(name.lower())
        for pos, char in zip(ambiguous_positions, combo):
            name_list[pos] = char
        variant = ''.join(name_list)
        variants.append(variant.title())
    return variants

def correct_name(raw_name, known_names, max_distance=2):
    raw_name = raw_name.title()

    for variant in generate_ao_variants(raw_name):
        if variant in known_names:
            return variant

    best_match = None
    best_distance = max_distance + 1
    for name in known_names:
        dist = levenshtein(raw_name.lower(), name.lower())
        if dist < best_distance:
            best_distance = dist
            best_match = name

    return best_match if best_distance <= max_distance else raw_name

def levenshtein(s1, s2):
    if len(s1) < len(s2):
        return levenshtein(s2, s1)

    if len(s2) == 0:
        return len(s1)

    previous_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]

class MouseAutomation:
    def __init__(self):
        self.toggle = False
        self.running = False
        self.thread = None
        
        # Set config file path (use current directory for both dev and exe)
        self.config_file = os.path.join(os.getcwd(), "fishscopeconfig.json")
        
        self.first_loop = True
        self.cycle_count = 0
        self.start_time = None

        # Mouse delay settings
        self.mouse_delay_enabled = False
        self.mouse_delay_ms = 100  # Default 100ms additional delay

        # Failsafe settings
        self.failsafe_enabled = True  # Default enabled
        self.failsafe_timeout = 20  # 20 seconds timeout (minimum enforced)

        # Bar game settings
        self.bar_game_tolerance = 5  # Default tolerance for bar game

        # Auto-sell settings
        self.auto_sell_enabled = True  # Default enabled

        # Fish count tracking for auto-sell cycles
        self.fish_count_until_auto_sell = 10  # Default to 10 fish
        self.current_fish_count = 0  # Current count of fish caught in this cycle

        # Auto reconnect settings
        self.auto_reconnect_enabled = False  # Default disabled
        self.auto_reconnect_time = 60  # Default 60 minutes
        self.auto_reconnect_timer_start = None  # Track when macro started
        self.roblox_private_server_link = ""  # Private server deeplink
        self.auto_reconnect_in_progress = False  # Flag to disable other functions during reconnect
        self.roblox_window_mode = "windowed"  # Default to windowed mode ("windowed" or "fullscreen")

        # Macro sequence state tracking
        self.automation_phase = "initialization"  # Track current phase of macro
        self.in_sell_cycle = False  # Track if we're in the selling cycle
        self.external_script_running = False  # Track if external script is running

        # First launch tracking
        self.first_launch_warning_shown = False

        # Pathing settings
        self.disable_all_pathing = False  # For users without VIP gamepass

        # Get screen dimensions using multiple methods for better compatibility
        self.screen_width, self.screen_height = self.get_screen_dimensions()
        print(f"Detected screen dimensions: {self.screen_width}x{self.screen_height}")

        # Auto-detect resolution and set appropriate coordinates
        self.current_resolution = self.detect_resolution()
        self.coordinates = self.get_coordinates_for_resolution(self.current_resolution)

        # Initialize OCR and webhook settings
        self.webhook_url = ""
        self.ignore_common_fish = False
        self.ignore_uncommon_fish = False
        self.ignore_rare_fish = False
        self.ignore_trash = False
        self.fish_data = {}

        # Enhanced webhook notification settings
        self.webhook_roblox_detected = True
        self.webhook_roblox_reconnected = True
        self.webhook_macro_started = True
        self.webhook_macro_stopped = True
        self.webhook_auto_sell_started = True
        self.webhook_back_to_fishing = True
        self.webhook_failsafe_triggered = True
        self.webhook_error_notifications = True
        self.webhook_phase_changes = False  # Disabled by default to avoid spam
        self.webhook_cycle_completion = True

        try:
            import numpy as np
            self.np = np
            self.numpy_available = True
            print("NumPy loaded for ultra-fast reeling")
        except:
            self.numpy_available = False
            print("NumPy not available - using fallback method")

        self.load_calibration()
        self.load_fish_data()

        # Initialize auto sell manager
        self.auto_sell_manager = AutoSellManager(
            coordinates=self.coordinates,
            apply_mouse_delay_callback=self.apply_mouse_delay
        )

    def run_with_timeout(self, func, timeout_seconds=5, default_result=None, *args, **kwargs):
        """
        Run a function with a timeout. If the function doesn't complete within the timeout,
        return the default result and continue execution.
        """
        try:
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(func, *args, **kwargs)
                try:
                    result = future.result(timeout=timeout_seconds)
                    return result
                except concurrent.futures.TimeoutError:
                    print(f"Function {func.__name__} timed out after {timeout_seconds} seconds, skipping...")
                    return default_result
        except Exception as e:
            print(f"Error running function {func.__name__} with timeout: {e}")
            return default_result

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
            # Fallback using autoit to get screen resolution (if available)
            # Since autoit doesn't have direct screen dimension function, 
            # we'll rely only on Windows API
            pass
        except:
            pass
        
        # Final fallback to common resolution
        return (1920, 1080)

    def detect_resolution(self):
        """Detect current resolution and return appropriate config name - users should manually select scale"""
        width, height = self.screen_width, self.screen_height

        # Simple resolution detection without scale assumptions
        # Users will manually select their preferred scale from the dropdown
        if width == 1024 and height == 768:
            return "1024x768_100"
        elif width == 1920 and height == 1080:
            return "1920x1080_100"  # Default to 100% scale, user can change
        elif width == 2560 and height == 1440:
            return "2560x1440_100"  # Default to 100% scale, user can change
        elif width == 1366 and height == 768:
            return "1366x768"
        elif width == 3840 and height == 2160:
            return "3840x2160_100"  # Default to 100% scale, user can change
        else:
            return "1920x1080_100"  # Default fallback

    def get_coordinates_for_resolution(self, resolution):
        """Get coordinates based on resolution using original defaults"""
        if resolution == "1024x768_100":
            return {
                'fish_button': (424, 559),
                'white_diamond': (674, 561),
                'reel_bar': (360, 504, 665, 522),
                'completed_border': (663, 560),
                'close_button': (640, 206),
                'fish_caught_desc': (300, 350, 600, 450),  # Estimated based on pattern
                'first_item': (442, 276),
                'sell_button': (316, 542),
                'confirm_button': (443, 407),
                'mouse_idle_position': (529, 162),
                'shaded_area': (505, 506),
                'sell_fish_shop': (400, 300),  # Placeholder coordinates
                'collection_button': (450, 350),  # Placeholder coordinates
                'exit_collections': (500, 400),  # Placeholder coordinates
                'exit_fish_shop': (550, 450)  # Placeholder coordinates
            }
        elif resolution == "1920x1080_100":
            return {
                'fish_button': (851, 802),
                'white_diamond': (1176, 805),
                'reel_bar': (757, 728, 1163, 750),
                'completed_border': (1133, 744),
                'close_button': (1108, 337),
                'fish_caught_desc': (700, 540, 1035, 685),
                'first_item': (830, 409),
                'sell_button': (588, 775),
                'confirm_button': (797, 613),
                'mouse_idle_position': (999, 190),
                'shaded_area': (951, 731),
                'sell_fish_shop': (900, 600),  # Placeholder coordinates
                'collection_button': (950, 650),  # Placeholder coordinates
                'exit_collections': (1000, 700),  # Placeholder coordinates
                'exit_fish_shop': (1050, 750)  # Placeholder coordinates
            }
        elif resolution == "1920x1080_125":
            return {
                'fish_button': (833, 788),
                'white_diamond': (1176, 805),
                'reel_bar': (733, 707, 1187, 732),
                'completed_border': (1157, 772),
                'close_button': (1127, 307),
                'fish_caught_desc': (700, 520, 1035, 665),  # Estimated based on pattern
                'first_item': (823, 403),
                'sell_button': (587, 767),
                'confirm_button': (833, 591),
                'mouse_idle_position': (996, 203),
                'shaded_area': (951, 731),
                'sell_fish_shop': (880, 590),  # Placeholder coordinates
                'collection_button': (930, 640),  # Placeholder coordinates
                'exit_collections': (980, 690),  # Placeholder coordinates
                'exit_fish_shop': (1030, 740)  # Placeholder coordinates
            }
        elif resolution == "1920x1080_150":
            return {
                'fish_button': (819, 777),
                'white_diamond': (1225, 780),
                'reel_bar': (709, 684, 1210, 714),
                'completed_border': (1180, 796),
                'close_button': (1147, 277),
                'fish_caught_desc': (700, 500, 1035, 645),  # Estimated based on pattern
                'first_item': (820, 402),
                'sell_button': (589, 760),
                'confirm_button': (801, 603),
                'mouse_idle_position': (970, 220),
                'shaded_area': (945, 691),
                'sell_fish_shop': (860, 580),  # Placeholder coordinates
                'collection_button': (910, 630),  # Placeholder coordinates
                'exit_collections': (960, 680),  # Placeholder coordinates
                'exit_fish_shop': (1010, 730)  # Placeholder coordinates
            }
        elif resolution == "2560x1440_100":
            return {
                'fish_button': (1149, 1089),
                'white_diamond': (1536, 1093),
                'reel_bar': (1042, 1000, 1515, 1026),
                'completed_border': (1479, 959),
                'close_button': (1455, 491),
                'fish_caught_desc': (933, 720, 1378, 913),
                'first_item': (1101, 546),
                'sell_button': (779, 1054),
                'confirm_button': (1054, 827),
                'mouse_idle_position': (1281, 1264),
                'shaded_area': (1271, 1008),
                'sell_fish_shop': (1200, 800),  # Placeholder coordinates
                'collection_button': (1250, 850),  # Placeholder coordinates
                'exit_collections': (1300, 900),  # Placeholder coordinates
                'exit_fish_shop': (1350, 950)  # Placeholder coordinates
            }
        elif resolution == "3840x2160_100":
            return {
                'fish_button': (1751, 1648),
                'white_diamond': (2253, 1652),
                'reel_bar': (1607, 1535, 2233, 1568),
                'completed_border': (2174, 1384),
                'close_button': (2136, 789),
                'fish_caught_desc': (1400, 1080, 2070, 1370),  # Estimated based on pattern
                'first_item': (1650, 819),
                'sell_button': (1168, 1588),
                'confirm_button': (1595, 1238),
                'mouse_idle_position': (1952, 452),
                'shaded_area': (1904, 1540),
                'sell_fish_shop': (1800, 1200),  # Placeholder coordinates
                'collection_button': (1850, 1250),  # Placeholder coordinates
                'exit_collections': (1900, 1300),  # Placeholder coordinates
                'exit_fish_shop': (1950, 1350)  # Placeholder coordinates
            }
        elif resolution == "3840x2160_125":
            return {
                'fish_button': (1727, 1633),
                'white_diamond': (2277, 1640),
                'reel_bar': (1582, 1515, 2257, 1552),
                'completed_border': (2197, 1412),
                'close_button': (2156, 758),
                'fish_caught_desc': (1400, 1060, 2070, 1350),  # Estimated based on pattern
                'first_item': (1667, 816),
                'sell_button': (1172, 1575),
                'confirm_button': (1595, 1235),
                'mouse_idle_position': (1990, 473),
                'shaded_area': (1898, 1518),
                'sell_fish_shop': (1780, 1180),  # Placeholder coordinates
                'collection_button': (1830, 1230),  # Placeholder coordinates
                'exit_collections': (1880, 1280),  # Placeholder coordinates
                'exit_fish_shop': (1930, 1330)  # Placeholder coordinates
            }
        elif resolution == "3840x2160_150":
            return {
                'fish_button': (1713, 1621),
                'white_diamond': (2302, 1627),
                'reel_bar': (1560, 1492, 2278, 1534),
                'completed_border': (2220, 1435),
                'close_button': (2176, 727),
                'fish_caught_desc': (1400, 1040, 2070, 1330),  # Estimated based on pattern
                'first_item': (1654, 817),
                'sell_button': (1180, 1567),
                'confirm_button': (1600, 1204),
                'mouse_idle_position': (1975, 469),
                'shaded_area': (1891, 1498),
                'sell_fish_shop': (1760, 1160),  # Placeholder coordinates
                'collection_button': (1810, 1210),  # Placeholder coordinates
                'exit_collections': (1860, 1260),  # Placeholder coordinates
                'exit_fish_shop': (1910, 1310)  # Placeholder coordinates
            }
        elif resolution == "3840x2160_200":
            return {
                'fish_button': (1704, 1596),
                'white_diamond': (2352, 1604),
                'reel_bar': (1514, 1450, 2328, 1498),
                'completed_border': (2268, 1488),
                'close_button': (2216, 670),
                'fish_caught_desc': (1400, 1020, 2070, 1310),  # Estimated based on pattern
                'first_item': (1658, 818),
                'sell_button': (1178, 1546),
                'confirm_button': (1600, 1224),
                'mouse_idle_position': (1938, 464),
                'shaded_area': (1898, 1460),
                'sell_fish_shop': (1740, 1140),  # Placeholder coordinates
                'collection_button': (1790, 1190),  # Placeholder coordinates
                'exit_collections': (1840, 1240),  # Placeholder coordinates
                'exit_fish_shop': (1890, 1290)  # Placeholder coordinates
            }
        elif resolution == "1080p":
            # Legacy support for old 1080p naming
            return {
                'fish_button': (852, 837),
                'white_diamond': (1176, 837),
                'reel_bar': (757, 762, 1162, 781),
                'completed_border': (1139, 763),
                'close_button': (1113, 344),
                'fish_caught_desc': (700, 540, 1035, 685),
                'first_item': (834, 409),
                'sell_button': (590, 805),
                'confirm_button': (807, 629),
                'mouse_idle_position': (1365, 805),
                'shaded_area': (946, 765),
                'sell_fish_shop': (900, 630),  # Placeholder coordinates
                'collection_button': (950, 680),  # Placeholder coordinates
                'exit_collections': (1000, 730),  # Placeholder coordinates
                'exit_fish_shop': (1050, 780)  # Placeholder coordinates
            }
        elif resolution == "1440p":
            # Legacy support for 1440p naming
            return {
                'fish_button': (1149, 1089),
                'white_diamond': (1536, 1093),
                'reel_bar': (1042, 1000, 1515, 1026),
                'completed_border': (1479, 959),
                'close_button': (1455, 491),
                'fish_caught_desc': (933, 720, 1378, 913),
                'first_item': (1101, 546),
                'sell_button': (779, 1054),
                'confirm_button': (1054, 827),
                'mouse_idle_position': (1281, 1264),
                'shaded_area': (1271, 1008),
                'sell_fish_shop': (1200, 800),  # Placeholder coordinates
                'collection_button': (1250, 850),  # Placeholder coordinates
                'exit_collections': (1300, 900),  # Placeholder coordinates
                'exit_fish_shop': (1350, 950)  # Placeholder coordinates
            }
        elif resolution == "1366x768":
            # Legacy support for 1366x768 naming
            return {
                'fish_button': (594, 588),
                'white_diamond': (866, 592),
                'reel_bar': (513, 529, 855, 545),
                'completed_border': (839, 577),
                'close_button': (817, 211),
                'fish_caught_desc': (497, 384, 735, 486),
                'first_item': (591, 287),
                'sell_button': (420, 570),
                'confirm_button': (567, 443),
                'mouse_idle_position': (1115, 381),
                'shaded_area': (664, 531),
                'sell_fish_shop': (650, 430),  # Placeholder coordinates
                'collection_button': (700, 480),  # Placeholder coordinates
                'exit_collections': (750, 530),  # Placeholder coordinates
                'exit_fish_shop': (800, 580)  # Placeholder coordinates
            }
        else:
            # Default to 1920x1080 100% scale
            return self.get_coordinates_for_resolution("1920x1080_100")



    def save_calibration(self):
        try:
            config_data = {
                'coordinates': self.coordinates,
                'current_resolution': self.current_resolution,
                'webhook_url': self.webhook_url,
                'ignore_common': self.ignore_common_fish,
                'ignore_uncommon': self.ignore_uncommon_fish,
                'ignore_rare': self.ignore_rare_fish,
                'ignore_trash': self.ignore_trash,
                'mouse_delay_enabled': self.mouse_delay_enabled,
                'mouse_delay_ms': self.mouse_delay_ms,
                'failsafe_enabled': self.failsafe_enabled,
                'failsafe_timeout': self.failsafe_timeout,
                'bar_game_tolerance': self.bar_game_tolerance,
                'auto_sell_enabled': self.auto_sell_enabled,
                'fish_count_until_auto_sell': self.fish_count_until_auto_sell,
                'auto_reconnect_enabled': self.auto_reconnect_enabled,
                'auto_reconnect_time': self.auto_reconnect_time,
                'roblox_private_server_link': self.roblox_private_server_link,
                'roblox_window_mode': self.roblox_window_mode,
                'first_launch_warning_shown': self.first_launch_warning_shown,
                'disable_all_pathing': self.disable_all_pathing,
                'webhook_roblox_detected': self.webhook_roblox_detected,
                'webhook_roblox_reconnected': self.webhook_roblox_reconnected,
                'webhook_macro_started': self.webhook_macro_started,
                'webhook_macro_stopped': self.webhook_macro_stopped,
                'webhook_auto_sell_started': self.webhook_auto_sell_started,
                'webhook_back_to_fishing': self.webhook_back_to_fishing,
                'webhook_failsafe_triggered': self.webhook_failsafe_triggered,
                'webhook_error_notifications': self.webhook_error_notifications,
                'webhook_phase_changes': self.webhook_phase_changes,
                'webhook_cycle_completion': self.webhook_cycle_completion,
                'config_version': '2.1'
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
                            if key in ['reel_bar', 'fish_caught_desc'] and len(coord) == 4:
                                self.coordinates[key] = coord
                            elif len(coord) == 2:
                                self.coordinates[key] = coord

                    if 'current_resolution' in saved_data:
                        self.current_resolution = saved_data['current_resolution']

                    # Load webhook settings
                    if 'webhook_url' in saved_data:
                        self.webhook_url = saved_data['webhook_url']
                    if 'ignore_common' in saved_data:
                        self.ignore_common_fish = bool(saved_data['ignore_common'])
                    if 'ignore_uncommon' in saved_data:
                        self.ignore_uncommon_fish = bool(saved_data['ignore_uncommon'])
                    if 'ignore_rare' in saved_data:
                        self.ignore_rare_fish = bool(saved_data['ignore_rare'])
                    if 'ignore_trash' in saved_data:
                        self.ignore_trash = bool(saved_data['ignore_trash'])

                    # Load mouse delay settings
                    if 'mouse_delay_enabled' in saved_data:
                        self.mouse_delay_enabled = bool(saved_data['mouse_delay_enabled'])
                    if 'mouse_delay_ms' in saved_data:
                        self.mouse_delay_ms = int(saved_data['mouse_delay_ms'])

                    # Load failsafe settings
                    if 'failsafe_enabled' in saved_data:
                        self.failsafe_enabled = bool(saved_data['failsafe_enabled'])
                    if 'failsafe_timeout' in saved_data:
                        timeout = int(saved_data['failsafe_timeout'])
                        # Enforce minimum of 20 seconds
                        self.failsafe_timeout = max(20, timeout)

                    # Load enhanced bar game settings
                    if 'bar_game_tolerance' in saved_data:
                        self.bar_game_tolerance = int(saved_data['bar_game_tolerance'])

                    # Load auto-sell settings
                    if 'auto_sell_enabled' in saved_data:
                        self.auto_sell_enabled = bool(saved_data['auto_sell_enabled'])
                        if hasattr(self, 'auto_sell_manager'):
                            self.auto_sell_manager.set_auto_sell_enabled(self.auto_sell_enabled)

                    # Load fish count until auto sell setting
                    if 'fish_count_until_auto_sell' in saved_data:
                        self.fish_count_until_auto_sell = int(saved_data['fish_count_until_auto_sell'])

                    # Load first launch warning flag
                    if 'first_launch_warning_shown' in saved_data:
                        self.first_launch_warning_shown = bool(saved_data['first_launch_warning_shown'])

                    # Load auto reconnect settings
                    if 'auto_reconnect_enabled' in saved_data:
                        self.auto_reconnect_enabled = bool(saved_data['auto_reconnect_enabled'])
                    if 'auto_reconnect_time' in saved_data:
                        self.auto_reconnect_time = int(saved_data['auto_reconnect_time'])
                    if 'roblox_private_server_link' in saved_data:
                        self.roblox_private_server_link = str(saved_data['roblox_private_server_link'])
                    if 'roblox_window_mode' in saved_data:
                        self.roblox_window_mode = str(saved_data['roblox_window_mode'])
                        
                    # Load pathing settings
                    if 'disable_all_pathing' in saved_data:
                        self.disable_all_pathing = bool(saved_data['disable_all_pathing'])
                        
                    # Load enhanced webhook notification settings
                    if 'webhook_roblox_detected' in saved_data:
                        self.webhook_roblox_detected = bool(saved_data['webhook_roblox_detected'])
                    if 'webhook_roblox_reconnected' in saved_data:
                        self.webhook_roblox_reconnected = bool(saved_data['webhook_roblox_reconnected'])
                    if 'webhook_macro_started' in saved_data:
                        self.webhook_macro_started = bool(saved_data['webhook_macro_started'])
                    elif 'webhook_automation_started' in saved_data:  # Backward compatibility
                        self.webhook_macro_started = bool(saved_data['webhook_automation_started'])
                    if 'webhook_macro_stopped' in saved_data:
                        self.webhook_macro_stopped = bool(saved_data['webhook_macro_stopped'])
                    elif 'webhook_automation_stopped' in saved_data:  # Backward compatibility
                        self.webhook_macro_stopped = bool(saved_data['webhook_automation_stopped'])
                    if 'webhook_auto_sell_started' in saved_data:
                        self.webhook_auto_sell_started = bool(saved_data['webhook_auto_sell_started'])
                    if 'webhook_back_to_fishing' in saved_data:
                        self.webhook_back_to_fishing = bool(saved_data['webhook_back_to_fishing'])
                    if 'webhook_failsafe_triggered' in saved_data:
                        self.webhook_failsafe_triggered = bool(saved_data['webhook_failsafe_triggered'])
                    if 'webhook_error_notifications' in saved_data:
                        self.webhook_error_notifications = bool(saved_data['webhook_error_notifications'])
                    if 'webhook_phase_changes' in saved_data:
                        self.webhook_phase_changes = bool(saved_data['webhook_phase_changes'])
                    if 'webhook_cycle_completion' in saved_data:
                        self.webhook_cycle_completion = bool(saved_data['webhook_cycle_completion'])
                else:
                    # Legacy format support
                    for key, coord in saved_data.items():
                        if key in self.coordinates:
                            if key in ['reel_bar', 'fish_caught_desc'] and len(coord) == 4:
                                self.coordinates[key] = coord
                            elif len(coord) == 2:
                                self.coordinates[key] = coord

        except Exception:
            pass



    def get_mouse_position(self):
        return autoit.mouse_get_pos()

    def get_pixel_color(self, x, y):
        screenshot = ImageGrab.grab(bbox=(x, y, x+1, y+1))
        return screenshot.getpixel((0, 0))

    def is_white_pixel(self, color, tolerance=10):
        r, g, b = color[:3]
        return all(c >= (255 - tolerance) for c in [r, g, b])

    def pixel_search_white(self, x, y, tolerance=10):
        try:
            color = self.get_pixel_color(x, y)
            return color == (255, 255, 255) or self.is_white_pixel(color, tolerance)
        except:
            return False

    def pixel_search_color(self, x1, y1, x2, y2, target_color, tolerance=5):
        if self.numpy_available:
            try:
                screenshot = ImageGrab.grab(bbox=(x1, y1, x2, y2))
                img_array = self.np.array(screenshot)

                target_r, target_g, target_b = target_color[:3]

                r_diff = self.np.abs(img_array[:, :, 0].astype(self.np.int16) - target_r) <= tolerance
                g_diff = self.np.abs(img_array[:, :, 1].astype(self.np.int16) - target_g) <= tolerance
                b_diff = self.np.abs(img_array[:, :, 2].astype(self.np.int16) - target_b) <= tolerance

                matches = r_diff & g_diff & b_diff

                match_coords = self.np.where(matches)
                if len(match_coords[0]) > 0:
                    return (x1 + match_coords[1][0], y1 + match_coords[0][0])

                return None
            except:
                pass

        try:
            screenshot = ImageGrab.grab(bbox=(x1, y1, x2, y2))
            width, height = screenshot.size

            sample_points = [
                (width//4, height//2),
                (width//2, height//2),
                (3*width//4, height//2),
                (width//2, height//4),
                (width//2, 3*height//4),
            ]

            for x, y in sample_points:
                if 0 <= x < width and 0 <= y < height:
                    pixel = screenshot.getpixel((x, y))
                    if self.color_match(pixel, target_color, tolerance):
                        return (x1 + x, y1 + y)
            return None
        except:
            return None

    def color_match(self, color1, color2, tolerance):
        return all(abs(c1 - c2) <= tolerance for c1, c2 in zip(color1, color2))

    def load_fish_data(self):
        """Load fish data from JSON file with fallback to bundled version"""
        # First try to load from bundled resource
        try:
            fish_data_path = resource_path('fish-data.json')
            if os.path.exists(fish_data_path):
                with open(fish_data_path, 'r') as f:
                    self.fish_data = json.load(f)
                print(f"Loaded {len(self.fish_data)} fish entries from bundled file")
                return
        except Exception as e:
            print(f"Failed to load bundled fish data: {str(e)}")
        
        # Fallback to online version
        try:
            response = requests.get(
                "https://raw.githubusercontent.com/cresqnt-sys/FishScope-macro/main/fish-data.json"
            )
            response.raise_for_status()
            self.fish_data = response.json()
            print(f"Loaded {len(self.fish_data)} fish entries from online source")
        except Exception as e:
            print(f"Failed to load fish data from online source: {str(e)}")
            self.fish_data = {}

    def extract_fish_name(self):
        if 'fish_caught_desc' not in self.coordinates:
            print("Fish caught description coordinates not set")
            return "Unknown Fish", None

        try:
            desc_x1, desc_y1, desc_x2, desc_y2 = self.coordinates['fish_caught_desc']
            screenshot = ImageGrab.grab(bbox=(desc_x1, desc_y1, desc_x2, desc_y2))

            try:
                screenshot.save("debug_ocr_capture.png")
                print("Saved debug OCR screenshot as 'debug_ocr_capture.png'")
            except Exception as e:
                print("Failed to save debug OCR screenshot:", e)

            fish_description = self.ocr_extract_tesseract(screenshot)

            if not fish_description.strip():
                print("OCR returned empty text.")
                return "Unknown Fish", None

            print(f"Raw OCR text: {fish_description}")

            fish_description = self.clean_ocr_text(fish_description)
            print(f"Cleaned OCR text: {fish_description}")

            # Search for fish name using fuzzy matching
            fish_name, mutation = self.search_for_fish_name(fish_description)

            if fish_name != "Unknown Fish":
                return fish_name, mutation

            print("No match found, returning Unknown Fish")
            return "Unknown Fish", None
            
        except Exception as e:
            print(f"Error in extract_fish_name: {e}")
            return "Unknown Fish", None

    def search_for_fish_name(self, fish_description):
        mutations = ["Ruffled", "Crusted", "Slick", "Rough", "Charred", "Shimmering", "Tainted", "Hollow", "Lucid", "Fragmented"]
        mutation_found = None

        for mutation in mutations:
            if mutation.lower() in fish_description.lower():
                mutation_found = mutation
                fish_description = fish_description.lower().replace(mutation.lower(), '').strip()
                print(f"Mutation found: {mutation_found}")
                break

        best_match = process.extractOne(fish_description, self.fish_data.keys())
        print(f"Fuzzy matching '{fish_description}' against fish data: Best match is '{best_match[0]}' with confidence {best_match[1]}")

        if best_match and best_match[1] >= 60:
            return best_match[0], mutation_found
        else:
            return "Unknown Fish", mutation_found

    def clean_ocr_text(self, text):
        """Clean OCR text by replacing common misread characters"""
        text = text.lower()
        replacements = {
            '0': 'o',
            '1': 'l',
            '2': 'z',
            '3': 'e',
            '4': 'a',
            '5': 's',
            '6': 'g',
            '7': 't',
            '8': 'b',
            '9': 'q',
        }
        for wrong, right in replacements.items():
            text = text.replace(wrong, right)
        return text
    
    def ocr_extract_tesseract(self, image):
        try:
            result = pytesseract.image_to_string(image)
            print(f"TesseractOCR raw results: {result}")
            return result
        except pytesseract.TesseractNotFoundError:
            print("Tesseract OCR not found. Attempting to reconfigure...")
            # Try to setup Tesseract again
            if setup_tesseract():
                try:
                    result = pytesseract.image_to_string(image)
                    print(f"TesseractOCR raw results (after reconfiguration): {result}")
                    return result
                except Exception as e:
                    print(f"OCR still failed after reconfiguration: {e}")
            else:
                print("Failed to find or configure Tesseract OCR.")
                print("Please install Tesseract from: https://github.com/UB-Mannheim/tesseract/wiki")
                print("For now, returning 'Unknown Fish' as fallback.")
            return "Unknown Fish"
        except Exception as e:
            print(f"OCR Error: {e}")
            print("Tesseract OCR failed. Please install Tesseract and ensure it's in your PATH.")
            print("For now, returning 'Unknown Fish' as fallback.")
            return "Unknown Fish"

    def extract_fish_name_with_timeout(self):
        """
        Extract fish name with a 5-second timeout to prevent hanging.
        Returns ("Unknown Fish", None) if timeout occurs.
        """
        try:
            result = self.run_with_timeout(
                self.extract_fish_name, 
                timeout_seconds=5, 
                default_result=("Unknown Fish", None)
            )
            return result
        except Exception as e:
            print(f"Error in extract_fish_name_with_timeout: {e}")
            return ("Unknown Fish", None)

    def send_webhook_message_with_timeout(self, fish_name, mutation):
        """
        Send webhook message with a 5-second timeout to prevent hanging.
        Skips webhook if timeout occurs.
        """
        try:
            self.run_with_timeout(
                self.send_webhook_message,
                5,  # timeout_seconds
                None,  # default_result
                fish_name,
                mutation
            )
        except Exception as e:
            print(f"Error in send_webhook_message_with_timeout: {e}")

    def get_rarity_color(self, rarity):
        """Get Discord embed color for fish rarity"""
        rarity_colors = {
            "Common": 0xbfbfbf,    # Light Gray
            "Uncommon": 0x4dbd5e,  # Light Green
            "Rare": 0x1f7dc4,      # Light Blue
        }
        return rarity_colors.get(rarity, 0x8B4513)  # Default brown color

    def send_webhook_message(self, fish_name, mutation):
        """Send webhook message for caught fish"""
        if not self.webhook_url:
            print("Webhook URL is not set.")
            return

        if fish_name == "Fishing Failed":
            return

        print(f"Checking fish name: '{fish_name}' against fish database with {len(self.fish_data)} entries")

        if fish_name in self.fish_data:
            rarity = self.fish_data[fish_name]["rarity"]
            color = self.get_rarity_color(rarity)
            print(f"Fish '{fish_name}' found in database with rarity: {rarity}")

            if rarity == "Trash":
                title = "You snagged some trash!"
                name = "Item"
                print(f"Fish '{fish_name}' is trash!")
            else:
                title = "Fish Caught!"
                name = "Fish"
                print(f"Fish '{fish_name}' is valid fish with rarity: {rarity}")
        else:
            rarity = "Trash"
            color = 0x8B4513
            title = "You snagged some trash!"
            name = "Item"
            print(f"Fish '{fish_name}' not found in database, marking as trash.")

        if rarity == "Common" and self.ignore_common_fish:
            print("Common fish ignored, not sending webhook.")
            return
        if rarity == "Uncommon" and self.ignore_uncommon_fish:
            print("Uncommon fish ignored, not sending webhook.")
            return
        if rarity == "Rare" and self.ignore_rare_fish:
            print("Rare fish ignored, not sending webhook.")
            return
        if rarity == "Trash" and self.ignore_trash:
            print("Trash ignored, not sending webhook.")
            return

        fields = [
            {"name": name, "value": fish_name, "inline": True},
            {"name": "Rarity", "value": rarity, "inline": True}
        ]

        if mutation:
            fields.append({"name": "Mutation", "value": mutation, "inline": True})

        embed = {
            "title": title,
            "color": color,
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "fields": fields,
            "thumbnail": {
                "url": "https://raw.githubusercontent.com/cresqnt-sys/FishScope-Macro/main/fishscope-nobg.png"
            },
            "footer": {
                "text": "FishScope Macro"
            }
        }

        data = {
            "embeds": [embed]
        }

        try:
            response = self.run_with_timeout(
                requests.post,
                5,  # timeout_seconds
                None,  # default_result
                self.webhook_url,
                json=data
            )
            if response and hasattr(response, 'status_code'):
                response.raise_for_status()
                print(f"Webhook sent successfully: {response.status_code}")
            else:
                print("Webhook timed out after 5 seconds, skipping...")
        except requests.exceptions.RequestException as e:
            print(f"Failed to send webhook: {e}")
            if hasattr(response, 'text'):
                print(f"Response content: {response.text}")
            print(f"Request data: {json.dumps(data, indent=2)}")
        except Exception as e:
            print(f"Error sending webhook: {e}")

    def send_webhook_message2(self, title, description, color=0x00ff00):
        """Send general webhook message for status updates"""
        if not self.webhook_url:
            print("Webhook URL is not set.")
            return

        embed = {
            "title": title,
            "color": color,
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "fields": [
                {"name": "Status", "value": description, "inline": False}
            ],
            "thumbnail": {
                "url": "https://raw.githubusercontent.com/cresqnt-sys/FishScope-Macro/main/fishscope-nobg.png"
            },
            "footer": {
                "text": "FishScope Macro"
            }
        }

        data = {
            "embeds": [embed]
        }

        try:
            response = self.run_with_timeout(
                requests.post,
                5,  # timeout_seconds
                None,  # default_result
                self.webhook_url,
                json=data
            )
            if response and hasattr(response, 'status_code'):
                response.raise_for_status()
                print(f"Webhook sent successfully: {response.status_code}")
            else:
                print("Webhook timed out after 5 seconds, skipping...")
        except requests.exceptions.RequestException as e:
            print(f"Failed to send webhook: {e}")
            if hasattr(response, 'text'):
                print(f"Response content: {response.text}")
            print(f"Request data: {json.dumps(data, indent=2)}")
        except Exception as e:
            print(f"Error sending webhook: {e}")

    def send_webhook_notification(self, notification_type, title, description, color=None, extra_fields=None):
        """Enhanced webhook notification system with type-based filtering"""
        if not self.webhook_url:
            return

        # Check if this notification type is enabled
        webhook_setting = getattr(self, f'webhook_{notification_type}', True)
        if not webhook_setting:
            print(f"Webhook notification '{notification_type}' is disabled, skipping...")
            return

        # Set default colors based on notification type
        if color is None:
            color_map = {
                'roblox_detected': 0x28a745,      # Green
                'roblox_reconnected': 0x17a2b8,   # Blue
                'macro_started': 0x28a745,   # Green
                'macro_stopped': 0xdc3545,   # Red
                'auto_sell_started': 0xffc107,    # Yellow
                'back_to_fishing': 0x20c997,      # Teal
                'failsafe_triggered': 0xfd7e14,   # Orange
                'error_notifications': 0xdc3545,  # Red
                'phase_changes': 0x6f42c1,        # Purple
                'cycle_completion': 0x6610f2      # Dark Purple
            }
            color = color_map.get(notification_type, 0x6c757d)  # Default gray

        # Create base embed
        embed = {
            "title": title,
            "color": color,
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "fields": [
                {"name": "Status", "value": description, "inline": False}
            ],
            "thumbnail": {
                "url": "https://raw.githubusercontent.com/cresqnt-sys/FishScope-Macro/main/fishscope-nobg.png"
            },
            "footer": {
                "text": "FishScope Macro"
            }
        }

        # Add extra fields if provided
        if extra_fields:
            embed["fields"].extend(extra_fields)

        data = {
            "embeds": [embed]
        }

        try:
            response = self.run_with_timeout(
                requests.post,
                5,  # timeout_seconds
                None,  # default_result
                self.webhook_url,
                json=data
            )
            if response and hasattr(response, 'status_code'):
                response.raise_for_status()
                print(f"Webhook notification '{notification_type}' sent successfully: {response.status_code}")
            else:
                print(f"Webhook notification '{notification_type}' timed out after 5 seconds, skipping...")
        except requests.exceptions.RequestException as e:
            print(f"Failed to send webhook notification '{notification_type}': {e}")
            if hasattr(response, 'text'):
                print(f"Response content: {response.text}")
        except Exception as e:
            print(f"Error sending webhook notification '{notification_type}': {e}")

    def send_roblox_detected_notification(self):
        """Send notification when Roblox process is detected"""
        self.send_webhook_notification(
            'roblox_detected',
            '🎮 Roblox Process Detected',
            'RobloxPlayerBeta.exe has been detected and is running'
        )

    def send_roblox_reconnected_notification(self):
        """Send notification when Roblox reconnection is complete"""
        extra_fields = []
        if self.auto_reconnect_time:
            extra_fields.append({
                "name": "Reconnect Interval", 
                "value": f"{self.auto_reconnect_time} minutes", 
                "inline": True
            })
        
        self.send_webhook_notification(
            'roblox_reconnected',
            '🔄 Roblox Reconnected',
            'Auto-reconnection successful, resuming fishing macro',
            extra_fields=extra_fields
        )

    def send_macro_started_notification(self):
        """Send notification when macro starts"""
        extra_fields = [
            {"name": "Fish Target", "value": f"{self.fish_count_until_auto_sell} fish", "inline": True}
        ]
        
        if self.auto_sell_enabled:
            extra_fields.append({"name": "Auto-Sell", "value": "Enabled", "inline": True})
        else:
            extra_fields.append({"name": "Auto-Sell", "value": "Disabled", "inline": True})
            
        if self.disable_all_pathing:
            extra_fields.append({"name": "Mode", "value": "Simple Fishing (No Pathing)", "inline": True})
        else:
            extra_fields.append({"name": "Mode", "value": "Full Macro", "inline": True})

        self.send_webhook_notification(
            'macro_started',
            '▶️ Macro Started',
            'FishScope macro has been started',
            extra_fields=extra_fields
        )

    def send_macro_stopped_notification(self):
        """Send notification when macro stops"""
        elapsed_time = ""
        if hasattr(self, 'start_time') and self.start_time:
            elapsed = time.time() - self.start_time
            hours = int(elapsed // 3600)
            minutes = int((elapsed % 3600) // 60)
            seconds = int(elapsed % 60)
            elapsed_time = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

        extra_fields = []
        if elapsed_time:
            extra_fields.append({"name": "Runtime", "value": elapsed_time, "inline": True})
        if hasattr(self, 'current_fish_count'):
            extra_fields.append({"name": "Fish Caught", "value": str(self.current_fish_count), "inline": True})

        self.send_webhook_notification(
            'macro_stopped',
            '⏹️ Macro Stopped',
            'FishScope macro has been stopped',
            extra_fields=extra_fields
        )

    # Backward compatibility methods
    def send_automation_started_notification(self):
        """Backward compatibility - redirects to send_macro_started_notification"""
        return self.send_macro_started_notification()
    
    def send_automation_stopped_notification(self):
        """Backward compatibility - redirects to send_macro_stopped_notification"""
        return self.send_macro_stopped_notification()

    def send_auto_sell_started_notification(self):
        """Send notification when auto-sell cycle starts"""
        extra_fields = [
            {"name": "Fish Count", "value": f"{self.current_fish_count}", "inline": True},
            {"name": "Selling", "value": f"{self.fish_count_until_auto_sell} fish", "inline": True}
        ]
        
        self.send_webhook_notification(
            'auto_sell_started',
            '💰 Auto-Sell Started',
            'Starting auto-sell cycle at fish shop',
            extra_fields=extra_fields
        )

    def send_back_to_fishing_notification(self):
        """Send notification when returning to fishing after auto-sell"""
        self.send_webhook_notification(
            'back_to_fishing',
            '🎣 Back to Fishing',
            'Auto-sell complete, returning to fishing location'
        )

    def send_failsafe_triggered_notification(self, reason="Soft lock detected"):
        """Send notification when failsafe is triggered"""
        extra_fields = [
            {"name": "Trigger Reason", "value": reason, "inline": True},
            {"name": "Timeout", "value": f"{self.failsafe_timeout} seconds", "inline": True}
        ]
        
        self.send_webhook_notification(
            'failsafe_triggered',
            '⚠️ Failsafe Triggered',
            'Failsafe system activated to recover from issue',
            extra_fields=extra_fields
        )

    def send_error_notification(self, error_type, error_message):
        """Send notification for errors and exceptions"""
        extra_fields = [
            {"name": "Error Type", "value": error_type, "inline": True},
            {"name": "Details", "value": error_message[:1000], "inline": False}  # Limit message length
        ]
        
        self.send_webhook_notification(
            'error_notifications',
            '❌ Error Detected',
            'An error occurred during macro execution',
            extra_fields=extra_fields
        )

    def send_phase_change_notification(self, old_phase, new_phase):
        """Send notification when macro phase changes"""
        phase_descriptions = {
            'initialization': 'Setting up macro and navigation',
            'fishing': 'Actively fishing for catches',
            'pre_sell': 'Preparing for auto-sell sequence',
            'selling': 'Selling caught fish at shop',
            'post_sell': 'Completing sell cycle'
        }
        
        extra_fields = [
            {"name": "Previous Phase", "value": phase_descriptions.get(old_phase, old_phase), "inline": True},
            {"name": "Current Phase", "value": phase_descriptions.get(new_phase, new_phase), "inline": True}
        ]
        
        self.send_webhook_notification(
            'phase_changes',
            '🔄 Phase Change',
            f'Macro phase changed from {old_phase} to {new_phase}',
            extra_fields=extra_fields
        )

    def send_cycle_completion_notification(self, cycle_type, fish_count=None):
        """Send notification when a cycle completes"""
        extra_fields = []
        if fish_count:
            extra_fields.append({"name": "Fish Processed", "value": str(fish_count), "inline": True})
        
        descriptions = {
            'fishing': 'Fishing cycle completed, target fish count reached',
            'selling': 'Auto-sell cycle completed successfully',
            'full': 'Complete macro cycle finished (fishing + selling)'
        }
        
        self.send_webhook_notification(
            'cycle_completion',
            '✅ Cycle Complete',
            descriptions.get(cycle_type, f'{cycle_type} cycle completed'),
            extra_fields=extra_fields
        )

    def setup_dpi_awareness(self):
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except:
                pass

    def get_dpi_scale_factor(self):
        try:
            hdc = ctypes.windll.user32.GetDC(0)
            dpi_x = ctypes.windll.gdi32.GetDeviceCaps(hdc, 88)
            ctypes.windll.user32.ReleaseDC(0, hdc)
            scale_factor = dpi_x / 96.0
            return scale_factor
        except Exception:
            return 1.0

    def get_effective_scale_factor(self):
        if self.manual_scale_override is not None:
            return self.manual_scale_override / 100.0
        elif self.auto_scale_enabled:
            return self.dpi_scale_factor
        else:
            return 1.0

    def update_scaled_coordinates(self):
        # For now, we'll use the coordinates as-is since the original system
        # was designed for specific resolutions. DPI scaling can be added later
        # if needed for coordinate adjustment
        pass

    def set_manual_scale_override(self, percentage):
        if percentage is None:
            self.manual_scale_override = None
        else:
            self.manual_scale_override = percentage
        self.update_scaled_coordinates()

    def set_auto_scale_enabled(self, enabled):
        self.auto_scale_enabled = enabled
        self.update_scaled_coordinates()

    def apply_mouse_delay(self):
        """Apply additional mouse delay if enabled"""
        if self.mouse_delay_enabled and self.mouse_delay_ms > 0:
            time.sleep(self.mouse_delay_ms / 1000.0)  # Convert ms to seconds

    def run_external_script(self, script_name, delay=1):
        """Run external scripts with proper error handling"""
        if not EXTERNAL_SCRIPTS_AVAILABLE:
            print(f"Warning: External scripts not available, skipping {script_name}")
            return False

        try:
            self.external_script_running = True
            print(f"Running {script_name}...")
            
            if script_name == "autoalign":
                auto_align_camera(delay=delay)
            elif script_name == "fishinglocation":
                run_fishing_location_macro(fishing_location_actions, delay=delay)
            elif script_name == "shoppath":
                run_shop_path_macro(shop_path_actions, delay=delay)
            else:
                print(f"Unknown script: {script_name}")
                return False
                
            print(f"{script_name} completed successfully")
            self.external_script_running = False
            return True
            
        except Exception as e:
            print(f"Error running {script_name}: {e}")
            self.external_script_running = False
            return False

    def click_coordinate(self, coord_name, delay=0.5):
        """Click a specific coordinate with error checking"""
        if coord_name not in self.coordinates:
            print(f"Warning: Coordinate '{coord_name}' not found")
            return False
            
        try:
            coord = self.coordinates[coord_name]
            if len(coord) >= 2:
                x, y = coord[0], coord[1]
                autoit.mouse_move(x, y, 3)
                time.sleep(0.3)
                autoit.mouse_click("left")
                self.apply_mouse_delay()
                time.sleep(delay)
                print(f"Clicked {coord_name} at ({x}, {y})")
                return True
            else:
                print(f"Warning: Invalid coordinates for '{coord_name}'")
                return False
        except Exception as e:
            print(f"Error clicking {coord_name}: {e}")
            return False

    def execute_failsafe(self):
        """Execute failsafe procedure: click X button, confirm sale, then click fish button"""
        # Skip failsafe if auto reconnect is in progress
        if self.auto_reconnect_in_progress:
            print("Skipping failsafe - auto reconnect in progress")
            return
            
        print("Failsafe activated - attempting to recover from soft lock...")

        # Send failsafe notification
        self.send_failsafe_triggered_notification("White diamond timeout - attempting recovery")

        # Click X button to close any open dialogs
        close_x, close_y = self.coordinates['close_button']
        autoit.mouse_move(close_x, close_y, 3)
        time.sleep(0.3)
        autoit.mouse_click("left")
        self.apply_mouse_delay()
        time.sleep(0.3)

        # Click confirm button to confirm any pending sale
        confirm_x, confirm_y = self.coordinates['confirm_button']
        autoit.mouse_move(confirm_x, confirm_y, 3)
        time.sleep(0.15)
        autoit.mouse_click("left")
        self.apply_mouse_delay()
        time.sleep(0.3)

        # Click fish button to resume fishing
        fish_x, fish_y = self.coordinates['fish_button']
        autoit.mouse_move(fish_x, fish_y, 3)
        time.sleep(0.15)
        autoit.mouse_click("left")
        self.apply_mouse_delay()
        time.sleep(0.15)

    def should_auto_reconnect(self):
        """Check if auto reconnect should be triggered"""
        if not self.auto_reconnect_enabled or not self.auto_reconnect_timer_start:
            return False
        
        elapsed_time = time.time() - self.auto_reconnect_timer_start
        return elapsed_time >= (self.auto_reconnect_time * 60)  # Convert minutes to seconds

    def get_auto_reconnect_time_remaining(self):
        """Get remaining time until auto reconnect in seconds"""
        if not self.auto_reconnect_enabled or not self.auto_reconnect_timer_start:
            return None
        
        elapsed_time = time.time() - self.auto_reconnect_timer_start
        total_time = self.auto_reconnect_time * 60  # Convert minutes to seconds
        remaining = total_time - elapsed_time
        return max(0, remaining)

    def interruptible_sleep(self, duration):
        """Sleep for the specified duration while checking for auto reconnect every 0.1 seconds"""
        steps = int(duration * 10)  # Check every 0.1 seconds
        for i in range(steps):
            if not self.toggle:  # Also check if macro is stopped
                return False
            if self.should_auto_reconnect():
                return "auto_reconnect"
            time.sleep(0.1)
        return True

    def perform_auto_reconnect(self):
        """Perform the auto reconnect sequence"""
        try:
            print("Auto reconnect sequence started")
            
            # Set flag to disable other macro functions
            self.auto_reconnect_in_progress = True
            
            # Send webhook notification
            self.send_webhook_notification(
                'roblox_reconnected',
                "🔄 Auto Reconnect Triggered",
                f"Reconnecting after {self.auto_reconnect_time} minutes...",
                color=0x17a2b8  # Blue color
            )
            
            # Step 1: Close Roblox instances
            self.close_roblox_instances()
            time.sleep(5)  # Give time for Roblox to close
            
            # Step 2: Launch private server if link is provided
            if self.roblox_private_server_link.strip():
                launch_success = self.launch_private_server()
                if launch_success:
                    # Step 3: Wait for Roblox to start and set window mode
                    if self.wait_for_roblox_and_set_window_mode():
                        # Send Roblox detected notification
                        self.send_roblox_detected_notification()
                        
                        # Step 4: Wait 60 seconds for Roblox to fully load (still part of auto reconnect period)
                        print("Waiting 60 seconds for Roblox to fully load...")
                        for i in range(600):  # 60 seconds in 0.1 second intervals
                            if not self.toggle:  # Check if macro was stopped
                                print("Macro stopped during 60-second wait")
                                self.auto_reconnect_in_progress = False
                                return False
                            time.sleep(0.1)
                        
                        # Step 5: Press backslash key sequence and wait for completion
                        self.press_backslash_sequence()
                        # Additional wait to ensure sequence is fully processed
                        time.sleep(2)
                    else:
                        print("Failed to detect Roblox startup, but continuing...")
                        # Still wait 60 seconds even if detection failed
                        print("Waiting 60 seconds for Roblox to fully load...")
                        for i in range(600):  # 60 seconds in 0.1 second intervals
                            if not self.toggle:  # Check if macro was stopped
                                print("Macro stopped during 60-second wait")
                                self.auto_reconnect_in_progress = False
                                return False
                            time.sleep(0.1)
                        self.press_backslash_sequence()
                        time.sleep(2)
                else:
                    print("Private server launch failed, waiting for manual join...")
                    # Still wait for Roblox detection in case of manual join
                    if self.wait_for_roblox_and_set_window_mode():
                        # Send Roblox detected notification
                        self.send_roblox_detected_notification()
                        
                        # Wait 60 seconds for Roblox to fully load
                        print("Waiting 60 seconds for Roblox to fully load...")
                        for i in range(600):  # 60 seconds in 0.1 second intervals
                            if not self.toggle:  # Check if macro was stopped
                                print("Macro stopped during 60-second wait")
                                self.auto_reconnect_in_progress = False
                                return False
                            time.sleep(0.1)
                        self.press_backslash_sequence()
                        time.sleep(2)
                    else:
                        print("No Roblox detected, skipping 60-second wait and backslash sequence")
            else:
                print("No private server link provided, waiting for manual join...")
                # Wait for Roblox detection in case of manual join
                if self.wait_for_roblox_and_set_window_mode():
                    # Send Roblox detected notification
                    self.send_roblox_detected_notification()
                    
                    # Wait 60 seconds for Roblox to fully load
                    print("Waiting 60 seconds for Roblox to fully load...")
                    for i in range(600):  # 60 seconds in 0.1 second intervals
                        if not self.toggle:  # Check if macro was stopped
                            print("Macro stopped during 60-second wait")
                            self.auto_reconnect_in_progress = False
                            return False
                        time.sleep(0.1)
                    self.press_backslash_sequence()
                    time.sleep(2)
                else:
                    print("No Roblox detected, skipping 60-second wait and backslash sequence")
            
            # Step 5: Reset timer and continue macro
            print("Backslash sequence completed, resuming macro...")
            self.auto_reconnect_timer_start = time.time()
            self.auto_reconnect_in_progress = False  # Re-enable other macro functions
            
            print("Auto reconnect sequence completed")
            
            # Send completion webhook
            self.send_roblox_reconnected_notification()
            
            return True
            
        except Exception as e:
            print(f"Error during auto reconnect: {e}")
            # Send error notification
            self.send_error_notification("Auto Reconnect Error", str(e))
            # Reset flags anyway to prevent being stuck
            self.auto_reconnect_in_progress = False
            self.auto_reconnect_timer_start = time.time()
            return False

    def close_roblox_instances(self):
        """Close all Roblox instances"""
        try:
            import subprocess
            
            # First try using taskkill for immediate termination
            try:
                # Kill RobloxPlayerBeta.exe (the main game client)
                result1 = subprocess.run(['taskkill', '/f', '/im', 'RobloxPlayerBeta.exe'], 
                                       capture_output=True, text=True, check=False)
                if result1.returncode == 0:
                    print("Successfully killed RobloxPlayerBeta.exe")
                else:
                    print("RobloxPlayerBeta.exe not found or already closed")
                
                # Kill RobloxStudioBeta.exe (just in case Studio is running)
                result2 = subprocess.run(['taskkill', '/f', '/im', 'RobloxStudioBeta.exe'], 
                                       capture_output=True, text=True, check=False)
                if result2.returncode == 0:
                    print("Successfully killed RobloxStudioBeta.exe")
                
                # Kill any Roblox browser processes
                result3 = subprocess.run(['taskkill', '/f', '/im', 'Roblox.exe'], 
                                       capture_output=True, text=True, check=False)
                if result3.returncode == 0:
                    print("Successfully killed Roblox.exe")
                    
            except Exception as e:
                print(f"Error using taskkill: {e}")
            
            # Also try using win32gui if available for more thorough cleanup
            if WIN32_AVAILABLE:
                try:
                    import win32api
                    import win32con
                    import win32gui
                    
                    def enum_windows_callback(hwnd, windows):
                        if win32gui.IsWindowVisible(hwnd):
                            window_text = win32gui.GetWindowText(hwnd)
                            if "Roblox" in window_text or "roblox" in window_text.lower():
                                windows.append((hwnd, window_text))
                        return True

                    windows = []
                    win32gui.EnumWindows(enum_windows_callback, windows)
                    
                    for hwnd, window_text in windows:
                        try:
                            win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
                            print(f"Sent close message to window: {window_text}")
                        except Exception as e:
                            print(f"Failed to close window {hwnd} ({window_text}): {e}")
                    
                    if windows:
                        print(f"Attempted to close {len(windows)} Roblox windows via win32gui")
                        
                except Exception as e:
                    print(f"Error using win32gui: {e}")
                    
            print("Roblox close sequence completed")
                    
        except Exception as e:
            print(f"Error closing Roblox instances: {e}")

    def launch_private_server(self):
        """Launch Roblox private server using roblox:// protocol"""
        try:
            if not self.roblox_private_server_link.strip():
                print("No private server link provided")
                return False
            
            import subprocess
            import urllib.parse
            import os
            
            link = self.roblox_private_server_link.strip()
            
            # Determine if this is already a roblox:// protocol URL or needs conversion
            if link.startswith("roblox://"):
                # Direct roblox:// protocol URL - use as-is
                roblox_url = link
                
            elif "roblox.com/games/" in link:
                # Convert https://www.roblox.com link to roblox:// protocol
                try:
                    # Parse the URL to extract components
                    # Extract game ID
                    game_part = link.split("games/")[1]
                    game_id = game_part.split("/")[0].split("?")[0]
                    
                    # Extract private server code if present
                    if "privateServerLinkCode=" in link:
                        private_code = link.split("privateServerLinkCode=")[1].split("&")[0]
                        roblox_url = f"roblox://placeId={game_id}&linkCode={private_code}"
                    else:
                        roblox_url = f"roblox://placeId={game_id}"
                    
                except Exception as e:
                    return False
            else:
                return False
            
            # Try multiple launch methods with the roblox:// URL
            
            # Method 1: os.system with proper escaping (most reliable for Windows)
            try:
                escaped_url = f'"{roblox_url}"'
                command = f'start "" {escaped_url}'
                result = os.system(command)
                if result == 0:
                    return True
            except Exception as e:
                pass
            
            # Method 2: PowerShell Start-Process
            try:
                powershell_cmd = f'Start-Process "{roblox_url}"'
                result = subprocess.run(['powershell', '-Command', powershell_cmd], 
                                      capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    return True
            except Exception as e:
                pass
            
            # Method 3: webbrowser module as last resort
            try:
                import webbrowser
                webbrowser.open(roblox_url)
                return True
            except Exception as e:
                pass
            
            return False
            
        except Exception as e:
            print(f"Error launching private server: {e}")
            return False

    def press_backslash_sequence(self):
        """Press backslash, enter, backslash sequence"""
        try:
            # Press backslash
            autoit.send("\\")
            time.sleep(1.2)  # Slightly longer delay to ensure input is registered
            
            # Press enter
            autoit.send("{ENTER}")
            time.sleep(1.2)  # Slightly longer delay to ensure input is registered
            
            # Press backslash again
            autoit.send("\\")
            time.sleep(1.2)  # Slightly longer delay to ensure input is registered
            
        except Exception as e:
            # Try alternative method if autoit fails
            try:
                import keyboard
                keyboard.send("\\")
                time.sleep(1.2)
                keyboard.send("enter")
                time.sleep(1.2)
                keyboard.send("\\")
                time.sleep(1.2)
            except Exception as e2:
                pass

    def is_roblox_running(self):
        """Check if RobloxPlayerBeta.exe is running"""
        try:
            import subprocess
            result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq RobloxPlayerBeta.exe'], 
                                  capture_output=True, text=True, check=False)
            return 'RobloxPlayerBeta.exe' in result.stdout
        except Exception as e:
            print(f"Error checking for Roblox process: {e}")
            return False

    def wait_for_roblox_and_set_window_mode(self):
        """Wait for RobloxPlayerBeta.exe to start and set the appropriate window mode"""
        
        # Wait for Roblox to start (check every 0.5 seconds for up to 60 seconds)
        for i in range(120):  # 60 seconds total
            if self.is_roblox_running():
                # Give Roblox a moment to fully load
                time.sleep(3)
                
                # Set window mode based on user preference
                if self.roblox_window_mode == "windowed":
                    self.set_roblox_windowed()
                else:  # fullscreen
                    self.set_roblox_fullscreen()
                
                return True
            
            time.sleep(0.5)
        
        print("⚠ Timeout waiting for RobloxPlayerBeta.exe to start")
        return False

    def set_roblox_windowed(self):
        """Set Roblox to windowed mode (maximized)"""
        try:
            if WIN32_AVAILABLE:
                import win32gui
                import win32con
                
                def enum_windows_callback(hwnd, windows):
                    if win32gui.IsWindowVisible(hwnd):
                        window_text = win32gui.GetWindowText(hwnd)
                        if "Roblox" in window_text:
                            windows.append(hwnd)
                    return True

                windows = []
                win32gui.EnumWindows(enum_windows_callback, windows)
                
                for hwnd in windows:
                    # Restore window if minimized
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                    time.sleep(0.5)
                    # Maximize the window
                    win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
                    return
        except Exception as e:
            print(f"Error setting Roblox to windowed mode: {e}")

    def set_roblox_fullscreen(self):
        """Set Roblox to fullscreen mode"""
        try:
            if WIN32_AVAILABLE:
                import win32gui
                import win32con
                
                def enum_windows_callback(hwnd, windows):
                    if win32gui.IsWindowVisible(hwnd):
                        window_text = win32gui.GetWindowText(hwnd)
                        if "Roblox" in window_text:
                            windows.append(hwnd)
                    return True

                windows = []
                win32gui.EnumWindows(enum_windows_callback, windows)
                
                for hwnd in windows:
                    # Get screen dimensions
                    screen_width = win32gui.GetSystemMetrics(win32con.SM_CXSCREEN)
                    screen_height = win32gui.GetSystemMetrics(win32con.SM_CYSCREEN)
                    
                    # Set window to fullscreen
                    win32gui.SetWindowPos(hwnd, win32con.HWND_TOP, 0, 0, 
                                        screen_width, screen_height, 
                                        win32con.SWP_SHOWWINDOW)
                    return
            else:
                # Fallback method using autoit key press (F11 for fullscreen)
                time.sleep(1)
                autoit.send("{F11}")
        except Exception as e:
            print(f"Error setting Roblox to fullscreen mode: {e}")

    def mouse_automation_loop(self):
        """Main macro loop with new fishing sequence and auto-sell cycles"""
        try:
            # Initialize macro state
            self.current_fish_count = 0
            self.automation_phase = "initialization"
            
            print("Starting new macro sequence...")
            
            while self.running and self.toggle:
                if not self.toggle:
                    break

                # Wait if auto reconnect is in progress
                if self.auto_reconnect_in_progress:
                    time.sleep(0.5)  # Check every 0.5 seconds
                    continue

                # Check for auto reconnect at the start of each cycle
                if self.should_auto_reconnect():
                    if self.perform_auto_reconnect():
                        # Reset macro state after reconnect
                        self.current_fish_count = 0
                        self.automation_phase = "initialization"
                        continue
                    else:
                        print("Auto reconnect failed, continuing with normal macro")

                try:
                    # Check if all pathing is disabled - simplified mode for users without VIP gamepass
                    if self.disable_all_pathing:
                        # Simple fishing mode - no navigation, no auto-sell, just fishing
                        print("Pathing disabled - Simple fishing mode")
                        
                        # Perform single fishing cycle
                        fish_caught = self.perform_single_fishing_cycle()
                        
                        # Check if auto reconnect was triggered during fishing
                        if fish_caught == "auto_reconnect":
                            if self.perform_auto_reconnect():
                                continue
                            else:
                                continue
                        
                        if fish_caught:
                            print("Fish caught! (Pathing disabled - no auto-sell)")
                        
                        continue  # Skip all the complex macro phases
                    
                    # Phase 1: Initial Setup (only on first run or after sell cycle)
                    if self.automation_phase == "initialization" or self.automation_phase == "post_sell":
                        old_phase = self.automation_phase
                        print("Phase: Initial Setup")
                        
                        # Send phase change notification
                        self.send_phase_change_notification(old_phase, "initialization")
                        
                        # Click Collection Button
                        if not self.click_coordinate('collection_button', 1.0):
                            print("Failed to click collection button, retrying...")
                            continue
                        
                        # Wait 1 second
                        time.sleep(1.0)
                        
                        # Click Exit Collections
                        if not self.click_coordinate('exit_collections', 1.0):
                            print("Failed to click exit collections, retrying...")
                            continue
                        
                        # Run autoalign.py
                        if not self.run_external_script("autoalign", delay=2):
                            print("Failed to run autoalign script")
                            # Continue anyway as this might not be critical
                        
                        # Wait 1 second
                        time.sleep(1.0)
                        
                        # Run fishinglocation.py
                        if not self.run_external_script("fishinglocation", delay=2):
                            print("Failed to run fishing location script")
                            # Continue anyway
                        
                        # Wait 1 second
                        time.sleep(1.0)
                        
                        # Reset fish count for new cycle
                        self.current_fish_count = 0
                        self.automation_phase = "fishing"
                        print(f"Setup complete. Starting fishing cycle (target: {self.fish_count_until_auto_sell} fish)")

                    # Phase 2: Fishing Loop
                    if self.automation_phase == "fishing":
                        # Check if we should continue fishing or start sell cycle
                        if self.auto_sell_enabled and self.current_fish_count >= self.fish_count_until_auto_sell:
                            print(f"Fish count target reached ({self.current_fish_count}/{self.fish_count_until_auto_sell})")
                            
                            # Send cycle completion notification
                            self.send_cycle_completion_notification('fishing', self.current_fish_count)
                            
                            self.automation_phase = "pre_sell"
                            continue
                        elif not self.auto_sell_enabled:
                            # If auto-sell is disabled, just keep fishing forever
                            print("Auto-sell disabled, continuing fishing...")
                        
                        # Perform single fishing cycle
                        fish_caught = self.perform_single_fishing_cycle()
                        
                        # Check if auto reconnect was triggered during fishing
                        if fish_caught == "auto_reconnect":
                            if self.perform_auto_reconnect():
                                # Reset automation state after reconnect
                                self.current_fish_count = 0
                                self.automation_phase = "initialization"
                                continue
                            else:
                                continue
                        
                        if fish_caught:
                            self.current_fish_count += 1
                            print(f"Fish caught! Count: {self.current_fish_count}/{self.fish_count_until_auto_sell}")

                    # Phase 3: Pre-Sell Setup (only if auto-sell enabled)
                    elif self.automation_phase == "pre_sell" and self.auto_sell_enabled:
                        print("Phase: Pre-Sell Setup")
                        
                        # Send auto-sell started notification
                        self.send_auto_sell_started_notification()
                        
                        # Send phase change notification
                        self.send_phase_change_notification("fishing", "pre_sell")
                        
                        # Click Collection Button
                        if not self.click_coordinate('collection_button', 1.0):
                            print("Failed to click collection button for sell phase")
                            continue
                        
                        # Wait 1 second
                        time.sleep(1.0)
                        
                        # Click Exit Collections
                        if not self.click_coordinate('exit_collections', 1.0):
                            print("Failed to click exit collections for sell phase")
                            continue
                        
                        # Run autoalign.py
                        if not self.run_external_script("autoalign", delay=2):
                            print("Failed to run autoalign script for sell phase")
                        
                        # Wait 1 second
                        time.sleep(1.0)
                        
                        # Run shoppath.py
                        if not self.run_external_script("shoppath", delay=2):
                            print("Failed to run shop path script")
                            # Continue anyway
                        
                        # Wait 4 seconds before clicking Sell Fish Shop (with auto reconnect check)
                        sleep_result = self.interruptible_sleep(4.0)
                        if sleep_result == "auto_reconnect":
                            if self.perform_auto_reconnect():
                                # Reset automation state after reconnect
                                self.current_fish_count = 0
                                self.automation_phase = "initialization"
                                continue
                            else:
                                print("Auto reconnect failed, continuing with normal macro")
                        elif sleep_result == False:
                            # Macro was stopped
                            break
                        
                        # Click Sell Fish Shop
                        if not self.click_coordinate('sell_fish_shop', 1.0):
                            print("Failed to click sell fish shop")
                            continue
                        
                        # Wait 1 second
                        time.sleep(1.0)
                        
                        self.automation_phase = "selling"

                    # Phase 4: Selling Loop
                    elif self.automation_phase == "selling":
                        print(f"Phase: Selling Loop (selling {self.fish_count_until_auto_sell} fish)")
                        
                        # Send phase change notification
                        self.send_phase_change_notification("pre_sell", "selling")
                        
                        # Perform selling loop the same number of times as fish caught
                        for i in range(self.fish_count_until_auto_sell):
                            if not self.toggle:
                                break
                            
                            print(f"Selling fish {i+1}/{self.fish_count_until_auto_sell}")
                            
                            # Perform auto sell sequence using existing auto sell manager
                            if hasattr(self, 'auto_sell_manager'):
                                self.auto_sell_manager.set_auto_sell_enabled(True)
                                self.auto_sell_manager.set_first_loop(False)
                                self.auto_sell_manager.update_coordinates(self.coordinates)
                                
                                print(f"Starting auto sell sequence for fish {i+1}")
                                # Force manual sell to bypass the should_perform_auto_sell check
                                if not self.auto_sell_manager.perform_manual_sell():
                                    print(f"Manual sell sequence failed for fish {i+1}")
                                    # Continue with next fish
                                else:
                                    print(f"Auto sell sequence completed for fish {i+1}")
                            else:
                                print("Auto sell manager not available")
                                break
                            
                            # Small delay between sells
                            time.sleep(0.5)
                        
                        # Wait 1 second after all selling is done
                        time.sleep(1.0)
                        
                        # Click Exit Fish Shop
                        if not self.click_coordinate('exit_fish_shop', 1.0):
                            print("Failed to click exit fish shop")
                        
                        # Wait 1 second
                        time.sleep(1.0)
                        
                        # Send sell cycle completion notification
                        self.send_cycle_completion_notification('selling', self.fish_count_until_auto_sell)
                        
                        # Send back to fishing notification
                        self.send_back_to_fishing_notification()
                        
                        # Reset for next cycle
                        self.automation_phase = "initialization"
                        print("Sell cycle complete, starting new fishing cycle...")

                except Exception as e:
                    print(f"Error in macro phase '{self.automation_phase}': {e}")
                    # Send error notification
                    self.send_error_notification(f"Macro Phase Error", f"Error in {self.automation_phase}: {str(e)}")
                    
                    # Reset to initialization phase on error
                    self.automation_phase = "initialization"
                    
                    # Brief pause before retrying (with auto reconnect check)
                    sleep_result = self.interruptible_sleep(2.0)
                    if sleep_result == "auto_reconnect":
                        if self.perform_auto_reconnect():
                            # Reset automation state after reconnect
                            self.current_fish_count = 0
                            self.automation_phase = "initialization"
                            continue
                        else:
                            print("Auto reconnect failed, continuing with normal macro")
                    elif sleep_result == False:
                        # Macro was stopped
                        break
                    continue

        except Exception as e:
            print(f"Critical error in macro loop: {e}")
            # Send critical error notification
            self.send_error_notification("Critical Macro Error", str(e))
            print("Macro loop terminated due to error")
        finally:
            print("Macro loop ended")

    def perform_single_fishing_cycle(self):
        """Perform a single fishing cycle and return True if fish was caught"""
        try:
            # Move to fish button and click
            fish_x, fish_y = self.coordinates['fish_button']
            autoit.mouse_move(fish_x, fish_y, 3)
            time.sleep(0.15)
            autoit.mouse_click("left")
            self.apply_mouse_delay()
            time.sleep(0.15)

            bar_color = None

            # Check for white pixel with failsafe timeout
            white_diamond_start_time = time.time()

            while True:
                if not self.toggle:
                    return False

                # Check for auto reconnect during white diamond wait
                if self.should_auto_reconnect():
                    return "auto_reconnect"

                check_x, check_y = self.coordinates['white_diamond']

                if self.pixel_search_white(check_x, check_y):
                    # Move mouse to idle position
                    idle_x, idle_y = self.coordinates['mouse_idle_position']
                    autoit.mouse_move(idle_x, idle_y, 3)

                    time.sleep(0.025)
                    shaded_x, shaded_y = self.coordinates['shaded_area']
                    bar_color = self.get_pixel_color(shaded_x, shaded_y)
                    print(f"Detected bar color: {bar_color}")
                    break

                # Check for failsafe timeout
                elapsed_time = time.time() - white_diamond_start_time
                if self.failsafe_enabled and elapsed_time > self.failsafe_timeout:
                    if self.auto_reconnect_in_progress:
                        print(f"Failsafe check: Auto reconnect in progress, skipping failsafe (elapsed: {elapsed_time:.1f}s)")
                    else:
                        print(f"Failsafe triggered: No white diamond detected within {self.failsafe_timeout} seconds (elapsed: {elapsed_time:.1f}s)")
                        self.execute_failsafe()
                        white_diamond_start_time = time.time()
                        continue

                time.sleep(0.05)

            # Perform reel-in mini-game
            start_time = time.time()
            loop_count = 0

            while True:
                if not self.toggle:
                    break
                if (time.time() - start_time) > 9:
                    break

                # Check for auto reconnect during reeling
                if self.should_auto_reconnect():
                    return "auto_reconnect"

                loop_count += 1
                if loop_count % 50 == 0:
                    completed_x, completed_y = self.coordinates['completed_border']
                    if self.pixel_search_white(completed_x, completed_y, tolerance=15):
                        time.sleep(1.0)
                        break

                # Check for bar color in the reel area
                search_area = self.coordinates['reel_bar']
                found_pos = self.pixel_search_color(*search_area, bar_color, tolerance=5)
                
                # Simple logic: If color found, do nothing. If not found, click.
                if found_pos is None:
                    autoit.mouse_click("left")

            time.sleep(0.5)

            # Extract fish name using OCR and send webhook (with timeout protection)
            try:
                fish_name, mutation = self.extract_fish_name_with_timeout()
                self.send_webhook_message_with_timeout(fish_name, mutation)
            except Exception as e:
                print(f"Error in fish name extraction or webhook: {e}")
                print("Continuing with macro execution...")

            time.sleep(0.3)

            # Always attempt to close the catch screen, even if OCR failed
            try:
                close_x, close_y = self.coordinates['close_button']
                autoit.mouse_move(close_x, close_y, 3)
                time.sleep(0.7)
                autoit.mouse_click("left")
                self.apply_mouse_delay()
                time.sleep(0.15)
                print("Close button clicked successfully")
            except Exception as e:
                print(f"Error clicking close button: {e}")

            return True  # Fish was caught successfully

        except Exception as e:
            print(f"Error in single fishing cycle: {e}")
            return False

    def start_automation(self):
        if self.running:
            return
        if not self.toggle:
            self.toggle = True
            self.running = True
            self.first_loop = True
            self.cycle_count = 0
            self.start_time = time.time()
            
            # Initialize auto reconnect timer
            self.auto_reconnect_timer_start = time.time()
            
            # Reset macro state for new sequence
            self.current_fish_count = 0
            self.automation_phase = "initialization"
            self.in_sell_cycle = False
            self.external_script_running = False
            
            if WIN32_AVAILABLE:
                try:
                    def enum_windows_callback(hwnd, windows):
                        if win32gui.IsWindowVisible(hwnd):
                            window_text = win32gui.GetWindowText(hwnd)
                            if "Roblox" in window_text:
                                windows.append(hwnd)
                        return True

                    windows = []
                    win32gui.EnumWindows(enum_windows_callback, windows)
                    if windows:
                        win32gui.SetForegroundWindow(windows[0])
                except:
                    pass

            self.thread = threading.Thread(target=self.mouse_automation_loop)
            self.thread.daemon = True
            self.thread.start()

            # Send webhook message for start
            self.send_macro_started_notification()

    def stop_automation(self):
        """Stop macro with improved thread handling and error recovery"""
        if not self.running:
            return

        print("Stop macro requested...")

        # Set stop flags immediately
        self.toggle = False
        self.running = False
        self.first_loop = True
        
        # Reset macro state
        self.automation_phase = "initialization"
        self.current_fish_count = 0
        self.in_sell_cycle = False
        self.external_script_running = False

        # Send webhook notification (non-blocking)
        try:
            self.send_macro_stopped_notification()
        except Exception as e:
            print(f"Warning: Failed to send stop webhook: {e}")

        # Handle thread termination with better timeout and error handling
        if self.thread and self.thread.is_alive():
            print("Waiting for macro thread to stop...")
            try:
                # Give thread more time to stop gracefully
                self.thread.join(timeout=3)

                # Check if thread is still alive after timeout
                if self.thread.is_alive():
                    print("Warning: Macro thread did not stop gracefully within timeout")
                    print("Thread may still be running in background - this is usually safe")
                    # Note: We don't force-kill threads as it can cause crashes
                    # The daemon thread will be cleaned up when the main process exits
                else:
                    print("Automation thread stopped successfully")

            except Exception as e:
                print(f"Error during thread cleanup: {e}")

        print("Stop automation completed")

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

        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self.update_animation)
        self.animation_timer.start(50)  
        self.animation_phase = 0

        self.setup_overlay()

    def setup_overlay(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        app = QApplication.instance()
        desktop = app.primaryScreen().virtualGeometry()
        self.setGeometry(desktop)

        self.setMouseTracking(True)

        self.setCursor(Qt.CursorShape.CrossCursor)

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def update_animation(self):
        self.animation_phase = (self.animation_phase + 1) % 100
        self.update()

    def wrap_text(self, text, font_metrics, max_width):
        words = text.split()
        lines = []
        current_line = ""

        for word in words:
            test_line = current_line + (" " if current_line else "") + word
            if font_metrics.boundingRect(test_line).width() <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word

        if current_line:
            lines.append(current_line)

        return lines if lines else [text]

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        painter.fillRect(self.rect(), QColor(0, 0, 0, 30))

        panel_width = min(max(700, self.width() // 2), self.width() - 40)
        panel_height = 160  
        panel_x = (self.width() - panel_width) // 2
        panel_y = 30 

        shadow_offset = 4
        shadow_gradient = QLinearGradient(0, panel_y + shadow_offset, 0, panel_y + panel_height + shadow_offset)
        shadow_gradient.setColorAt(0, QColor(0, 0, 0, 60))
        shadow_gradient.setColorAt(1, QColor(0, 0, 0, 15))
        painter.setBrush(QBrush(shadow_gradient))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(panel_x + shadow_offset, panel_y + shadow_offset, panel_width, panel_height, 12, 12)

        gradient = QLinearGradient(0, panel_y, 0, panel_y + panel_height)
        gradient.setColorAt(0, QColor(45, 45, 45, 180))
        gradient.setColorAt(1, QColor(25, 25, 25, 180))

        painter.setBrush(QBrush(gradient))

        pulse_intensity = 0.3 + 0.2 * abs(50 - self.animation_phase) / 50.0
        border_color = QColor(int(80 + 40 * pulse_intensity), int(120 + 30 * pulse_intensity), 200)
        painter.setPen(QPen(border_color, 2))
        painter.drawRoundedRect(panel_x, panel_y, panel_width, panel_height, 12, 12)

        glow_alpha = int(80 + 40 * pulse_intensity)
        painter.setPen(QPen(QColor(100, 140, 220, glow_alpha), 1))
        painter.drawRoundedRect(panel_x + 1, panel_y + 1, panel_width - 2, panel_height - 2, 11, 11)

        painter.setPen(QColor(255, 255, 255))
        painter.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))

        text_padding = 20
        available_width = panel_width - (text_padding * 2)

        title_lines = self.wrap_text(self.message, painter.fontMetrics(), available_width)
        title_y_start = panel_y + 25

        for i, line in enumerate(title_lines):
            line_rect = painter.fontMetrics().boundingRect(line)
            title_x = panel_x + (panel_width - line_rect.width()) // 2
            title_y = title_y_start + (i * 20)
            painter.drawText(title_x, title_y, line)

        painter.setFont(QFont("Segoe UI", 11))
        instruction = "Click anywhere on the screen to set coordinate"
        inst_lines = self.wrap_text(instruction, painter.fontMetrics(), available_width)
        inst_y_start = title_y_start + (len(title_lines) * 20) + 15

        painter.setPen(QColor(200, 200, 200))
        for i, line in enumerate(inst_lines):
            line_rect = painter.fontMetrics().boundingRect(line)
            inst_x = panel_x + (panel_width - line_rect.width()) // 2
            inst_y = inst_y_start + (i * 15)
            painter.drawText(inst_x, inst_y, line)

        painter.setFont(QFont("Segoe UI", 10))
        esc_text = "Press ESC to cancel"
        esc_rect = painter.fontMetrics().boundingRect(esc_text)
        esc_x = panel_x + (panel_width - esc_rect.width()) // 2
        esc_y = inst_y_start + (len(inst_lines) * 15) + 15
        painter.setPen(QColor(180, 180, 180))
        painter.drawText(esc_x, esc_y, esc_text)

        coord_text = f"Mouse Position: ({self.mouse_pos.x()}, {self.mouse_pos.y()})"
        painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        coord_rect = painter.fontMetrics().boundingRect(coord_text)

        coord_y = panel_y + panel_height - 25

        coord_box_width = min(coord_rect.width() + 20, panel_width - 20)
        coord_box_height = 22
        coord_box_x = panel_x + (panel_width - coord_box_width) // 2
        coord_box_y = coord_y - 16

        coord_gradient = QLinearGradient(0, coord_box_y, 0, coord_box_y + coord_box_height)
        coord_gradient.setColorAt(0, QColor(60, 120, 200, 150))
        coord_gradient.setColorAt(1, QColor(40, 80, 160, 150))

        painter.setBrush(QBrush(coord_gradient))
        painter.setPen(QPen(QColor(100, 150, 255, 120), 1))
        painter.drawRoundedRect(coord_box_x, coord_box_y, coord_box_width, coord_box_height, 6, 6)

        text_x = coord_box_x + (coord_box_width - coord_rect.width()) // 2
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(text_x, coord_y, coord_text)

        if self.show_click_feedback:
            local_pos = self.mapFromGlobal(self.click_pos)
            center_x = local_pos.x()
            center_y = local_pos.y()

            # Draw modern click feedback with glow effect
            # Outer glow circle
            painter.setPen(QPen(QColor(0, 255, 100, 100), 8))
            painter.drawEllipse(center_x - 30, center_y - 30, 60, 60)

            # Main circle with gradient
            click_gradient = QLinearGradient(center_x - 25, center_y - 25, center_x + 25, center_y + 25)
            click_gradient.setColorAt(0, QColor(50, 255, 150, 200))
            click_gradient.setColorAt(1, QColor(0, 200, 100, 200))
            painter.setBrush(QBrush(click_gradient))
            painter.setPen(QPen(QColor(0, 255, 100), 3))
            painter.drawEllipse(center_x - 25, center_y - 25, 50, 50)

            # Precise crosshair with modern styling
            painter.setPen(QPen(QColor(255, 255, 255), 2))
            painter.drawLine(center_x - 15, center_y, center_x + 15, center_y)
            painter.drawLine(center_x, center_y - 15, center_x, center_y + 15)

            # Center dot for precise targeting
            painter.setBrush(QBrush(QColor(255, 50, 50)))
            painter.setPen(QPen(QColor(255, 255, 255), 1))
            painter.drawEllipse(center_x - 3, center_y - 3, 6, 6)

    def mouseMoveEvent(self, event):
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

    def closeEvent(self, event):
        """Clean up timers when closing"""
        self.animation_timer.stop()
        self.click_feedback_timer.stop()
        super().closeEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.calibration_cancelled.emit()
            self.close()

    def showEvent(self, event):
        super().showEvent(event)
        self.setFocus()
        self.activateWindow()
        self.raise_()

class AdvancedCalibrationWindow(QMainWindow):
    def __init__(self, automation, parent=None):
        super().__init__(parent)
        self.automation = automation
        self.parent_window = parent

        self.calibrating = False
        self.current_calibration = None
        self.reel_bar_step = 1
        self.reel_bar_coords = []

        self.coord_labels = {
            'fish_button': 'Fish Button - Click to start fishing',
            'white_diamond': 'White Diamond - Pixel that turns white when fish is caught',
            'shaded_area': 'Shaded Area - Pixel location to sample bar color from (should be on the reel bar)',
            'reel_bar': 'Reel Bar - The Reel progress bar',
            'completed_border': 'Completed Border - A pixel of the completed screen border',
            'close_button': 'Close Button - Close the successfully caught fish',
            'first_item': 'First Item - Click the first item',
            'confirm_button': 'Confirm Button - Confirm the sale',
            'mouse_idle_position': 'Mouse Idle Position - Where mouse will normally be. Must be in a place without UI.'
        }

        self.coord_labels_widgets = {}

        self.setup_ui()
        self.apply_clean_theme()

    def setup_ui(self):
        self.setWindowTitle("Advanced Calibrations - FishScope Macro")
        self.setFixedSize(700, 700)

        # Set application icon
        if os.path.exists("icon.ico"):
            self.setWindowIcon(QIcon("icon.ico"))

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 15, 15, 15)

        # Header
        header_layout = QVBoxLayout()
        header_layout.setSpacing(4)

        title_label = QLabel("Advanced Calibrations")
        title_font = QFont("Segoe UI", 18, QFont.Weight.Bold)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("color: #ffffff; margin: 4px 0;")
        header_layout.addWidget(title_label)

        subtitle_label = QLabel("Customize coordinate positions for your specific setup")
        subtitle_font = QFont("Segoe UI", 10)
        subtitle_label.setFont(subtitle_font)
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle_label.setStyleSheet("color: #888888; margin-bottom: 10px;")
        header_layout.addWidget(subtitle_label)

        main_layout.addLayout(header_layout)

        # Add a scroll area for calibration controls
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setSpacing(10)
        scroll_layout.setContentsMargins(0, 0, 0, 0)

        # Calibration Section
        calibration_group = QGroupBox("Coordinate Calibration")
        calibration_layout = QVBoxLayout(calibration_group)
        calibration_layout.setContentsMargins(12, 15, 12, 12)
        calibration_layout.setSpacing(6)

        calib_info = QLabel("Click 'Calibrate' for each coordinate to set up automation points")
        calib_info.setStyleSheet("color: #888888; font-size: 11px; margin-bottom: 6px;")
        calibration_layout.addWidget(calib_info)

        scroll_area_calibration = QScrollArea()
        scroll_area_calibration.setWidgetResizable(True)
        scroll_area_calibration.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area_calibration.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        scroll_widget_calibration = QWidget()
        scroll_layout_calibration = QVBoxLayout(scroll_widget_calibration)
        scroll_layout_calibration.setSpacing(3)
        scroll_layout_calibration.setContentsMargins(4, 4, 4, 4)

        # Create calibration rows for all coordinates
        for coord_name, description in self.coord_labels.items():
            self.create_calibration_row(scroll_layout_calibration, coord_name, description)

        # Set minimum size to ensure all content is scrollable
        scroll_widget_calibration.setMinimumHeight(520)

        scroll_area_calibration.setWidget(scroll_widget_calibration)
        calibration_layout.addWidget(scroll_area_calibration)
        scroll_layout.addWidget(calibration_group)

        # Close button
        close_layout = QHBoxLayout()
        close_layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                font-weight: 600;
                padding: 10px 20px;
                font-size: 13px;
                border: none;
                border-radius: 6px;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #5a6268;
            }
            QPushButton:pressed {
                background-color: #545b62;
            }
        """)
        close_layout.addWidget(close_btn)
        close_layout.addStretch()

        scroll_layout.addLayout(close_layout)

        scroll_area.setWidget(scroll_widget)
        main_layout.addWidget(scroll_area)

    def create_calibration_row(self, parent_layout, coord_name, description):
        frame = QFrame()
        frame.setFixedHeight(50)
        frame.setStyleSheet("""
            QFrame {
                background-color: #2d2d2d;
                border: 1px solid #404040;
                border-radius: 6px;
                margin: 1px;
            }
        """)

        frame_layout = QHBoxLayout(frame)
        frame_layout.setContentsMargins(12, 8, 12, 8)
        frame_layout.setSpacing(10)

        # Left side - Info
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)

        # Coordinate name
        name_label = QLabel(description.split(' - ')[0])
        name_label.setStyleSheet("color: #ffffff; font-weight: 600; font-size: 12px;")
        info_layout.addWidget(name_label)

        # Current coordinates
        coord_label = QLabel(self.get_coord_text(coord_name))
        coord_label.setStyleSheet("color: #888888; font-size: 10px; font-family: 'Consolas', monospace;")
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
        if coord_name in self.automation.coordinates:
            coord = self.automation.coordinates[coord_name]
            if coord_name in ['reel_bar', 'fish_caught_desc'] and len(coord) == 4:
                return f"({coord[0]}, {coord[1]}, {coord[2]}, {coord[3]})"
            elif len(coord) == 2:
                return f"({coord[0]}, {coord[1]})"
        return "Not set"

    def start_calibration(self, coord_name):
        if self.calibrating:
            return

        self.calibrating = True
        self.current_calibration = coord_name

        # Hide the calibration window during calibration for better focus
        self.hide()

        # Create overlay window with improved messaging
        if coord_name == 'reel_bar':
            display_name = self.coord_labels[coord_name].split(' - ')[0]
            message = f"{display_name} - Step 1: TOP-LEFT corner"
            self.reel_bar_step = 1
        elif coord_name == 'fish_caught_desc':
            display_name = self.coord_labels[coord_name].split(' - ')[0]
            message = f"Calibrating: {display_name} - Click the top-left corner of the description area"
            self.fish_caught_desc_step = 1
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
        elif self.current_calibration == 'fish_caught_desc':
            if self.fish_caught_desc_step == 1:
                # Store top-left coordinates
                self.fish_caught_desc_top_left = (x, y)
                self.fish_caught_desc_step = 2

                # Close current overlay
                self.overlay.close()

                # Show second overlay for bottom-right with improved messaging
                display_name = self.coord_labels['fish_caught_desc'].split(' - ')[0]
                message = f"Calibrating: {display_name} - Click the bottom-right corner of the description area"
                self.overlay = CalibrationOverlay(message)
                self.overlay.coordinate_selected.connect(self.on_calibration_click)
                self.overlay.calibration_cancelled.connect(self.cancel_calibration)
                self.overlay.show()
                return
            else:
                # Complete fish caught description calibration with bottom-right coordinates
                self.fish_caught_desc_bottom_right = (x, y)
                self.automation.coordinates['fish_caught_desc'] = (
                    self.fish_caught_desc_top_left[0], self.fish_caught_desc_top_left[1],
                    self.fish_caught_desc_bottom_right[0], self.fish_caught_desc_bottom_right[1]
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

        self.current_calibration = None

        # Show the calibration window again
        self.show()
        self.raise_()  # Bring window to front
        self.activateWindow()  # Make it the active window

    def cancel_calibration(self):
        self.calibrating = False
        self.current_calibration = None

        # Show the calibration window again
        self.show()
        self.raise_()  # Bring window to front
        self.activateWindow()  # Make it the active window

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

class CalibrationUI(QMainWindow):
    def __init__(self, automation):
        super().__init__()
        self.automation = automation

        self.calibrating = False
        self.current_calibration = None
        self.reel_bar_step = 1
        self.reel_bar_coords = []
        self.advanced_calibration_window = None
        
        # Flag to prevent showing Tesseract popup multiple times
        self.tesseract_popup_shown = False

        # Initialize auto updater
        self.auto_updater = AutoUpdater(self)

        # Setup timer for auto reconnect display updates
        self.ui_update_timer = QTimer()
        self.ui_update_timer.timeout.connect(self.update_auto_reconnect_display)
        self.ui_update_timer.start(1000)  # Update every second

        # Premade calibrations using original coordinates
        self.premade_calibrations = {
            "1024x768 | Windowed | 100% Scale": {
                'fish_button': (424, 559),
                'white_diamond': (674, 561),
                'reel_bar': (360, 504, 665, 522),
                'completed_border': (663, 560),
                'close_button': (640, 206),
                'fish_caught_desc': (300, 350, 600, 450),
                'first_item': (442, 276),
                'sell_button': (316, 542),
                'confirm_button': (443, 407),
                'mouse_idle_position': (529, 162),
                'shaded_area': (505, 506),
                'sell_fish_shop': (400, 300),  # Placeholder coordinates
                'collection_button': (450, 350),  # Placeholder coordinates
                'exit_collections': (500, 400),  # Placeholder coordinates
                'exit_fish_shop': (550, 450)  # Placeholder coordinates
            },
            "1920x1080 | Windowed | 100% Scale": {
                'fish_button': (851, 802),
                'white_diamond': (1176, 805),
                'reel_bar': (757, 728, 1163, 750),
                'completed_border': (1133, 744),
                'close_button': (1108, 337),
                'fish_caught_desc': (700, 540, 1035, 685),
                'first_item': (830, 409),
                'sell_button': (588, 775),
                'confirm_button': (797, 613),
                'mouse_idle_position': (999, 190),
                'shaded_area': (951, 731),
                'sell_fish_shop': (900, 600),  # Placeholder coordinates
                'collection_button': (950, 650),  # Placeholder coordinates
                'exit_collections': (1000, 700),  # Placeholder coordinates
                'exit_fish_shop': (1050, 750)  # Placeholder coordinates
            },
            "1920x1080 | Windowed | 125% Scale": {
                'fish_button': (833, 788),
                'white_diamond': (1201, 792),
                'reel_bar': (733, 707, 1187, 732),
                'completed_border': (1157, 772),
                'close_button': (1127, 307),
                'fish_caught_desc': (700, 520, 1035, 665),
                'first_item': (823, 403),
                'sell_button': (587, 767),
                'confirm_button': (833, 591),
                'mouse_idle_position': (996, 203),
                'shaded_area': (950, 712)
            },
            "1920x1080 | Windowed | 150% Scale": {
                'fish_button': (819, 777),
                'white_diamond': (1225, 780),
                'reel_bar': (709, 684, 1210, 714),
                'completed_border': (1180, 796),
                'close_button': (1147, 277),
                'fish_caught_desc': (700, 500, 1035, 645),
                'first_item': (820, 402),
                'sell_button': (589, 760),
                'confirm_button': (801, 603),
                'mouse_idle_position': (970, 220),
                'shaded_area': (945, 691)
            },
            "3840x2160 | Windowed | 100% Scale": {
                'fish_button': (1751, 1648),
                'white_diamond': (2253, 1652),
                'reel_bar': (1607, 1535, 2233, 1568),
                'completed_border': (2174, 1384),
                'close_button': (2136, 789),
                'fish_caught_desc': (1400, 1080, 2070, 1370),
                'first_item': (1650, 819),
                'sell_button': (1168, 1588),
                'confirm_button': (1595, 1238),
                'mouse_idle_position': (1952, 452),
                'shaded_area': (1904, 1540)
            },
            "3840x2160 | Windowed | 125% Scale": {
                'fish_button': (1727, 1633),
                'white_diamond': (2277, 1640),
                'reel_bar': (1582, 1515, 2257, 1552),
                'completed_border': (2197, 1412),
                'close_button': (2156, 758),
                'fish_caught_desc': (1400, 1060, 2070, 1350),
                'first_item': (1667, 816),
                'sell_button': (1172, 1575),
                'confirm_button': (1595, 1235),
                'mouse_idle_position': (1990, 473),
                'shaded_area': (1898, 1518)
            },
            "3840x2160 | Windowed | 150% Scale": {
                'fish_button': (1713, 1621),
                'white_diamond': (2302, 1627),
                'reel_bar': (1560, 1492, 2278, 1534),
                'completed_border': (2220, 1435),
                'close_button': (2176, 727),
                'fish_caught_desc': (1400, 1040, 2070, 1330),
                'first_item': (1654, 817),
                'sell_button': (1180, 1567),
                'confirm_button': (1600, 1204),
                'mouse_idle_position': (1975, 469),
                'shaded_area': (1891, 1498)
            },
            "3840x2160 | Windowed | 200% Scale": {
                'fish_button': (1704, 1596),
                'white_diamond': (2352, 1604),
                'reel_bar': (1514, 1450, 2328, 1498),
                'completed_border': (2268, 1488),
                'close_button': (2216, 670),
                'fish_caught_desc': (1400, 1020, 2070, 1310),
                'first_item': (1658, 818),
                'sell_button': (1178, 1546),
                'confirm_button': (1600, 1224),
                'mouse_idle_position': (1938, 464),
                'shaded_area': (1898, 1460)
            },
            # Legacy support for existing configurations
            "1920x1080 | Windowed | 100% Scale (Legacy)": {
                'fish_button': (851, 801),
                'white_diamond': (1177, 803),
                'reel_bar': (758, 729, 1159, 744),
                'completed_border': (1135, 745),
                'close_button': (1108, 336),
                'fish_caught_desc': (700, 540, 1035, 685),
                'first_item': (830, 407),
                'sell_button': (592, 774),
                'confirm_button': (789, 615),
                'mouse_idle_position': (975, 210),
                'shaded_area': (947, 732)
            },
            "1920x1080 | Full Screen | 100% Scale": {
                'fish_button': (852, 837),
                'white_diamond': (1176, 837),
                'reel_bar': (757, 762, 1162, 781),
                'completed_border': (1139, 763),
                'close_button': (1113, 344),
                'fish_caught_desc': (700, 540, 1035, 685),
                'first_item': (834, 409),
                'sell_button': (590, 805),
                'confirm_button': (807, 629),
                'mouse_idle_position': (1365, 805),
                'shaded_area': (946, 765)
            },
            "2560x1440 | Windowed | 100% Scale": {
                'fish_button': (1149, 1089),
                'white_diamond': (1536, 1093),
                'reel_bar': (1042, 1000, 1515, 1026),
                'completed_border': (1479, 959),
                'close_button': (1455, 491),
                'fish_caught_desc': (933, 720, 1378, 913),
                'first_item': (1101, 546),
                'sell_button': (779, 1054),
                'confirm_button': (1054, 827),
                'mouse_idle_position': (1281, 1264),
                'shaded_area': (1271, 1008)
            },
            "1366x768 | Full Screen | 100% Scale": {
                'fish_button': (594, 588),
                'white_diamond': (866, 592),
                'reel_bar': (513, 529, 855, 545),
                'completed_border': (839, 577),
                'close_button': (817, 211),
                'fish_caught_desc': (497, 384, 735, 486),
                'first_item': (591, 287),
                'sell_button': (420, 570),
                'confirm_button': (567, 443),
                'mouse_idle_position': (1115, 381),
                'shaded_area': (664, 531)
            }
        }

        self.setup_ui()
        self.apply_clean_theme()

    def on_webhook_url_changed(self, text):
        self.automation.webhook_url = text
        self.automation.save_calibration()

    def update_ignore_common(self, state):
        self.automation.ignore_common_fish = state == Qt.CheckState.Checked.value
        self.automation.save_calibration()

    def update_ignore_uncommon(self, state):
        self.automation.ignore_uncommon_fish = state == Qt.CheckState.Checked.value
        self.automation.save_calibration()

    def update_ignore_rare(self, state):
        self.automation.ignore_rare_fish = state == Qt.CheckState.Checked.value
        self.automation.save_calibration()

    def update_ignore_trash(self, state):
        self.automation.ignore_trash = state == Qt.CheckState.Checked.value
        self.automation.save_calibration()

    def update_webhook_roblox_detected(self, state):
        self.automation.webhook_roblox_detected = state == Qt.CheckState.Checked.value
        self.automation.save_calibration()

    def update_webhook_roblox_reconnected(self, state):
        self.automation.webhook_roblox_reconnected = state == Qt.CheckState.Checked.value
        self.automation.save_calibration()

    def update_webhook_macro_started(self, state):
        self.automation.webhook_macro_started = state == Qt.CheckState.Checked.value
        self.automation.save_calibration()

    def update_webhook_macro_stopped(self, state):
        self.automation.webhook_macro_stopped = state == Qt.CheckState.Checked.value
        self.automation.save_calibration()

    def update_webhook_auto_sell_started(self, state):
        self.automation.webhook_auto_sell_started = state == Qt.CheckState.Checked.value
        self.automation.save_calibration()

    def update_webhook_back_to_fishing(self, state):
        self.automation.webhook_back_to_fishing = state == Qt.CheckState.Checked.value
        self.automation.save_calibration()

    def update_webhook_failsafe_triggered(self, state):
        self.automation.webhook_failsafe_triggered = state == Qt.CheckState.Checked.value
        self.automation.save_calibration()

    def update_webhook_error_notifications(self, state):
        self.automation.webhook_error_notifications = state == Qt.CheckState.Checked.value
        self.automation.save_calibration()

    def update_webhook_phase_changes(self, state):
        self.automation.webhook_phase_changes = state == Qt.CheckState.Checked.value
        self.automation.save_calibration()

    def update_webhook_cycle_completion(self, state):
        self.automation.webhook_cycle_completion = state == Qt.CheckState.Checked.value
        self.automation.save_calibration()

    def test_webhook(self):
        """Test the webhook by sending a test message"""
        if not self.automation.webhook_url:
            msg = QMessageBox(self)
            msg.setWindowTitle("No Webhook URL")
            msg.setText("Please enter a webhook URL before testing.")
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

        try:
            # Send a test notification using the basic webhook function to bypass settings
            embed = {
                "title": "🧪 Test Webhook",
                "color": 0x17a2b8,
                "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "fields": [
                    {"name": "Status", "value": "This is a test message to verify your webhook is working correctly!", "inline": False}
                ],
                "thumbnail": {
                    "url": "https://raw.githubusercontent.com/cresqnt-sys/FishScope-Macro/main/fishscope-nobg.png"
                },
                "footer": {
                    "text": "FishScope Macro - Test Message"
                }
            }

            data = {"embeds": [embed]}
            response = requests.post(self.automation.webhook_url, json=data)
            response.raise_for_status()
            
            # Show success message
            msg = QMessageBox(self)
            msg.setWindowTitle("Test Sent")
            msg.setText("Test webhook sent successfully! Check your Discord channel.")
            msg.setIcon(QMessageBox.Icon.Information)
            msg.setStyleSheet("""
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
            msg.exec()
            
        except Exception as e:
            # Show error message
            msg = QMessageBox(self)
            msg.setWindowTitle("Test Failed")
            msg.setText(f"Failed to send test webhook:\n{str(e)}")
            msg.setIcon(QMessageBox.Icon.Critical)
            msg.setStyleSheet("""
                QMessageBox {
                    background-color: #2d2d2d;
                    color: white;
                }
                QMessageBox QPushButton {
                    background-color: #dc3545;
                    color: white;
                    border: 1px solid #c82333;
                    padding: 8px 16px;
                    border-radius: 4px;
                    min-width: 80px;
                    font-weight: bold;
                }
                QMessageBox QPushButton:hover {
                    background-color: #c82333;
                }
            """)
            msg.exec()

    def on_tab_changed(self, index):
        """Handle tab change events"""
        # Check if the webhook tab is being opened
        tab_text = self.tab_widget.tabText(index)
        if tab_text == "Webhook":
            self.check_tesseract_on_webhook_tab()

    def check_tesseract_on_webhook_tab(self):
        """Check for Tesseract when webhook tab is opened and show popup if not found"""
        # Don't show popup again if already shown in this session
        if self.tesseract_popup_shown:
            return
            
        try:
            # First check if tesseract is already available in PATH
            if shutil.which('tesseract'):
                return  # Tesseract found, no need to show popup
            
            # Check if pytesseract is configured with a custom path
            if hasattr(pytesseract.pytesseract, 'tesseract_cmd') and pytesseract.pytesseract.tesseract_cmd:
                if os.path.exists(pytesseract.pytesseract.tesseract_cmd):
                    return  # Tesseract found at configured path
            
            # Try to run setup_tesseract to see if it can find Tesseract
            if setup_tesseract():
                return  # setup_tesseract found and configured Tesseract
            
            # If we get here, Tesseract was not found - show popup
            self.show_tesseract_missing_popup()
            
        except Exception as e:
            print(f"Error checking for Tesseract: {e}")
            # Show popup anyway if there's an error
            self.show_tesseract_missing_popup()

    def show_tesseract_missing_popup(self):
        """Show popup warning about missing Tesseract"""
        # Set flag to prevent showing again
        self.tesseract_popup_shown = True
        
        msg = QMessageBox(self)
        msg.setWindowTitle("Tesseract OCR Not Found")
        msg.setText("Tesseract OCR is required for fish detection in webhooks!")
        msg.setInformativeText(
            "Tesseract OCR was not detected on your system. "
            "Without Tesseract, the macro cannot identify caught fish for webhook notifications.\n\n"
            "Please download and install Tesseract from the link below, then restart the application."
        )
        msg.setDetailedText(
            "Download link: https://github.com/UB-Mannheim/tesseract/wiki\n\n"
            "Installation instructions:\n"
            "1. Click the link above or visit the GitHub page\n"
            "2. Download the Windows installer for your system (32-bit or 64-bit)\n"
            "3. Run the installer and follow the installation wizard\n"
            "4. Restart FishScope Macro after installation\n\n"
            "The macro will automatically detect Tesseract in common installation directories:\n"
            "• C:\\Program Files\\Tesseract-OCR\\\n"
            "• C:\\Program Files (x86)\\Tesseract-OCR\\\n"
            "• User AppData directories"
        )
        msg.setIcon(QMessageBox.Icon.Warning)
        
        # Add a button to open the download link
        download_button = msg.addButton("Open Download Page", QMessageBox.ButtonRole.ActionRole)
        ok_button = msg.addButton("OK", QMessageBox.ButtonRole.AcceptRole)
        
        msg.setStyleSheet("""
            QMessageBox {
                background-color: #2d2d2d;
                color: white;
                min-width: 400px;
            }
            QMessageBox QPushButton {
                background-color: #fd7e14;
                color: white;
                border: 1px solid #e8650e;
                padding: 8px 16px;
                border-radius: 4px;
                min-width: 100px;
                font-weight: bold;
            }
            QMessageBox QPushButton:hover {
                background-color: #e8650e;
            }
            QMessageBox QLabel {
                color: white;
            }
        """)
        
        result = msg.exec()
        
        # Check which button was clicked
        if msg.clickedButton() == download_button:
            import webbrowser
            webbrowser.open("https://github.com/UB-Mannheim/tesseract/wiki")

    def enable_all_notifications(self):
        """Enable all webhook notifications"""
        self.automation.webhook_roblox_detected = True
        self.automation.webhook_roblox_reconnected = True
        self.automation.webhook_automation_started = True
        self.automation.webhook_automation_stopped = True
        self.automation.webhook_auto_sell_started = True
        self.automation.webhook_back_to_fishing = True
        self.automation.webhook_failsafe_triggered = True
        self.automation.webhook_error_notifications = True
        self.automation.webhook_phase_changes = True
        self.automation.webhook_cycle_completion = True
        
        # Update checkbox states
        self.webhook_roblox_detected_checkbox.setChecked(True)
        self.webhook_roblox_reconnected_checkbox.setChecked(True)
        self.webhook_automation_started_checkbox.setChecked(True)
        self.webhook_automation_stopped_checkbox.setChecked(True)
        self.webhook_auto_sell_started_checkbox.setChecked(True)
        self.webhook_back_to_fishing_checkbox.setChecked(True)
        self.webhook_failsafe_triggered_checkbox.setChecked(True)
        self.webhook_error_notifications_checkbox.setChecked(True)
        self.webhook_phase_changes_checkbox.setChecked(True)
        self.webhook_cycle_completion_checkbox.setChecked(True)
        
        self.automation.save_calibration()

    def disable_all_notifications(self):
        """Disable all webhook notifications"""
        self.automation.webhook_roblox_detected = False
        self.automation.webhook_roblox_reconnected = False
        self.automation.webhook_automation_started = False
        self.automation.webhook_automation_stopped = False
        self.automation.webhook_auto_sell_started = False
        self.automation.webhook_back_to_fishing = False
        self.automation.webhook_failsafe_triggered = False
        self.automation.webhook_error_notifications = False
        self.automation.webhook_phase_changes = False
        self.automation.webhook_cycle_completion = False
        
        # Update checkbox states
        self.webhook_roblox_detected_checkbox.setChecked(False)
        self.webhook_roblox_reconnected_checkbox.setChecked(False)
        self.webhook_automation_started_checkbox.setChecked(False)
        self.webhook_automation_stopped_checkbox.setChecked(False)
        self.webhook_auto_sell_started_checkbox.setChecked(False)
        self.webhook_back_to_fishing_checkbox.setChecked(False)
        self.webhook_failsafe_triggered_checkbox.setChecked(False)
        self.webhook_error_notifications_checkbox.setChecked(False)
        self.webhook_phase_changes_checkbox.setChecked(False)
        self.webhook_cycle_completion_checkbox.setChecked(False)
        
        self.automation.save_calibration()

    def update_auto_sell_enabled(self, state):
        self.automation.auto_sell_enabled = state == Qt.CheckState.Checked.value
        # Sync with auto sell manager
        if hasattr(self.automation, 'auto_sell_manager'):
            self.automation.auto_sell_manager.set_auto_sell_enabled(self.automation.auto_sell_enabled)
        self.automation.save_calibration()

    def update_fish_count_until_auto_sell(self, value):
        self.automation.fish_count_until_auto_sell = value
        self.automation.save_calibration()

    def update_disable_all_pathing(self, state):
        self.automation.disable_all_pathing = state == Qt.CheckState.Checked.value
        self.automation.save_calibration()

    def update_auto_reconnect_enabled(self, state):
        self.automation.auto_reconnect_enabled = state == Qt.CheckState.Checked.value
        self.automation.save_calibration()

    def update_auto_reconnect_time(self, value):
        self.automation.auto_reconnect_time = value
        self.automation.save_calibration()

    def update_window_mode(self, text):
        self.automation.roblox_window_mode = "windowed" if text == "Windowed" else "fullscreen"
        self.automation.save_calibration()

    def validate_private_server_link(self, link):
        """Validate the private server link and return validation result"""
        link = link.strip()
        
        if not link:
            return {"valid": True, "message": "", "type": "empty"}
        
        # Check if it's a share link
        if "share?code=" in link and "roblox.com" in link:
            return {
                "valid": False, 
                "message": "Share link detected - conversion required", 
                "type": "share_link",
                "link": link
            }
        
        # Check if it's a proper private server link
        if "privateServerLinkCode=" in link and "roblox.com" in link:
            return {"valid": True, "message": "Valid private server link", "type": "private_server"}
        
        # Check if it's a roblox:// protocol link
        if link.startswith("roblox://") and "placeId=" in link:
            return {"valid": True, "message": "Valid roblox:// protocol link", "type": "roblox_protocol"}
        
        # Check if it looks like a Roblox link but might be wrong format
        if "roblox.com" in link:
            return {
                "valid": False, 
                "message": "Invalid Roblox link format", 
                "type": "invalid_roblox"
            }
        
        # Not a Roblox link at all
        return {
            "valid": False, 
            "message": "Not a valid Roblox link", 
            "type": "invalid"
        }

    def show_share_link_instructions(self, share_link):
        """Show instructions for converting a share link to private server link"""
        msg = QMessageBox(self)
        msg.setWindowTitle("Share Link Detected")
        msg.setIcon(QMessageBox.Icon.Information)
        
        instructions = f"""Share Link Conversion Required

You've entered a share link:
{share_link}

To convert this to a proper private server link, please follow these steps:

1. Copy the share link you entered
2. Open your web browser 
3. Paste the link in the address bar and press Enter
4. Roblox will redirect you to the game page
5. Copy the NEW URL from the address bar (it should contain 'privateServerLinkCode=')
6. Come back here and paste the new URL

The new URL should look like:
https://www.roblox.com/games/XXXXXXX/Game-Name?privateServerLinkCode=XXXXXXXXXX

Click OK to acknowledge these instructions."""

        msg.setText(instructions)
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.setStyleSheet("""
            QMessageBox {
                background-color: #2d2d2d;
                color: white;
                font-size: 12px;
                min-width: 500px;
            }
            QMessageBox QPushButton {
                background-color: #17a2b8;
                color: white;
                border: 1px solid #138496;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
                min-width: 80px;
            }
            QMessageBox QPushButton:hover {
                background-color: #138496;
            }
        """)
        msg.exec()

    def update_private_server_link(self, text):
        # Validate the link
        validation = self.validate_private_server_link(text)
        
        # Update the visual feedback
        self.update_link_validation_display(validation)
        
        # Show instructions for share links
        if validation["type"] == "share_link":
            # Clear the invalid link first
            self.private_server_input.clear()
            self.show_share_link_instructions(validation["link"])
            return
        
        # Save the link if it's valid or empty
        self.automation.roblox_private_server_link = text
        self.automation.save_calibration()

    def update_link_validation_display(self, validation):
        """Update the UI to show link validation status"""
        if not hasattr(self, 'link_status_label'):
            return
            
        if validation["type"] == "empty":
            self.link_status_label.setText("")
            self.link_status_label.hide()
        elif validation["valid"]:
            self.link_status_label.setText("✓ " + validation["message"])
            self.link_status_label.setStyleSheet("color: #28a745; font-size: 10px; font-weight: 500;")  # Green
            self.link_status_label.show()
        else:
            self.link_status_label.setText("⚠ " + validation["message"])
            if validation["type"] == "share_link":
                self.link_status_label.setStyleSheet("color: #fd7e14; font-size: 10px; font-weight: 500;")  # Orange
            else:
                self.link_status_label.setStyleSheet("color: #dc3545; font-size: 10px; font-weight: 500;")  # Red
            self.link_status_label.show()

    def update_auto_reconnect_display(self):
        """Update the auto reconnect timer display"""
        if not hasattr(self, 'timer_label'):
            return
            
        if not self.automation.auto_reconnect_enabled or not self.automation.running:
            self.timer_label.setText("Time until reconnect: --:--")
            return
            
        remaining_seconds = self.automation.get_auto_reconnect_time_remaining()
        if remaining_seconds is None:
            self.timer_label.setText("Time until reconnect: --:--")
            return
            
        # Convert seconds to minutes and seconds
        minutes = int(remaining_seconds // 60)
        seconds = int(remaining_seconds % 60)
        
        if remaining_seconds <= 0:
            self.timer_label.setText("Time until reconnect: Reconnecting...")
            self.timer_label.setStyleSheet("color: #dc3545; font-size: 11px; font-weight: 500;")  # Red
        elif remaining_seconds <= 60:  # Less than 1 minute
            self.timer_label.setText(f"Time until reconnect: {seconds}s")
            self.timer_label.setStyleSheet("color: #fd7e14; font-size: 11px; font-weight: 500;")  # Orange
        else:
            self.timer_label.setText(f"Time until reconnect: {minutes}:{seconds:02d}")
            self.timer_label.setStyleSheet("color: #4a9eff; font-size: 11px; font-weight: 500;")  # Blue

    def update_mouse_delay_enabled(self, state):
        self.automation.mouse_delay_enabled = state == Qt.CheckState.Checked.value
        self.automation.save_calibration()

    def update_mouse_delay_amount(self, value):
        self.automation.mouse_delay_ms = value
        self.automation.save_calibration()

    def update_failsafe_enabled(self, state):
        self.automation.failsafe_enabled = state == Qt.CheckState.Checked.value
        self.automation.save_calibration()

    def update_failsafe_timeout(self, value):
        # Enforce minimum of 20 seconds
        if value < 20:
            value = 20
            self.failsafe_timeout_spinbox.setValue(20)
        self.automation.failsafe_timeout = value
        self.automation.save_calibration()

    def open_advanced_calibrations(self):
        """Open the advanced calibrations window"""
        if self.advanced_calibration_window is None:
            self.advanced_calibration_window = AdvancedCalibrationWindow(self.automation, self)

        self.advanced_calibration_window.show()
        self.advanced_calibration_window.raise_()
        self.advanced_calibration_window.activateWindow()

    def get_display_scale(self):
        """Get the current display scale percentage"""
        try:
            import ctypes

            # Get the DPI of the primary monitor
            hdc = ctypes.windll.user32.GetDC(0)
            dpi = ctypes.windll.gdi32.GetDeviceCaps(hdc, 88)  # LOGPIXELSX
            ctypes.windll.user32.ReleaseDC(0, hdc)

            # Calculate scale percentage (96 DPI = 100%)
            scale_percentage = round((dpi / 96.0) * 100)
            return scale_percentage
        except Exception:
            return 100  # Default to 100% if detection fails

    def check_display_scale(self):
        """Check display scale and warn user if not 100%"""
        scale = self.get_display_scale()
        if scale != 100:
            msg = QMessageBox(self)
            msg.setWindowTitle("Display Scale Warning")
            msg.setText(f"Display Scale Detection\n\nYour current display scale is {scale}%.\n\nThis macro was designed for 100% display scale. Using a different scale may cause coordinate calibrations to be inaccurate. We have some scalled configurations available, but they may not work perfectly.\n\nIt is highly recommended to change your display scale to 100% for optimal performance.\n\nClick OK to open Display Settings.")
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.setStandardButtons(QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
            msg.setDefaultButton(QMessageBox.StandardButton.Ok)
            msg.setStyleSheet("""
                QMessageBox {
                    background-color: #2d2d2d;
                    color: white;
                    font-size: 12px;
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

            result = msg.exec()
            if result == QMessageBox.StandardButton.Ok:
                self.open_display_settings()

    def open_display_settings(self):
        """Open Windows Display Settings"""
        try:
            import subprocess
            # Use start command to open the settings URI
            subprocess.run(['start', 'ms-settings:display'], shell=True, check=False)
        except Exception as e:
            print(f"Failed to open display settings: {e}")
            # Fallback: try to open legacy display settings
            try:
                subprocess.run(['control', 'desk.cpl'], shell=True, check=False)
            except Exception as e2:
                print(f"Failed to open legacy display settings: {e2}")

    def show_first_launch_warning(self):
        """Show first launch warning about Custom Fonts in Roblox"""
        if not self.automation.first_launch_warning_shown:
            msg = QMessageBox(self)
            msg.setWindowTitle("Important Warning - Custom Fonts")
            msg.setText("⚠️ IMPORTANT WARNING ⚠️\n\nUsing Custom Fonts in Roblox will break this macro!\n\nThe macro relies on pixel detection in the shaded area of the fishing bar to determine the correct color for the reeling minigame. Custom fonts can block or interfere with these critical pixels, causing the macro to fail during the fishing process.\n\nPlease ensure that Custom Fonts are DISABLED in Blox/Fish/Voidstrap settings before using this macro.\n\nClick OK to acknowledge this warning.")
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.setStandardButtons(QMessageBox.StandardButton.Ok)
            msg.setDefaultButton(QMessageBox.StandardButton.Ok)
            msg.setStyleSheet("""
                QMessageBox {
                    background-color: #2d2d2d;
                    color: white;
                    font-size: 12px;
                    min-width: 500px;
                }
                QMessageBox QPushButton {
                    background-color: #dc3545;
                    color: white;
                    border: 1px solid #c82333;
                    padding: 8px 16px;
                    border-radius: 4px;
                    font-weight: bold;
                    min-width: 80px;
                }
                QMessageBox QPushButton:hover {
                    background-color: #c82333;
                }
                QMessageBox QPushButton:pressed {
                    background-color: #bd2130;
                }
            """)

            result = msg.exec()
            if result == QMessageBox.StandardButton.Ok:
                # Mark the warning as shown and save config
                self.automation.first_launch_warning_shown = True
                self.automation.save_calibration()

    def create_fish_desc_calibration_row(self, parent_layout):
        """Create calibration row specifically for fish caught description"""
        frame = QFrame()
        frame.setFixedHeight(50)
        frame.setStyleSheet("""
            QFrame {
                background-color: #2d2d2d;
                border: 1px solid #404040;
                border-radius: 6px;
                margin: 1px;
            }
        """)

        frame_layout = QHBoxLayout(frame)
        frame_layout.setContentsMargins(12, 8, 12, 8)
        frame_layout.setSpacing(10)

        # Left side - Info
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)

        # Coordinate name
        name_label = QLabel("Fish Caught Description")
        name_label.setStyleSheet("color: #ffffff; font-weight: 600; font-size: 12px;")
        info_layout.addWidget(name_label)

        # Current coordinates
        coord_label = QLabel(self.get_fish_desc_coord_text())
        coord_label.setStyleSheet("color: #888888; font-size: 10px; font-family: 'Consolas', monospace;")
        info_layout.addWidget(coord_label)

        frame_layout.addLayout(info_layout)
        frame_layout.addStretch()

        # Right side - Calibrate button
        calib_btn = QPushButton("Calibrate")
        calib_btn.clicked.connect(self.start_fish_desc_calibration)
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

        # Store reference for updating
        self.fish_desc_coord_label = coord_label

    def create_shop_calibration_rows(self, parent_layout):
        """Create calibration rows for shop and collection coordinates"""
        shop_coords = {
            'sell_button': 'Sell Button',
            'sell_fish_shop': 'Sell Fish Shop',
            'collection_button': 'Collection Button', 
            'exit_collections': 'Exit Collections',
            'exit_fish_shop': 'Exit Fish Shop'
        }
        
        self.shop_coord_labels = {}
        
        for coord_name, display_name in shop_coords.items():
            frame = QFrame()
            frame.setFixedHeight(50)
            frame.setStyleSheet("""
                QFrame {
                    background-color: #2d2d2d;
                    border: 1px solid #404040;
                    border-radius: 6px;
                    margin: 1px;
                }
            """)

            frame_layout = QHBoxLayout(frame)
            frame_layout.setContentsMargins(12, 8, 12, 8)
            frame_layout.setSpacing(10)

            # Left side - Info
            info_layout = QVBoxLayout()
            info_layout.setSpacing(2)

            # Coordinate name
            name_label = QLabel(display_name)
            name_label.setStyleSheet("color: #ffffff; font-weight: 600; font-size: 12px;")
            info_layout.addWidget(name_label)

            # Current coordinates
            coord_label = QLabel(self.get_shop_coord_text(coord_name))
            coord_label.setStyleSheet("color: #888888; font-size: 10px; font-family: 'Consolas', monospace;")
            info_layout.addWidget(coord_label)

            frame_layout.addLayout(info_layout)
            frame_layout.addStretch()

            # Right side - Calibrate button
            calib_btn = QPushButton("Calibrate")
            calib_btn.clicked.connect(lambda checked, name=coord_name: self.start_shop_calibration(name))
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

            # Store reference for updating
            self.shop_coord_labels[coord_name] = coord_label

    def get_shop_coord_text(self, coord_name):
        """Get coordinate text for shop coordinates"""
        if coord_name in self.automation.coordinates:
            coord = self.automation.coordinates[coord_name]
            if len(coord) == 2:
                return f"({coord[0]}, {coord[1]})"
        return "Not set"

    def start_shop_calibration(self, coord_name):
        """Start calibration for shop coordinates"""
        if self.calibrating:
            return

        self.calibrating = True
        self.current_calibration = coord_name

        # Hide the main window during calibration for better focus
        self.hide()

        # Create overlay window
        coord_display_names = {
            'sell_fish_shop': 'Sell Fish Shop',
            'collection_button': 'Collection Button',
            'exit_collections': 'Exit Collections', 
            'exit_fish_shop': 'Exit Fish Shop'
        }
        
        display_name = coord_display_names.get(coord_name, coord_name)
        message = f"Calibrating: {display_name}"

        self.overlay = CalibrationOverlay(message)
        self.overlay.coordinate_selected.connect(self.on_shop_calibration_click)
        self.overlay.calibration_cancelled.connect(self.cancel_shop_calibration)

        # Show the overlay
        self.overlay.show()

    def on_shop_calibration_click(self, x, y):
        """Handle shop calibration clicks"""
        # Set the coordinate
        self.automation.coordinates[self.current_calibration] = (x, y)
        
        # Close overlay
        self.overlay.close()
        self.complete_shop_calibration()

    def complete_shop_calibration(self):
        """Complete shop calibration"""
        self.calibrating = False

        # Update the coordinate label
        if self.current_calibration in self.shop_coord_labels:
            coord_label = self.shop_coord_labels[self.current_calibration]
            coord_label.setText(self.get_shop_coord_text(self.current_calibration))

        # Auto-save the calibration
        self.automation.save_calibration()

        self.current_calibration = None

        # Show the main window again
        self.show()
        self.raise_()
        self.activateWindow()

    def cancel_shop_calibration(self):
        """Cancel shop calibration"""
        self.calibrating = False
        self.current_calibration = None

        # Show the main window again
        self.show()
        self.raise_()
        self.activateWindow()

    def get_fish_desc_coord_text(self):
        """Get coordinate text for fish caught description"""
        if 'fish_caught_desc' in self.automation.coordinates:
            coord = self.automation.coordinates['fish_caught_desc']
            if len(coord) == 4:
                return f"({coord[0]}, {coord[1]}, {coord[2]}, {coord[3]})"
        return "Not set"

    def start_fish_desc_calibration(self):
        """Start calibration for fish caught description"""
        if self.calibrating:
            return

        self.calibrating = True
        self.current_calibration = 'fish_caught_desc'

        # Hide the main window during calibration for better focus
        self.hide()

        # Create overlay window for top-left corner
        message = "Fish Caught Description - Click the top-left corner of the description area"
        self.fish_caught_desc_step = 1

        self.overlay = CalibrationOverlay(message)
        self.overlay.coordinate_selected.connect(self.on_fish_desc_calibration_click)
        self.overlay.calibration_cancelled.connect(self.cancel_fish_desc_calibration)

        # Show the overlay
        self.overlay.show()

    def on_fish_desc_calibration_click(self, x, y):
        """Handle fish description calibration clicks"""
        if self.fish_caught_desc_step == 1:
            # Store top-left coordinates
            self.fish_caught_desc_top_left = (x, y)
            self.fish_caught_desc_step = 2

            # Close current overlay
            self.overlay.close()

            # Show second overlay for bottom-right
            message = "Fish Caught Description - Click the bottom-right corner of the description area"
            self.overlay = CalibrationOverlay(message)
            self.overlay.coordinate_selected.connect(self.on_fish_desc_calibration_click)
            self.overlay.calibration_cancelled.connect(self.cancel_fish_desc_calibration)
            self.overlay.show()
            return
        else:
            # Complete fish caught description calibration with bottom-right coordinates
            self.fish_caught_desc_bottom_right = (x, y)
            self.automation.coordinates['fish_caught_desc'] = (
                self.fish_caught_desc_top_left[0], self.fish_caught_desc_top_left[1],
                self.fish_caught_desc_bottom_right[0], self.fish_caught_desc_bottom_right[1]
            )

        # Close overlay
        self.overlay.close()
        self.complete_fish_desc_calibration()

    def complete_fish_desc_calibration(self):
        """Complete fish description calibration"""
        self.calibrating = False

        # Update the coordinate label
        self.fish_desc_coord_label.setText(self.get_fish_desc_coord_text())

        # Auto-save the calibration
        self.automation.save_calibration()

        self.current_calibration = None

        # Show the main window again
        self.show()
        self.raise_()
        self.activateWindow()

    def cancel_fish_desc_calibration(self):
        """Cancel fish description calibration"""
        self.calibrating = False
        self.current_calibration = None

        # Show the main window again
        self.show()
        self.raise_()
        self.activateWindow()



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
                background-color: transparent;
                border: none;
            }
            QScrollArea QWidget {
                background-color: transparent;
            }
            QScrollBar:vertical {
                background-color: #2d2d2d;
                width: 12px;
                border-radius: 6px;
                margin: 0;
            }
            QScrollBar::handle:vertical {
                background-color: #555555;
                border-radius: 6px;
                min-height: 20px;
                margin: 2px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #4a9eff;
            }
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0;
                width: 0;
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
            QTabWidget::pane {
                border: 1px solid #404040;
                background-color: #2d2d2d;
                border-radius: 6px;
                margin-top: 2px;
            }
            QTabBar::tab {
                background-color: #404040;
                color: #e0e0e0;
                border: 1px solid #555555;
                padding: 10px 20px;
                margin-right: 2px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                font-weight: 500;
                min-width: 80px;
                font-size: 12px;
            }
            QTabBar::tab:selected {
                background-color: #4a9eff;
                color: white;
                font-weight: 600;
                border-color: #4a9eff;
            }
            QTabBar::tab:hover:!selected {
                background-color: #555555;
                border-color: #666666;
            }
            QTabWidget::tab-bar {
                alignment: center;
            }
            QLineEdit {
                background-color: #2d2d2d;
                color: #e0e0e0;
                border: 1px solid #555555;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 11px;
            }
            QLineEdit:focus {
                border-color: #4a9eff;
            }
            QCheckBox {
                color: #e0e0e0;
                font-size: 11px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 2px solid #555555;
                border-radius: 3px;
                background-color: #2d2d2d;
            }
            QCheckBox::indicator:checked {
                background-color: #4a9eff;
                border-color: #4a9eff;
            }
            QCheckBox::indicator:hover {
                border-color: #4a9eff;
            }
            QSpinBox {
                background-color: #2d2d2d;
                color: #e0e0e0;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 11px;
                min-width: 80px;
            }
            QSpinBox:focus {
                border-color: #4a9eff;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                background-color: #404040;
                border: 1px solid #555555;
                width: 16px;
                border-radius: 2px;
            }
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {
                background-color: #4a9eff;
            }
            QComboBox {
                background-color: #2d2d2d;
                color: #e0e0e0;
                border: 1px solid #555555;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 11px;
                min-width: 180px;
            }
            QComboBox:focus {
                border-color: #4a9eff;
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
                border-radius: 4px;
            }
        """)

    def setup_ui(self):
        self.setWindowTitle("FishScope Macro")
        self.setFixedSize(700, 700)  # Increased size for better tab display

        # Set application icon
        if os.path.exists("icon.ico"):
            self.setWindowIcon(QIcon("icon.ico"))

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 15, 15, 15)

        # Header Section
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

        # Create the tab widget
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #404040;
                background-color: #2d2d2d;
                border-radius: 6px;
            }
            QTabBar::tab {
                background-color: #404040;
                color: #e0e0e0;
                border: 1px solid #555555;
                padding: 8px 16px;
                margin-right: 2px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                font-weight: 500;
                min-width: 80px;
            }
            QTabBar::tab:selected {
                background-color: #4a9eff;
                color: white;
                font-weight: 600;
            }
            QTabBar::tab:hover:!selected {
                background-color: #555555;
            }
            QTabWidget::tab-bar {
                alignment: center;
            }
        """)

        # Create tabs
        self.create_controls_tab()
        self.create_calibrations_tab()
        self.create_webhook_tab()
        self.create_settings_tab()

        # Connect tab change signal to check for Tesseract on webhook tab
        self.tab_widget.currentChanged.connect(self.on_tab_changed)

        main_layout.addWidget(self.tab_widget)

        # Footer Section
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

        main_layout.addLayout(footer_layout)

        # Check display scale after UI is set up
        QTimer.singleShot(1000, self.check_display_scale)

    def create_controls_tab(self):
        """Create the Controls tab with macro controls and hotkey info"""
        controls_tab = QWidget()
        self.tab_widget.addTab(controls_tab, "Controls")
        
        # Add scroll area to the controls tab
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setSpacing(15)
        scroll_layout.setContentsMargins(10, 10, 10, 10)

        # VIP Gamepass Notice Section
        vip_notice_group = QGroupBox("Important Notice")
        vip_notice_layout = QVBoxLayout(vip_notice_group)
        vip_notice_layout.setSpacing(8)
        vip_notice_layout.setContentsMargins(12, 15, 12, 12)

        vip_notice_label = QLabel("You need the \"VIP\" Gamepass WalkSpeed boost for Auto Reconnect and Auto Sell features to work properly.")
        vip_notice_label.setWordWrap(True)
        vip_notice_label.setStyleSheet("""
            QLabel {
                color: #856404;
                background-color: #fff3cd;
                border: 1px solid #ffeaa7;
                border-radius: 4px;
                padding: 10px;
                font-size: 12px;
                font-weight: 500;
            }
        """)
        vip_notice_layout.addWidget(vip_notice_label)
        scroll_layout.addWidget(vip_notice_group)

        # Control Section
        control_group = QGroupBox("Macro Controls")
        control_layout = QVBoxLayout(control_group)
        control_layout.setSpacing(8)
        control_layout.setContentsMargins(12, 15, 12, 12)

        # Hotkey info
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

        # Control buttons
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
        scroll_layout.addWidget(control_group)

        # Auto Reconnect Section
        auto_reconnect_group = QGroupBox("Auto Reconnect")
        auto_reconnect_layout = QVBoxLayout(auto_reconnect_group)
        auto_reconnect_layout.setSpacing(8)
        auto_reconnect_layout.setContentsMargins(12, 15, 12, 12)

        # Auto reconnect info
        reconnect_info = QLabel("Automatically reconnect to private server after specified time")
        reconnect_info.setStyleSheet("color: #888888; font-size: 11px; margin-bottom: 6px;")
        auto_reconnect_layout.addWidget(reconnect_info)

        # Auto reconnect enabled checkbox
        reconnect_enable_layout = QHBoxLayout()
        reconnect_enable_layout.setSpacing(10)

        self.auto_reconnect_checkbox = QCheckBox("Enable Auto Reconnect")
        self.auto_reconnect_checkbox.setChecked(self.automation.auto_reconnect_enabled)
        self.auto_reconnect_checkbox.stateChanged.connect(self.update_auto_reconnect_enabled)
        self.auto_reconnect_checkbox.setStyleSheet("""
            QCheckBox {
                color: #e0e0e0;
                font-size: 11px;
                font-weight: 500;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 2px solid #555555;
                border-radius: 3px;
                background-color: #2d2d2d;
            }
            QCheckBox::indicator:checked {
                background-color: #4a9eff;
                border-color: #4a9eff;
            }
        """)
        reconnect_enable_layout.addWidget(self.auto_reconnect_checkbox)
        reconnect_enable_layout.addStretch()
        auto_reconnect_layout.addLayout(reconnect_enable_layout)

        # Time until reconnect setting
        time_layout = QHBoxLayout()
        time_layout.setSpacing(10)

        time_label = QLabel("Time until reconnect (minutes):")
        time_label.setStyleSheet("color: #e0e0e0; font-size: 11px;")
        time_layout.addWidget(time_label)

        self.auto_reconnect_time_spinbox = QSpinBox()
        self.auto_reconnect_time_spinbox.setRange(1, 1440)  # 1 minute to 24 hours
        self.auto_reconnect_time_spinbox.setValue(self.automation.auto_reconnect_time)
        self.auto_reconnect_time_spinbox.setSuffix(" min")
        self.auto_reconnect_time_spinbox.valueChanged.connect(self.update_auto_reconnect_time)
        self.auto_reconnect_time_spinbox.setStyleSheet("""
            QSpinBox {
                background-color: #2d2d2d;
                color: #e0e0e0;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 11px;
                min-width: 80px;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                background-color: #404040;
                border: 1px solid #555555;
                width: 16px;
            }
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {
                background-color: #4a9eff;
            }
        """)
        time_layout.addWidget(self.auto_reconnect_time_spinbox)
        time_layout.addStretch()
        auto_reconnect_layout.addLayout(time_layout)

        # Private server link input
        server_link_layout = QVBoxLayout()
        server_link_layout.setSpacing(5)

        server_link_label = QLabel("Roblox Private Server Link:")
        server_link_label.setStyleSheet("color: #e0e0e0; font-size: 11px;")
        server_link_layout.addWidget(server_link_label)

        self.private_server_input = QLineEdit()
        self.private_server_input.setPlaceholderText("https://www.roblox.com/games/16732694052?privateServerLinkCode=...")
        self.private_server_input.setText(self.automation.roblox_private_server_link)
        self.private_server_input.textChanged.connect(self.update_private_server_link)
        self.private_server_input.setStyleSheet("""
            QLineEdit {
                background-color: #2d2d2d;
                color: #e0e0e0;
                border: 1px solid #555555;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 11px;
            }
            QLineEdit:focus {
                border-color: #4a9eff;
            }
        """)
        server_link_layout.addWidget(self.private_server_input)

        # Link validation status
        self.link_status_label = QLabel("")
        self.link_status_label.setStyleSheet("color: #888888; font-size: 10px;")
        self.link_status_label.hide()  # Hidden by default
        server_link_layout.addWidget(self.link_status_label)
        
        auto_reconnect_layout.addLayout(server_link_layout)

        # Roblox window mode setting
        window_mode_layout = QHBoxLayout()
        window_mode_layout.setSpacing(10)

        window_mode_label = QLabel("Roblox when launched:")
        window_mode_label.setStyleSheet("color: #e0e0e0; font-size: 11px;")
        window_mode_layout.addWidget(window_mode_label)

        self.window_mode_combo = QComboBox()
        self.window_mode_combo.addItems(["Windowed", "Fullscreen"])
        self.window_mode_combo.setCurrentText("Windowed" if self.automation.roblox_window_mode == "windowed" else "Fullscreen")
        self.window_mode_combo.currentTextChanged.connect(self.update_window_mode)
        self.window_mode_combo.setStyleSheet("""
            QComboBox {
                background-color: #3d3d3d;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 4px 8px;
                color: #e0e0e0;
                font-size: 11px;
                min-width: 100px;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid #888888;
                margin-right: 5px;
            }
            QComboBox QAbstractItemView {
                background-color: #3d3d3d;
                border: 1px solid #555555;
                selection-background-color: #4a9eff;
                color: #e0e0e0;
            }
        """)
        window_mode_layout.addWidget(self.window_mode_combo)
        window_mode_layout.addStretch()
        auto_reconnect_layout.addLayout(window_mode_layout)

        # Timer display
        timer_layout = QHBoxLayout()
        timer_layout.setSpacing(10)

        self.timer_label = QLabel("Time until reconnect: --:--")
        self.timer_label.setStyleSheet("color: #4a9eff; font-size: 11px; font-weight: 500;")
        timer_layout.addWidget(self.timer_label)
        timer_layout.addStretch()
        auto_reconnect_layout.addLayout(timer_layout)

        # Auto reconnect behavior note
        reconnect_note = QLabel("ℹ Once reconnected, waits 60 seconds before clicking Start in SOLS.")
        reconnect_note.setStyleSheet("color: #888888; font-size: 9px; font-style: italic; margin-top: 5px;")
        auto_reconnect_layout.addWidget(reconnect_note)

        scroll_layout.addWidget(auto_reconnect_group)

        # Trigger initial validation of private server link
        if self.automation.roblox_private_server_link:
            validation = self.validate_private_server_link(self.automation.roblox_private_server_link)
            self.update_link_validation_display(validation)

        # Add stretch to push content to top
        scroll_layout.addStretch()

        scroll_area.setWidget(scroll_widget)
        
        # Set layout for controls tab
        tab_layout = QVBoxLayout(controls_tab)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.addWidget(scroll_area)

    def create_calibrations_tab(self):
        """Create the Calibrations tab with premade and custom calibrations"""
        calibrations_tab = QWidget()
        self.tab_widget.addTab(calibrations_tab, "Calibrations")
        
        # Add scroll area to the calibrations tab
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setSpacing(15)
        scroll_layout.setContentsMargins(10, 10, 10, 10)

        # Premade Calibrations Section
        premade_group = QGroupBox("Premade Calibrations")
        premade_layout = QVBoxLayout(premade_group)
        premade_layout.setContentsMargins(12, 15, 12, 12)
        premade_layout.setSpacing(8)

        premade_info = QLabel("Select a premade calibration to quickly set up coordinates")
        premade_info.setStyleSheet("color: #888888; font-size: 11px; margin-bottom: 6px;")
        premade_layout.addWidget(premade_info)

        # Premade calibrations selector
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
        scroll_layout.addWidget(premade_group)

        # Custom Calibrations Section
        calibrations_group = QGroupBox("Custom Calibrations")
        calibrations_layout = QVBoxLayout(calibrations_group)
        calibrations_layout.setContentsMargins(12, 15, 12, 12)
        calibrations_layout.setSpacing(8)

        calibrations_info = QLabel("Configure coordinate positions for specific game elements")
        calibrations_info.setStyleSheet("color: #888888; font-size: 11px; margin-bottom: 6px;")
        calibrations_layout.addWidget(calibrations_info)

        # Fish caught description calibration
        fish_desc_label = QLabel("Fish Caught Description:")
        fish_desc_label.setStyleSheet("color: #e0e0e0; font-weight: 500; margin-top: 5px;")
        calibrations_layout.addWidget(fish_desc_label)

        fish_desc_info = QLabel("Calibrate the area where fish descriptions appear for OCR extraction")
        fish_desc_info.setStyleSheet("color: #888888; font-size: 11px; margin-bottom: 6px;")
        calibrations_layout.addWidget(fish_desc_info)

        # Create calibration row for fish_caught_desc
        self.create_fish_desc_calibration_row(calibrations_layout)

        # Spacer
        calibrations_layout.addWidget(QLabel(""))

        # Shop calibrations section
        shop_label = QLabel("Shop & Sell Calibrations:")
        shop_label.setStyleSheet("color: #e0e0e0; font-weight: 500; margin-top: 10px;")
        calibrations_layout.addWidget(shop_label)

        shop_info = QLabel("Configure coordinates for shop interactions and selling")
        shop_info.setStyleSheet("color: #888888; font-size: 11px; margin-bottom: 6px;")
        calibrations_layout.addWidget(shop_info)

        # Create calibration rows for the new coordinates
        self.create_shop_calibration_rows(calibrations_layout)

        # Advanced Calibrations button
        calibrations_layout.addWidget(QLabel(""))
        advanced_calib_layout = QHBoxLayout()
        advanced_calib_layout.setSpacing(10)

        advanced_calib_label = QLabel("Advanced (Custom Calibrations):")
        advanced_calib_label.setStyleSheet("color: #e0e0e0; font-weight: 500; font-size: 12px;")
        advanced_calib_layout.addWidget(advanced_calib_label)

        advanced_calib_btn = QPushButton("Open Calibrations")
        advanced_calib_btn.clicked.connect(self.open_advanced_calibrations)
        advanced_calib_btn.setStyleSheet("""
            QPushButton {
                background-color: #6f42c1;
                color: white;
                font-weight: 600;
                padding: 8px 16px;
                font-size: 12px;
                border: none;
                border-radius: 6px;
                min-width: 140px;
            }
            QPushButton:hover {
                background-color: #5a32a3;
            }
            QPushButton:pressed {
                background-color: #4c2a85;
            }
        """)
        advanced_calib_layout.addWidget(advanced_calib_btn)
        advanced_calib_layout.addStretch()

        calibrations_layout.addLayout(advanced_calib_layout)

        scroll_layout.addWidget(calibrations_group)

        # Control buttons
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(12)
        buttons_layout.addStretch()

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
        buttons_layout.addWidget(reset_btn)
        buttons_layout.addStretch()

        scroll_layout.addLayout(buttons_layout)

        # Add stretch to push content to top
        scroll_layout.addStretch()

        scroll_area.setWidget(scroll_widget)
        
        # Set layout for calibrations tab
        tab_layout = QVBoxLayout(calibrations_tab)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.addWidget(scroll_area)

    def create_webhook_tab(self):
        """Create the Webhook tab with Discord webhook settings and fish filtering"""
        webhook_tab = QWidget()
        self.tab_widget.addTab(webhook_tab, "Webhook")
        
        # Add scroll area to the webhook tab
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setSpacing(15)
        scroll_layout.setContentsMargins(10, 10, 10, 10)

        # Webhook Settings Section
        webhook_group = QGroupBox("Webhook Settings")
        webhook_layout = QVBoxLayout(webhook_group)
        webhook_layout.setContentsMargins(12, 15, 12, 12)
        webhook_layout.setSpacing(8)

        webhook_label = QLabel("Webhook URL:")
        webhook_label.setStyleSheet("color: #e0e0e0; font-weight: 500;")
        webhook_layout.addWidget(webhook_label)

        self.webhook_input = QLineEdit()
        self.webhook_input.setPlaceholderText("Enter your discord webhook URL here")
        self.webhook_input.setText(self.automation.webhook_url)  # Load saved webhook URL
        self.webhook_input.setStyleSheet("""
            QLineEdit {
                background-color: #2d2d2d;
                color: #e0e0e0;
                border: 1px solid #555555;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 11px;
            }
        """)
        self.webhook_input.textChanged.connect(self.on_webhook_url_changed)
        webhook_layout.addWidget(self.webhook_input)

        scroll_layout.addWidget(webhook_group)

        # Notification Types Section
        notifications_group = QGroupBox("Notification Types")
        notifications_layout = QVBoxLayout(notifications_group)
        notifications_layout.setContentsMargins(12, 15, 12, 12)
        notifications_layout.setSpacing(8)

        notifications_info = QLabel("Enable or disable specific types of webhook notifications")
        notifications_info.setStyleSheet("color: #888888; font-size: 11px; margin-bottom: 8px;")
        notifications_layout.addWidget(notifications_info)

        # Process & Connection Events
        process_section = QLabel("Process & Connection Events")
        process_section.setStyleSheet("color: #4a9eff; font-weight: 600; font-size: 12px; margin-top: 8px;")
        notifications_layout.addWidget(process_section)

        self.webhook_roblox_detected_checkbox = QCheckBox("Roblox Process Detected")
        self.webhook_roblox_detected_checkbox.setChecked(self.automation.webhook_roblox_detected)
        self.webhook_roblox_detected_checkbox.stateChanged.connect(self.update_webhook_roblox_detected)
        self.webhook_roblox_detected_checkbox.setStyleSheet(self.get_checkbox_style())
        notifications_layout.addWidget(self.webhook_roblox_detected_checkbox)

        self.webhook_roblox_reconnected_checkbox = QCheckBox("Roblox Reconnection Events")
        self.webhook_roblox_reconnected_checkbox.setChecked(self.automation.webhook_roblox_reconnected)
        self.webhook_roblox_reconnected_checkbox.stateChanged.connect(self.update_webhook_roblox_reconnected)
        self.webhook_roblox_reconnected_checkbox.setStyleSheet(self.get_checkbox_style())
        notifications_layout.addWidget(self.webhook_roblox_reconnected_checkbox)

        # Automation Events
        automation_section = QLabel("Macro Events")
        automation_section.setStyleSheet("color: #28a745; font-weight: 600; font-size: 12px; margin-top: 12px;")
        notifications_layout.addWidget(automation_section)

        self.webhook_macro_started_checkbox = QCheckBox("Macro Started")
        self.webhook_macro_started_checkbox.setChecked(self.automation.webhook_macro_started)
        self.webhook_macro_started_checkbox.stateChanged.connect(self.update_webhook_macro_started)
        self.webhook_macro_started_checkbox.setStyleSheet(self.get_checkbox_style())
        notifications_layout.addWidget(self.webhook_macro_started_checkbox)

        self.webhook_macro_stopped_checkbox = QCheckBox("Macro Stopped")
        self.webhook_macro_stopped_checkbox.setChecked(self.automation.webhook_macro_stopped)
        self.webhook_macro_stopped_checkbox.stateChanged.connect(self.update_webhook_macro_stopped)
        self.webhook_macro_stopped_checkbox.setStyleSheet(self.get_checkbox_style())
        notifications_layout.addWidget(self.webhook_macro_stopped_checkbox)

        self.webhook_auto_sell_started_checkbox = QCheckBox("Auto-Sell Started")
        self.webhook_auto_sell_started_checkbox.setChecked(self.automation.webhook_auto_sell_started)
        self.webhook_auto_sell_started_checkbox.stateChanged.connect(self.update_webhook_auto_sell_started)
        self.webhook_auto_sell_started_checkbox.setStyleSheet(self.get_checkbox_style())
        notifications_layout.addWidget(self.webhook_auto_sell_started_checkbox)

        self.webhook_back_to_fishing_checkbox = QCheckBox("Back to Fishing")
        self.webhook_back_to_fishing_checkbox.setChecked(self.automation.webhook_back_to_fishing)
        self.webhook_back_to_fishing_checkbox.stateChanged.connect(self.update_webhook_back_to_fishing)
        self.webhook_back_to_fishing_checkbox.setStyleSheet(self.get_checkbox_style())
        notifications_layout.addWidget(self.webhook_back_to_fishing_checkbox)

        # System Events
        system_section = QLabel("System Events")
        system_section.setStyleSheet("color: #fd7e14; font-weight: 600; font-size: 12px; margin-top: 12px;")
        notifications_layout.addWidget(system_section)

        self.webhook_failsafe_triggered_checkbox = QCheckBox("Failsafe Triggered")
        self.webhook_failsafe_triggered_checkbox.setChecked(self.automation.webhook_failsafe_triggered)
        self.webhook_failsafe_triggered_checkbox.stateChanged.connect(self.update_webhook_failsafe_triggered)
        self.webhook_failsafe_triggered_checkbox.setStyleSheet(self.get_checkbox_style())
        notifications_layout.addWidget(self.webhook_failsafe_triggered_checkbox)

        self.webhook_error_notifications_checkbox = QCheckBox("Error Notifications")
        self.webhook_error_notifications_checkbox.setChecked(self.automation.webhook_error_notifications)
        self.webhook_error_notifications_checkbox.stateChanged.connect(self.update_webhook_error_notifications)
        self.webhook_error_notifications_checkbox.setStyleSheet(self.get_checkbox_style())
        notifications_layout.addWidget(self.webhook_error_notifications_checkbox)

        # Progress & Status Events
        progress_section = QLabel("Progress & Status Events")
        progress_section.setStyleSheet("color: #6f42c1; font-weight: 600; font-size: 12px; margin-top: 12px;")
        notifications_layout.addWidget(progress_section)

        self.webhook_phase_changes_checkbox = QCheckBox("Phase Changes (Can be spammy)")
        self.webhook_phase_changes_checkbox.setChecked(self.automation.webhook_phase_changes)
        self.webhook_phase_changes_checkbox.stateChanged.connect(self.update_webhook_phase_changes)
        self.webhook_phase_changes_checkbox.setStyleSheet(self.get_checkbox_style())
        notifications_layout.addWidget(self.webhook_phase_changes_checkbox)

        self.webhook_cycle_completion_checkbox = QCheckBox("Cycle Completions")
        self.webhook_cycle_completion_checkbox.setChecked(self.automation.webhook_cycle_completion)
        self.webhook_cycle_completion_checkbox.stateChanged.connect(self.update_webhook_cycle_completion)
        self.webhook_cycle_completion_checkbox.setStyleSheet(self.get_checkbox_style())
        notifications_layout.addWidget(self.webhook_cycle_completion_checkbox)

        scroll_layout.addWidget(notifications_group)

        # Fish Filtering Section
        filtering_group = QGroupBox("Fish Filtering")
        filtering_layout = QVBoxLayout(filtering_group)
        filtering_layout.setContentsMargins(12, 15, 12, 12)
        filtering_layout.setSpacing(8)

        filtering_info = QLabel("Choose which fish types to ignore in webhook notifications")
        filtering_info.setStyleSheet("color: #888888; font-size: 11px; margin-bottom: 8px;")
        filtering_layout.addWidget(filtering_info)

        # Add checkboxes for ignoring fish rarities
        self.ignore_common_checkbox = QCheckBox("Ignore Common Fish")
        self.ignore_common_checkbox.setChecked(self.automation.ignore_common_fish)
        self.ignore_common_checkbox.stateChanged.connect(self.update_ignore_common)
        self.ignore_common_checkbox.setStyleSheet(self.get_checkbox_style())
        filtering_layout.addWidget(self.ignore_common_checkbox)

        self.ignore_uncommon_checkbox = QCheckBox("Ignore Uncommon Fish")
        self.ignore_uncommon_checkbox.setChecked(self.automation.ignore_uncommon_fish)
        self.ignore_uncommon_checkbox.stateChanged.connect(self.update_ignore_uncommon)
        self.ignore_uncommon_checkbox.setStyleSheet(self.get_checkbox_style())
        filtering_layout.addWidget(self.ignore_uncommon_checkbox)

        self.ignore_rare_checkbox = QCheckBox("Ignore Rare Fish")
        self.ignore_rare_checkbox.setChecked(self.automation.ignore_rare_fish)
        self.ignore_rare_checkbox.stateChanged.connect(self.update_ignore_rare)
        self.ignore_rare_checkbox.setStyleSheet(self.get_checkbox_style())
        filtering_layout.addWidget(self.ignore_rare_checkbox)

        self.ignore_trash_checkbox = QCheckBox("Ignore Trash")
        self.ignore_trash_checkbox.setChecked(self.automation.ignore_trash)
        self.ignore_trash_checkbox.stateChanged.connect(self.update_ignore_trash)
        self.ignore_trash_checkbox.setStyleSheet(self.get_checkbox_style())
        filtering_layout.addWidget(self.ignore_trash_checkbox)

        scroll_layout.addWidget(filtering_group)

        # Webhook Control Buttons
        webhook_controls_group = QGroupBox("Webhook Controls")
        webhook_controls_layout = QVBoxLayout(webhook_controls_group)
        webhook_controls_layout.setContentsMargins(12, 15, 12, 12)
        webhook_controls_layout.setSpacing(8)

        controls_info = QLabel("Quick actions for webhook management")
        controls_info.setStyleSheet("color: #888888; font-size: 11px; margin-bottom: 8px;")
        webhook_controls_layout.addWidget(controls_info)

        controls_button_layout = QHBoxLayout()
        controls_button_layout.setSpacing(10)

        test_webhook_btn = QPushButton("Test Webhook")
        test_webhook_btn.clicked.connect(self.test_webhook)
        test_webhook_btn.setStyleSheet("""
            QPushButton {
                background-color: #17a2b8;
                color: white;
                font-weight: 600;
                padding: 8px 16px;
                font-size: 11px;
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
        controls_button_layout.addWidget(test_webhook_btn)

        enable_all_btn = QPushButton("Enable All")
        enable_all_btn.clicked.connect(self.enable_all_notifications)
        enable_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                font-weight: 600;
                padding: 8px 16px;
                font-size: 11px;
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
        controls_button_layout.addWidget(enable_all_btn)

        disable_all_btn = QPushButton("Disable All")
        disable_all_btn.clicked.connect(self.disable_all_notifications)
        disable_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #dc3545;
                color: white;
                font-weight: 600;
                padding: 8px 16px;
                font-size: 11px;
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
        controls_button_layout.addWidget(disable_all_btn)

        controls_button_layout.addStretch()
        webhook_controls_layout.addLayout(controls_button_layout)

        scroll_layout.addWidget(webhook_controls_group)

        # Add stretch to push content to top
        scroll_layout.addStretch()

        scroll_area.setWidget(scroll_widget)
        
        # Set layout for webhook tab
        tab_layout = QVBoxLayout(webhook_tab)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.addWidget(scroll_area)

    def get_checkbox_style(self):
        """Get consistent checkbox styling"""
        return """
            QCheckBox {
                color: #e0e0e0;
                font-size: 11px;
                margin: 3px 0;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 2px solid #555555;
                border-radius: 3px;
                background-color: #2d2d2d;
            }
            QCheckBox::indicator:checked {
                background-color: #4a9eff;
                border-color: #4a9eff;
            }
        """

    def create_settings_tab(self):
        """Create the Settings tab with failsafe, auto-sell, and other settings"""
        settings_tab = QWidget()
        self.tab_widget.addTab(settings_tab, "Settings")
        
        # Add scroll area to the settings tab
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setSpacing(15)
        scroll_layout.setContentsMargins(10, 10, 10, 10)

        # Failsafe Settings
        failsafe_group = QGroupBox("Failsafe System")
        failsafe_layout = QVBoxLayout(failsafe_group)
        failsafe_layout.setContentsMargins(12, 15, 12, 12)
        failsafe_layout.setSpacing(8)

        failsafe_info = QLabel("Prevents macro from getting soft-locked")
        failsafe_info.setStyleSheet("color: #888888; font-size: 11px; margin-bottom: 6px;")
        failsafe_layout.addWidget(failsafe_info)

        # Failsafe enabled checkbox
        self.failsafe_checkbox = QCheckBox("Enable Failsafe System")
        self.failsafe_checkbox.setChecked(self.automation.failsafe_enabled)
        self.failsafe_checkbox.stateChanged.connect(self.update_failsafe_enabled)
        self.failsafe_checkbox.setStyleSheet("""
            QCheckBox {
                color: #e0e0e0;
                font-size: 11px;
                margin: 3px 0;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 2px solid #555555;
                border-radius: 3px;
                background-color: #2d2d2d;
            }
            QCheckBox::indicator:checked {
                background-color: #4a9eff;
                border-color: #4a9eff;
            }
        """)
        failsafe_layout.addWidget(self.failsafe_checkbox)

        # Failsafe timeout setting
        timeout_layout = QHBoxLayout()
        timeout_layout.setSpacing(10)

        timeout_label = QLabel("Timeout (seconds):")
        timeout_label.setStyleSheet("color: #e0e0e0; font-size: 11px;")
        timeout_layout.addWidget(timeout_label)

        self.failsafe_timeout_spinbox = QSpinBox()
        self.failsafe_timeout_spinbox.setRange(20, 60)  # 20 to 60 seconds (minimum 20s enforced)
        self.failsafe_timeout_spinbox.setValue(self.automation.failsafe_timeout)
        self.failsafe_timeout_spinbox.setSuffix(" sec")
        self.failsafe_timeout_spinbox.valueChanged.connect(self.update_failsafe_timeout)
        self.failsafe_timeout_spinbox.setStyleSheet("""
            QSpinBox {
                background-color: #2d2d2d;
                color: #e0e0e0;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 11px;
                min-width: 80px;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                background-color: #404040;
                border: 1px solid #555555;
                width: 16px;
            }
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {
                background-color: #4a9eff;
            }
        """)
        timeout_layout.addWidget(self.failsafe_timeout_spinbox)
        timeout_layout.addStretch()

        failsafe_layout.addLayout(timeout_layout)
        scroll_layout.addWidget(failsafe_group)

        # Auto-sell Settings
        auto_sell_group = QGroupBox("Auto-Sell System")
        auto_sell_layout = QVBoxLayout(auto_sell_group)
        auto_sell_layout.setContentsMargins(12, 15, 12, 12)
        auto_sell_layout.setSpacing(8)

        auto_sell_info = QLabel("Automatically sells caught fish when enabled")
        auto_sell_info.setStyleSheet("color: #888888; font-size: 11px; margin-bottom: 6px;")
        auto_sell_layout.addWidget(auto_sell_info)

        # Auto-sell enabled checkbox
        self.auto_sell_checkbox = QCheckBox("Enable Auto-Sell")
        self.auto_sell_checkbox.setChecked(self.automation.auto_sell_enabled)
        self.auto_sell_checkbox.stateChanged.connect(self.update_auto_sell_enabled)
        self.auto_sell_checkbox.setStyleSheet("""
            QCheckBox {
                color: #e0e0e0;
                font-size: 11px;
                margin: 3px 0;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 2px solid #555555;
                border-radius: 3px;
                background-color: #2d2d2d;
            }
            QCheckBox::indicator:checked {
                background-color: #28a745;
                border-color: #28a745;
            }
        """)
        auto_sell_layout.addWidget(self.auto_sell_checkbox)

        # Fish count until auto-sell setting
        fish_count_layout = QHBoxLayout()
        fish_count_layout.setSpacing(10)

        fish_count_label = QLabel("Fish Caught Until Auto Sell:")
        fish_count_label.setStyleSheet("color: #e0e0e0; font-size: 11px;")
        fish_count_layout.addWidget(fish_count_label)

        self.fish_count_spinbox = QSpinBox()
        self.fish_count_spinbox.setRange(1, 100)  # 1 to 100 fish
        self.fish_count_spinbox.setValue(getattr(self.automation, 'fish_count_until_auto_sell', 10))  # Default to 10
        self.fish_count_spinbox.setSuffix(" fish")
        self.fish_count_spinbox.valueChanged.connect(self.update_fish_count_until_auto_sell)
        self.fish_count_spinbox.setStyleSheet("""
            QSpinBox {
                background-color: #2d2d2d;
                color: #e0e0e0;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 11px;
                min-width: 80px;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                background-color: #404040;
                border: 1px solid #555555;
                width: 16px;
            }
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {
                background-color: #4a9eff;
            }
        """)
        fish_count_layout.addWidget(self.fish_count_spinbox)
        fish_count_layout.addStretch()

        auto_sell_layout.addLayout(fish_count_layout)
        scroll_layout.addWidget(auto_sell_group)

        # Pathing Settings
        pathing_group = QGroupBox("Pathing Settings")
        pathing_layout = QVBoxLayout(pathing_group)
        pathing_layout.setContentsMargins(12, 15, 12, 12)
        pathing_layout.setSpacing(8)

        pathing_info = QLabel("For players without the VIP gamepass - disables navigation and auto-sell features")
        pathing_info.setStyleSheet("color: #888888; font-size: 11px; margin-bottom: 6px;")
        pathing_layout.addWidget(pathing_info)

        # Disable all pathing checkbox
        self.disable_pathing_checkbox = QCheckBox("Disable All Pathing (No VIP Gamepass)")
        self.disable_pathing_checkbox.setChecked(self.automation.disable_all_pathing)
        self.disable_pathing_checkbox.stateChanged.connect(self.update_disable_all_pathing)
        self.disable_pathing_checkbox.setStyleSheet("""
            QCheckBox {
                color: #e0e0e0;
                font-size: 11px;
                margin: 3px 0;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 2px solid #555555;
                border-radius: 3px;
                background-color: #2d2d2d;
            }
            QCheckBox::indicator:checked {
                background-color: #ffc107;
                border-color: #ffc107;
            }
        """)
        pathing_layout.addWidget(self.disable_pathing_checkbox)

        # Warning message
        pathing_warning = QLabel("⚠️ When enabled: Only basic fishing will work, no auto-sell or navigation")
        pathing_warning.setWordWrap(True)
        pathing_warning.setStyleSheet("""
            QLabel {
                color: #856404;
                background-color: #fff3cd;
                border: 1px solid #ffeaa7;
                border-radius: 4px;
                padding: 8px;
                font-size: 10px;
                margin-top: 5px;
            }
        """)
        pathing_layout.addWidget(pathing_warning)
        scroll_layout.addWidget(pathing_group)

        # Mouse Delay Settings
        mouse_delay_group = QGroupBox("Mouse Delay Settings")
        mouse_delay_layout = QVBoxLayout(mouse_delay_group)
        mouse_delay_layout.setContentsMargins(12, 15, 12, 12)
        mouse_delay_layout.setSpacing(8)

        mouse_delay_info = QLabel("Add extra delay after mouse clicks to prevent issues with fast clicking")
        mouse_delay_info.setStyleSheet("color: #888888; font-size: 11px; margin-bottom: 6px;")
        mouse_delay_layout.addWidget(mouse_delay_info)

        # Mouse delay checkbox
        self.mouse_delay_checkbox = QCheckBox("Enable Additional Mouse Delay")
        self.mouse_delay_checkbox.setChecked(self.automation.mouse_delay_enabled)
        self.mouse_delay_checkbox.stateChanged.connect(self.update_mouse_delay_enabled)
        self.mouse_delay_checkbox.setStyleSheet("""
            QCheckBox {
                color: #e0e0e0;
                font-size: 11px;
                margin: 3px 0;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 2px solid #555555;
                border-radius: 3px;
                background-color: #2d2d2d;
            }
            QCheckBox::indicator:checked {
                background-color: #4a9eff;
                border-color: #4a9eff;
            }
        """)
        mouse_delay_layout.addWidget(self.mouse_delay_checkbox)

        # Mouse delay amount setting
        delay_amount_layout = QHBoxLayout()
        delay_amount_layout.setSpacing(10)

        delay_amount_label = QLabel("Delay Amount (ms):")
        delay_amount_label.setStyleSheet("color: #e0e0e0; font-size: 11px;")
        delay_amount_layout.addWidget(delay_amount_label)

        self.mouse_delay_spinbox = QSpinBox()
        self.mouse_delay_spinbox.setRange(0, 2000)  # 0 to 2000ms
        self.mouse_delay_spinbox.setValue(self.automation.mouse_delay_ms)
        self.mouse_delay_spinbox.setSuffix(" ms")
        self.mouse_delay_spinbox.valueChanged.connect(self.update_mouse_delay_amount)
        self.mouse_delay_spinbox.setStyleSheet("""
            QSpinBox {
                background-color: #2d2d2d;
                color: #e0e0e0;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 11px;
                min-width: 80px;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                background-color: #404040;
                border: 1px solid #555555;
                width: 16px;
            }
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {
                background-color: #4a9eff;
            }
        """)
        delay_amount_layout.addWidget(self.mouse_delay_spinbox)
        delay_amount_layout.addStretch()

        mouse_delay_layout.addLayout(delay_amount_layout)
        scroll_layout.addWidget(mouse_delay_group)

        # Control buttons and save info
        settings_info_layout = QVBoxLayout()
        settings_info_layout.setSpacing(10)

        auto_save_label = QLabel("Settings are automatically saved to fishscopeconfig.json")
        auto_save_label.setStyleSheet("color: #888888; font-size: 12px;")
        auto_save_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        settings_info_layout.addWidget(auto_save_label)

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

        save_config_btn = QPushButton("Save Config")
        save_config_btn.clicked.connect(self.automation.save_calibration)
        save_config_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                font-weight: 600;
                padding: 8px 16px;
                font-size: 12px;
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
        settings_buttons_layout.addWidget(save_config_btn)
        settings_buttons_layout.addStretch()

        settings_info_layout.addLayout(settings_buttons_layout)
        scroll_layout.addLayout(settings_info_layout)

        # Add stretch to push content to top
        scroll_layout.addStretch()

        scroll_area.setWidget(scroll_widget)
        
        # Set layout for settings tab
        tab_layout = QVBoxLayout(settings_tab)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.addWidget(scroll_area)





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

        # Update all coordinate labels in the UI (only if they exist)
        if hasattr(self, 'coord_labels_widgets'):
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
            # Reset to default coordinates based on detected resolution
            self.automation.current_resolution = self.automation.detect_resolution()
            self.automation.coordinates = self.automation.get_coordinates_for_resolution(self.automation.current_resolution)

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
        if hasattr(self, 'coord_labels_widgets') and hasattr(self, 'coord_labels'):
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

    # Show first launch warning about Custom Fonts (1 second delay to ensure UI is ready)
    QTimer.singleShot(1000, ui.show_first_launch_warning)

    # Check for updates on startup (silent mode - only show if update available)
    QTimer.singleShot(2000, lambda: ui.auto_updater.check_for_updates(silent=True))

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
