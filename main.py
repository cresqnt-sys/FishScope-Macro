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
                            QMessageBox, QGroupBox, QComboBox, QCheckBox, QLineEdit, QSpinBox)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject, QPoint
from PyQt6.QtGui import QFont, QCursor, QPainter, QPen, QColor, QIcon, QLinearGradient, QBrush
from updater import AutoUpdater
import requests
# Import easyocr and numpy only when needed for faster startup
import re
from datetime import datetime, timezone
from itertools import product

try:
    import win32gui
    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False

pyautogui.FAILSAFE = False

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
        self.config_file = "fishscopeconfig.json"
        self.first_loop = True
        self.cycle_count = 0
        self.start_time = None

        # Mouse delay settings
        self.mouse_delay_enabled = False
        self.mouse_delay_ms = 100  # Default 100ms additional delay

        # Failsafe settings
        self.failsafe_enabled = True  # Default enabled
        self.failsafe_timeout = 20  # 20 seconds timeout

        # Bar game settings
        self.bar_game_tolerance = 5  # Default tolerance for bar game

        # First launch tracking
        self.first_launch_warning_shown = False

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

        # Initialize EasyOCR reader (background loading after UI)
        self.ocr_reader = None
        self.ocr_initialized = False
        self.ocr_loading = False

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
                'shaded_area': (505, 506)
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
                'shaded_area': (951, 731)
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
                'shaded_area': (951, 731)
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
                'shaded_area': (945, 691)
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
                'shaded_area': (1271, 1008)
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
                'shaded_area': (1904, 1540)
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
                'shaded_area': (1898, 1518)
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
                'shaded_area': (1891, 1498)
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
                'shaded_area': (1898, 1460)
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
                'shaded_area': (946, 765)
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
                'shaded_area': (1271, 1008)
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
                'shaded_area': (664, 531)
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
                'first_launch_warning_shown': self.first_launch_warning_shown,
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
                        self.failsafe_timeout = int(saved_data['failsafe_timeout'])

                    # Load enhanced bar game settings
                    if 'bar_game_tolerance' in saved_data:
                        self.bar_game_tolerance = int(saved_data['bar_game_tolerance'])

                    # Load first launch warning flag
                    if 'first_launch_warning_shown' in saved_data:
                        self.first_launch_warning_shown = bool(saved_data['first_launch_warning_shown'])
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
        return pyautogui.position()

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

    def init_ocr_reader_background(self):
        """Initialize EasyOCR reader in background thread"""
        if self.ocr_initialized or self.ocr_loading:
            return

        self.ocr_loading = True

        def _init_ocr():
            try:
                # Import heavy libraries only when needed
                import easyocr
                import torch

                # Check if CUDA is available
                gpu_available = torch.cuda.is_available()

                # Initialize EasyOCR with appropriate settings
                if gpu_available:
                    self.ocr_reader = easyocr.Reader(['en'], gpu=True)
                else:
                    self.ocr_reader = easyocr.Reader(['en'], gpu=False)
                self.ocr_initialized = True
            except Exception as e:
                print(f"OCR initialization failed: {e}")
                self.ocr_reader = None
                self.ocr_initialized = False
            finally:
                self.ocr_loading = False

        # Start OCR initialization in background thread
        ocr_thread = threading.Thread(target=_init_ocr, daemon=True)
        ocr_thread.start()

    def wait_for_ocr_ready(self, timeout=30):
        """Wait for OCR to be ready, with timeout"""
        import time
        start_time = time.time()
        while not self.ocr_initialized and self.ocr_loading:
            if time.time() - start_time > timeout:
                print("OCR initialization timeout - proceeding without OCR")
                return False
            time.sleep(0.1)
        return self.ocr_initialized

    def load_fish_data(self):
        """Load fish data from JSON file"""
        try:
            with open('fish-data.json', 'r') as f:
                self.fish_data = json.load(f)
            print(f"Loaded {len(self.fish_data)} fish entries")
        except FileNotFoundError:
            print("Fish data file not found. Using empty dictionary.")
            self.fish_data = {}

    def extract_fish_name(self):
        # Wait for OCR to be ready if it's still loading
        if not self.ocr_initialized and self.ocr_loading:
            if not self.wait_for_ocr_ready():
                return "Unknown Fish", None

        if not self.ocr_reader:
            return "Unknown Fish", None

        # Get the fish description area coordinates
        if 'fish_caught_desc' not in self.coordinates:
            print("Fish caught description coordinates not set")
            return "Unknown Fish", None

        desc_x1, desc_y1, desc_x2, desc_y2 = self.coordinates['fish_caught_desc']
        screenshot = ImageGrab.grab(bbox=(desc_x1, desc_y1, desc_x2, desc_y2))

        try:
            # Convert PIL image to numpy array for EasyOCR
            import numpy as np
            screenshot_array = np.array(screenshot)

            # Use EasyOCR to extract text
            results = self.ocr_reader.readtext(screenshot_array)
            fish_description = ' '.join([result[1] for result in results])
            print(f"Raw OCR text: {fish_description}")

            fish_description = self.clean_ocr_text(fish_description)
            print(f"Cleaned OCR text: {fish_description}")

            mutations = ["Ruffled", "Crusted", "Slick", "Rough", "Charred", "Shimmering", "Tainted", "Hollow", "Lucid"]
            fish_gone = ["thefishisgone.", "thefishisgone...", "the fish is gone.", "thefishisgone.,", "the fish is gone..."]

            fish_name_match = re.search(r"you'?ve got (.+?)(?:!|\.\.\.)", fish_description)

            if fish_name_match:
                full_fish_name = fish_name_match.group(1).strip(" .!").strip().title()

                full_fish_name = correct_name(full_fish_name, self.fish_data.keys())

                mutation = None
                fish_name = full_fish_name

                for mut_candidate in mutations:
                    variants = generate_ao_variants(mut_candidate)
                    for variant in variants:
                        if variant.lower() in full_fish_name.lower():
                            mutation = mut_candidate.title()
                            fish_name = full_fish_name.lower().replace(variant.lower(), '').strip().title()
                            break
                    if mutation:
                        break

                if not mutation:
                    for mut_candidate in mutations:
                        dist = levenshtein(mut_candidate.lower(), full_fish_name.lower().split()[0])
                        if dist <= 2:
                            mutation = mut_candidate.title()
                            fish_name = full_fish_name[len(mut_candidate):].strip().title()
                            break

                if not mutation:
                    fish_name = full_fish_name

                return fish_name, mutation
            else:
                for gone in fish_gone:
                    if gone in fish_description:
                        print("Fishing Failed")
                        return "Fishing Failed", None
                print("Regex failed. Raw OCR text:", fish_description)
                return "Unknown Fish", None

        except Exception as e:
            print(f"OCR extraction failed: {e}")
            return "Unknown Fish", None

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
            rarity = self.fish_data[fish_name]['rarity']
            color = self.get_rarity_color(rarity)
            print(f"Fish '{fish_name}' found in database with rarity: {rarity}")
        else:
            rarity = "Trash"
            color = 0x8B4513  # Default brown color
            print(f"Fish '{fish_name}' not found in database, marking as trash. Available fish: {list(self.fish_data.keys())}")

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

        title = "Fish Caught!" if rarity != "Trash" else "You snagged some trash!"
        name = "Fish" if rarity != "Trash" else "Item"

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
            response = requests.post(self.webhook_url, json=data)
            response.raise_for_status()
            print(f"Webhook sent successfully: {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"Failed to send webhook: {e}")
            if hasattr(response, 'text'):
                print(f"Response content: {response.text}")
            print(f"Request data: {json.dumps(data, indent=2)}")

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
            response = requests.post(self.webhook_url, json=data)
            response.raise_for_status()
            print(f"Webhook sent successfully: {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"Failed to send webhook: {e}")
            if hasattr(response, 'text'):
                print(f"Response content: {response.text}")
            print(f"Request data: {json.dumps(data, indent=2)}")

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

    def execute_failsafe(self):
        """Execute failsafe procedure: click X button, confirm sale, then click fish button"""
        print("Failsafe activated - attempting to recover from soft lock...")

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

    def mouse_automation_loop(self):
        """Main automation loop with faster clicking for reel-in and improved error handling"""
        try:
            while self.running and self.toggle:
                if not self.toggle:
                    break

                try:
                    # Move to fish button and click (2x faster)
                    fish_x, fish_y = self.coordinates['fish_button']
                    autoit.mouse_move(fish_x, fish_y, 3)
                    time.sleep(0.15)  # Reduced from 0.3
                    autoit.mouse_click("left")
                    self.apply_mouse_delay()  # Apply additional delay if enabled
                    time.sleep(0.15)  # Reduced from 0.3

                    # Auto-sell (skip on first loop, 2x faster)
                    if not self.first_loop:
                        # Click first item
                        item_x, item_y = self.coordinates['first_item']
                        autoit.mouse_move(item_x, item_y, 3)
                        time.sleep(0.15)  # Reduced from 0.3
                        autoit.mouse_click("left")
                        self.apply_mouse_delay()  # Apply additional delay if enabled
                        time.sleep(0.15)  # Reduced from 0.3

                        # Click sell button
                        sell_x, sell_y = self.coordinates['sell_button']
                        autoit.mouse_move(sell_x, sell_y, 3)
                        time.sleep(0.15)  # Reduced from 0.3
                        autoit.mouse_click("left")
                        self.apply_mouse_delay()  # Apply additional delay if enabled
                        time.sleep(0.15)  # Reduced from 0.3

                        # Click confirm button
                        confirm_x, confirm_y = self.coordinates['confirm_button']
                        autoit.mouse_move(confirm_x, confirm_y, 3)
                        time.sleep(0.15)  # Reduced from 0.3
                        autoit.mouse_click("left")
                        self.apply_mouse_delay()  # Apply additional delay if enabled
                        time.sleep(0.15)  # Reduced from 0.3
                    else:
                        self.first_loop = False

                    bar_color = None

                    # Check for white pixel (faster detection) with failsafe timeout
                    white_diamond_start_time = time.time()
                    bar_color = None

                    while True:
                        if not self.toggle:
                            return

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
                        if self.failsafe_enabled and (time.time() - white_diamond_start_time) > self.failsafe_timeout:
                            print(f"Failsafe triggered: No white diamond detected within {self.failsafe_timeout} seconds")
                            self.execute_failsafe()
                            # Reset the timer and continue white diamond detection (fish button already clicked in failsafe)
                            white_diamond_start_time = time.time()
                            continue

                        time.sleep(0.05)  # Reduced from 0.1 for faster detection

                    start_time = time.time()
                    loop_count = 0
                    bar_was_present = True  # Track if bar was present in previous iteration

                    while True:
                        if not self.toggle:
                            break
                        if (time.time() - start_time) > 9:
                            break

                        loop_count += 1
                        if loop_count % 50 == 0:
                            completed_x, completed_y = self.coordinates['completed_border']
                            if self.pixel_search_white(completed_x, completed_y, tolerance=15):
                                time.sleep(1.0)
                                break

                        search_area = self.coordinates['reel_bar']
                        found_pos = self.pixel_search_color(*search_area, bar_color, tolerance=5)

                        if found_pos is None:
                            pyautogui.click()
                            # If bar was present before but now isn't, click one more time
                            if bar_was_present:
                                time.sleep(0.01)  # Small delay between clicks
                                pyautogui.click()
                            bar_was_present = False
                        else:
                            bar_was_present = True

                    # Extract fish name using OCR and send webhook
                    fish_name, mutation = self.extract_fish_name()
                    self.send_webhook_message(fish_name, mutation)

                    time.sleep(0.3)  # Wait a bit for OCR processing

                    # Close the catch screen (keep original timing for X button)
                    close_x, close_y = self.coordinates['close_button']
                    autoit.mouse_move(close_x, close_y, 3)
                    time.sleep(0.7)  # Keep original timing for X button
                    autoit.mouse_click("left")
                    self.apply_mouse_delay()  # Apply additional delay if enabled
                    time.sleep(0.15)  # Reduced from 0.3

                    self.cycle_count += 1

                except Exception as e:
                    print(f"Error in automation cycle: {e}")
                    # Continue to next cycle instead of crashing
                    time.sleep(1)  # Brief pause before retrying
                    continue

        except Exception as e:
            print(f"Critical error in automation loop: {e}")
            print("Automation loop terminated due to error")
        finally:
            print("Automation loop ended")

    def start_automation(self):
        if not self.toggle:
            self.toggle = True
            self.running = True
            self.first_loop = True
            self.cycle_count = 0
            self.start_time = time.time()
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
            self.send_webhook_message2(
                "FishScope Macro Started",
                "FischScope has been started.",
                color=0x28a745  # Green color
            )

    def stop_automation(self):
        """Stop automation with improved thread handling and error recovery"""
        print("Stop automation requested...")

        # Set stop flags immediately
        self.toggle = False
        self.running = False
        self.first_loop = True

        # Send webhook notification (non-blocking)
        try:
            if self.webhook_url:  # Only send if webhook is configured
                self.send_webhook_message2(
                    "FishScope Macro Stopped",
                    "FishScope has been stopped.",
                    color=0xdc3545  # Red color
                )
        except Exception as e:
            print(f"Warning: Failed to send stop webhook: {e}")

        # Handle thread termination with better timeout and error handling
        if self.thread and self.thread.is_alive():
            print("Waiting for automation thread to stop...")
            try:
                # Give thread more time to stop gracefully
                self.thread.join(timeout=3)

                # Check if thread is still alive after timeout
                if self.thread.is_alive():
                    print("Warning: Automation thread did not stop gracefully within timeout")
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
            'sell_button': 'Sell Button - Click to sell item',
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

        # Initialize auto updater
        self.auto_updater = AutoUpdater(self)

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
                'shaded_area': (505, 506)
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
                'shaded_area': (951, 731)
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
        self.setFixedSize(600, 600)

        # Set application icon
        if os.path.exists("icon.ico"):
            self.setWindowIcon(QIcon("icon.ico"))

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 15, 15, 15)

        # Add a scroll area to the main layout
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setSpacing(10)
        scroll_layout.setContentsMargins(0, 0, 0, 0)

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

        scroll_layout.addLayout(header_layout)

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
        scroll_layout.addWidget(control_group)

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
        scroll_layout.addWidget(premade_group)

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

        # Add checkboxes for ignoring fish rarities
        self.ignore_common_checkbox = QCheckBox("Ignore Common Fish")
        self.ignore_common_checkbox.setChecked(self.automation.ignore_common_fish)
        self.ignore_common_checkbox.stateChanged.connect(self.update_ignore_common)
        self.ignore_common_checkbox.setStyleSheet("""
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
        """)
        webhook_layout.addWidget(self.ignore_common_checkbox)

        self.ignore_uncommon_checkbox = QCheckBox("Ignore Uncommon Fish")
        self.ignore_uncommon_checkbox.setChecked(self.automation.ignore_uncommon_fish)
        self.ignore_uncommon_checkbox.stateChanged.connect(self.update_ignore_uncommon)
        self.ignore_uncommon_checkbox.setStyleSheet("""
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
        """)
        webhook_layout.addWidget(self.ignore_uncommon_checkbox)

        self.ignore_rare_checkbox = QCheckBox("Ignore Rare Fish")
        self.ignore_rare_checkbox.setChecked(self.automation.ignore_rare_fish)
        self.ignore_rare_checkbox.stateChanged.connect(self.update_ignore_rare)
        self.ignore_rare_checkbox.setStyleSheet("""
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
        """)
        webhook_layout.addWidget(self.ignore_rare_checkbox)

        self.ignore_trash_checkbox = QCheckBox("Ignore Trash")
        self.ignore_trash_checkbox.setChecked(self.automation.ignore_trash)
        self.ignore_trash_checkbox.stateChanged.connect(self.update_ignore_trash)
        self.ignore_trash_checkbox.setStyleSheet("""
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
        """)
        webhook_layout.addWidget(self.ignore_trash_checkbox)

        # Add fish caught description calibration to webhook section
        webhook_layout.addWidget(QLabel(""))  # Spacer

        fish_desc_label = QLabel("Fish Caught Description Calibration:")
        fish_desc_label.setStyleSheet("color: #e0e0e0; font-weight: 500; margin-top: 10px;")
        webhook_layout.addWidget(fish_desc_label)

        fish_desc_info = QLabel("Calibrate the area where fish descriptions appear for OCR extraction")
        fish_desc_info.setStyleSheet("color: #888888; font-size: 11px; margin-bottom: 6px;")
        webhook_layout.addWidget(fish_desc_info)

        # Create calibration row for fish_caught_desc
        self.create_fish_desc_calibration_row(webhook_layout)

        scroll_layout.addWidget(webhook_group)

        # Settings Section - More compact
        settings_group = QGroupBox("Settings")
        settings_layout = QVBoxLayout(settings_group)
        settings_layout.setContentsMargins(12, 15, 12, 12)
        settings_layout.setSpacing(8)

        # Failsafe Settings (at the top)
        failsafe_layout = QVBoxLayout()
        failsafe_layout.setSpacing(8)

        failsafe_label = QLabel("Failsafe System:")
        failsafe_label.setStyleSheet("color: #e0e0e0; font-weight: 500; font-size: 12px;")
        failsafe_layout.addWidget(failsafe_label)

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
        self.failsafe_timeout_spinbox.setRange(5, 60)  # 5 to 60 seconds
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
        settings_layout.addLayout(failsafe_layout)

        # Spacer between failsafe and advanced calibrations
        settings_layout.addWidget(QLabel(""))

        # Advanced Calibrations button
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

        settings_layout.addLayout(advanced_calib_layout)

        # Mouse Delay Settings
        mouse_delay_layout = QVBoxLayout()
        mouse_delay_layout.setSpacing(8)

        mouse_delay_label = QLabel("Mouse Delay Settings:")
        mouse_delay_label.setStyleSheet("color: #e0e0e0; font-weight: 500; font-size: 12px; margin-top: 10px;")
        mouse_delay_layout.addWidget(mouse_delay_label)

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
        settings_layout.addLayout(mouse_delay_layout)

        # Spacer
        settings_layout.addWidget(QLabel(""))

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
        scroll_layout.addWidget(settings_group)

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

        idea_label2 = QLabel("Webhook System: vex")
        idea_label2.setStyleSheet("color: #888888; font-size: 11px;")
        footer_layout.addWidget(idea_label2)

        scroll_layout.addLayout(footer_layout)

        scroll_area.setWidget(scroll_widget)
        main_layout.addWidget(scroll_area)

        # Check display scale after UI is set up
        QTimer.singleShot(1000, self.check_display_scale)





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

    # Initialize OCR in background after UI is shown (500ms delay)
    QTimer.singleShot(500, automation.init_ocr_reader_background)

    # Check for updates on startup (silent mode - only show if update available)
    QTimer.singleShot(2000, lambda: ui.auto_updater.check_for_updates(silent=True))

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
