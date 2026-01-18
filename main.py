import time 
import threading 
import keyboard 
from PIL import ImageGrab 
import ctypes 
import autoit 
import json 
import os 
import sys 
import concurrent .futures 
from PyQt6 .QtWidgets import QApplication ,QMainWindow ,QVBoxLayout ,QHBoxLayout ,QWidget ,QPushButton ,QLabel ,QFrame ,QScrollArea ,QMessageBox ,QGroupBox ,QComboBox ,QCheckBox ,QLineEdit ,QSpinBox ,QTabWidget ,QDialog ,QRadioButton ,QButtonGroup 
from PyQt6 .QtCore import Qt ,QTimer ,pyqtSignal ,QObject ,QPoint ,QUrl 
from PyQt6 .QtGui import QFont ,QCursor ,QPainter ,QPen ,QColor ,QIcon ,QLinearGradient ,QBrush ,QDesktopServices ,QPixmap 
from updater import AutoUpdater 
from auto_sell import AutoSellManager 
from reconnect import AutoReconnectManager 
from calibration_manager import CalibrationManager 
import requests 
import re 
from datetime import datetime ,timezone 
from itertools import product 
import pytesseract 
import shutil 
import cv2 
from fuzzywuzzy import process 
import logging 
from pathlib import Path 
import webbrowser 

def resource_path (relative_path ):
    try :
        base_path =sys ._MEIPASS 
    except Exception :
        base_path =os .path .abspath ('.')
    return os .path .join (base_path ,relative_path )

def setup_tesseract ():
    try :
        if shutil .which ('tesseract'):
            return True 
    except Exception :
        pass 
    if os .name =='nt':
        common_paths =['C:\\Program Files\\Tesseract-OCR\\tesseract.exe','C:\\Program Files (x86)\\Tesseract-OCR\\tesseract.exe',os .path .expanduser ('~\\AppData\\Local\\Programs\\Tesseract-OCR\\tesseract.exe'),'C:\\tesseract\\tesseract.exe','D:\\Program Files\\Tesseract-OCR\\tesseract.exe','D:\\Program Files (x86)\\Tesseract-OCR\\tesseract.exe']
    for path in common_paths :
        if os .path .exists (path ):
            pytesseract .pytesseract .tesseract_cmd =path 
            try :
                from PIL import Image 
                import numpy as np 
                test_img =Image .new ('RGB',(100 ,30 ),color ='white')
                pytesseract .image_to_string (test_img )
                return True 
            except Exception as e :
                continue 
    try :
        import glob 
        program_files_paths =['C:\\Program Files\\*esseract*\\tesseract.exe','C:\\Program Files (x86)\\*esseract*\\tesseract.exe']
        for pattern in program_files_paths :
            matches =glob .glob (pattern )
            for match in matches :
                if os .path .exists (match ):
                    pytesseract .pytesseract .tesseract_cmd =match 
                    try :
                        from PIL import Image 
                        test_img =Image .new ('RGB',(100 ,30 ),color ='white')
                        pytesseract .image_to_string (test_img )
                        return True 
                    except Exception as e :
                        continue 
    except Exception :
        pass 
    print ('Warning: Tesseract OCR not found in PATH or common installation directories.')
    print ("Please install Tesseract OCR or ensure it's in your PATH.")
    print ('Download from: https://github.com/UB-Mannheim/tesseract/wiki')
    return False 
setup_tesseract ()
try :
    from autoalign import auto_align_camera 
    from fishinglocation import run_macro as run_fishing_location_macro ,macro_actions as fishing_location_actions 
    from shoppath import run_macro as run_shop_path_macro ,macro_actions as shop_path_actions 
    from nonvipfishinglocation import run_macro as run_nonvip_fishing_location_macro ,macro_actions as nonvip_fishing_location_actions 
    from nonvipshoppath import run_macro as run_nonvip_shop_path_macro ,macro_actions as nonvip_shop_path_actions 
    EXTERNAL_SCRIPTS_AVAILABLE =True 
except ImportError as e :
    EXTERNAL_SCRIPTS_AVAILABLE =False 
    print (f'Warning: Could not import external macro scripts: {e }')
try :
    import win32gui 
    WIN32_AVAILABLE =True 
except ImportError :
    WIN32_AVAILABLE =False 

def generate_ao_variants (name ):
    ambiguous_positions =[i for i ,c in enumerate (name .lower ())if c in ('a','o')]
    variants =[]
    options =[('a','o')]*len (ambiguous_positions )
    for combo in product (*options ):
        name_list =list (name .lower ())
        for pos ,char in zip (ambiguous_positions ,combo ):
            name_list [pos ]=char 
        variant =''.join (name_list )
        variants .append (variant .title ())
    return variants 

def correct_name (raw_name ,known_names ,max_distance =2 ):
    raw_name =raw_name .title ()
    for variant in generate_ao_variants (raw_name ):
        if variant in known_names :
            return variant 
    best_match =None 
    best_distance =max_distance +1 
    for name in known_names :
        dist =levenshtein (raw_name .lower (),name .lower ())
        if dist <best_distance :
            best_distance =dist 
            best_match =name 
    return best_match if best_distance <=max_distance else raw_name 

def levenshtein (s1 ,s2 ):
    if len (s1 )<len (s2 ):
        return levenshtein (s2 ,s1 )
    if len (s2 )==0 :
        return len (s1 )
    previous_row =list (range (len (s2 )+1 ))
    for i ,c1 in enumerate (s1 ):
        current_row =[i +1 ]
        for j ,c2 in enumerate (s2 ):
            insertions =previous_row [j +1 ]+1 
            deletions =current_row [j ]+1 
            substitutions =previous_row [j ]+(c1 !=c2 )
            current_row .append (min (insertions ,deletions ,substitutions ))
        previous_row =current_row 
    return previous_row [-1 ]

class MouseAutomation :

    def __init__ (self ):
        self .toggle =False 
        self .running =False 
        self .thread =None 
        self .emergency_stop_event =threading .Event ()
        self .config_file =os .path .join (os .getcwd (),'fishscopeconfig.json')
        self .first_loop =True 
        self .cycle_count =0 
        self .start_time =None 
        self .mouse_delay_enabled =False 
        self .mouse_delay_ms =100 
        self .failsafe_enabled =True 
        self .failsafe_timeout =20 
        self .failsafe_consecutive_count =0 
        self .failsafe_reconnect_threshold =5 
        self .failsafe_reconnect_enabled =True 
        self .bar_game_tolerance =5 
        self .auto_sell_enabled =True 
        self .auto_sell_configuration ='Sell All (Recommended)'
        self .fish_count_until_auto_sell =10 
        self .current_fish_count =0 
        self .auto_reconnect_manager =AutoReconnectManager (self )
        self .calibration_manager =CalibrationManager (verbose =False )
        try :
            success ,message ,calibration_data =self .calibration_manager .update_calibrations ()
        except Exception as e :
            pass 
        self .automation_phase ='initialization'
        self .in_sell_cycle =False 
        self .external_script_running =False 
        self .first_launch_warning_shown =False 
        self .use_vip_paths =True 
        self .screen_width ,self .screen_height =self .get_screen_dimensions ()
        self .current_resolution =self .detect_resolution ()
        self .coordinates ={'fish_button':(851 ,802 ),'white_diamond':(1176 ,805 ),'reel_bar':(757 ,728 ,1163 ,750 ),'completed_border':(1133 ,744 ),'close_button':(1108 ,337 ),'fish_caught_desc':(700 ,540 ,1035 ,685 ),'first_item':(830 ,409 ),'sell_button':(588 ,775 ),'confirm_button':(797 ,613 ),'mouse_idle_position':(999 ,190 ),'shaded_area':(951 ,731 ),'sell_fish_shop':(900 ,600 ),'collection_button':(950 ,650 ),'exit_collections':(1000 ,700 ),'exit_fish_shop':(1050 ,750 )}
        self .webhook_url =''
        self .ignore_common_fish =False 
        self .ignore_uncommon_fish =False 
        self .ignore_rare_fish =False 
        self .ignore_trash =False 
        self .fish_data ={}
        self .webhook_roblox_detected =True 
        self .webhook_roblox_reconnected =True 
        self .webhook_macro_started =True 
        self .webhook_macro_stopped =True 
        self .webhook_auto_sell_started =True 
        self .webhook_back_to_fishing =True 
        self .webhook_failsafe_triggered =True 
        self .webhook_error_notifications =True 
        self .webhook_phase_changes =False 
        self .webhook_cycle_completion =True 
        try :
            import numpy as np 
            self .np =np 
            self .numpy_available =True 
        except :
            self .numpy_available =False 
        self .load_calibration ()
        self .load_fish_data ()
        self .auto_sell_manager =AutoSellManager (coordinates =self .coordinates ,apply_mouse_delay_callback =self .apply_mouse_delay )

    @property 
    def auto_reconnect_enabled (self ):
        return self .auto_reconnect_manager .auto_reconnect_enabled 

    @auto_reconnect_enabled .setter 
    def auto_reconnect_enabled (self ,value ):
        self .auto_reconnect_manager .auto_reconnect_enabled =value 

    @property 
    def auto_reconnect_time (self ):
        return self .auto_reconnect_manager .auto_reconnect_time 

    @auto_reconnect_time .setter 
    def auto_reconnect_time (self ,value ):
        self .auto_reconnect_manager .auto_reconnect_time =value 

    @property 
    def auto_reconnect_timer_start (self ):
        return self .auto_reconnect_manager .auto_reconnect_timer_start 

    @auto_reconnect_timer_start .setter 
    def auto_reconnect_timer_start (self ,value ):
        self .auto_reconnect_manager .auto_reconnect_timer_start =value 

    @property 
    def roblox_private_server_link (self ):
        return self .auto_reconnect_manager .roblox_private_server_link 

    @roblox_private_server_link .setter 
    def roblox_private_server_link (self ,value ):
        self .auto_reconnect_manager .roblox_private_server_link =value 

    @property 
    def auto_reconnect_in_progress (self ):
        return self .auto_reconnect_manager .auto_reconnect_in_progress 

    @auto_reconnect_in_progress .setter 
    def auto_reconnect_in_progress (self ,value ):
        self .auto_reconnect_manager .auto_reconnect_in_progress =value 

    @property 
    def roblox_window_mode (self ):
        return self .auto_reconnect_manager .roblox_window_mode 

    @roblox_window_mode .setter 
    def roblox_window_mode (self ,value ):
        self .auto_reconnect_manager .roblox_window_mode =value 

    @property 
    def backslash_sequence_delay (self ):
        return self .auto_reconnect_manager .backslash_sequence_delay 

    @backslash_sequence_delay .setter 
    def backslash_sequence_delay (self ,value ):
        self .auto_reconnect_manager .backslash_sequence_delay =max (20.0 ,float (value ))

    def run_with_timeout (self ,func ,timeout_seconds =5 ,default_result =None ,*args ,**kwargs ):
        try :
            with concurrent .futures .ThreadPoolExecutor ()as executor :
                future =executor .submit (func ,*args ,**kwargs )
                try :
                    result =future .result (timeout =timeout_seconds )
                    return result 
                except concurrent .futures .TimeoutError :
                    print (f'Function {func .__name__ } timed out after {timeout_seconds } seconds, skipping...')
                    return default_result 
        except Exception as e :
            print (f'Error running function {func .__name__ } with timeout: {e }')
            return default_result 

    def get_screen_dimensions (self ):
        try :
            user32 =ctypes .windll .user32 
            virtual_width =user32 .GetSystemMetrics (78 )
            virtual_height =user32 .GetSystemMetrics (79 )
            if virtual_width >0 and virtual_height >0 :
                return (virtual_width ,virtual_height )
            screensize =(user32 .GetSystemMetrics (0 ),user32 .GetSystemMetrics (1 ))
            if screensize [0 ]>0 and screensize [1 ]>0 :
                return screensize 
        except :
            pass 
        try :
            pass 
        except :
            pass 
        return (1920 ,1080 )

    def detect_resolution (self ):
        width ,height =(self .screen_width ,self .screen_height )
        if width ==1024 and height ==768 :
            return '1024x768_100'
        elif width ==1920 and height ==1080 :
            return '1920x1080_100'
        elif width ==2560 and height ==1440 :
            return '2560x1440_100'
        elif width ==1366 and height ==768 :
            return '1366x768'
        elif width ==3840 and height ==2160 :
            return '3840x2160_100'
        else :
            return '1920x1080_100'

    def get_coordinates_for_resolution (self ,resolution ):
        try :
            if hasattr (self ,'calibration_manager'):
                available_calibrations =self .calibration_manager .get_available_calibrations ()
                base_resolution =resolution .split ('_')[0 ]
                best_match =None 
                for calib_name in available_calibrations :
                    calib_lower =calib_name .lower ()
                    if base_resolution in calib_lower :
                        best_match =calib_name 
                        break 
                    elif resolution .lower ()in calib_lower or resolution .replace ('_',' ').lower ()in calib_lower :
                        best_match =calib_name 
                        break 
                if best_match :
                    coordinates =self .calibration_manager .get_calibration_by_name (best_match )
                    if coordinates :
                        converted_coords ={}
                        for coord_name ,coord_data in coordinates .items ():
                            if isinstance (coord_data ,list ):
                                converted_coords [coord_name ]=tuple (coord_data )
                            else :
                                converted_coords [coord_name ]=coord_data 
                        return converted_coords 
                if available_calibrations :
                    fallback_name =None 
                    if '2560x1440'in base_resolution :
                        for calib_name in available_calibrations :
                            if '1920x1080'in calib_name .lower ():
                                fallback_name =calib_name 
                                break 
                    if not fallback_name :
                        preferred_resolutions =['1920x1080','1366x768','1600x900','1280x720']
                        for pref_res in preferred_resolutions :
                            for calib_name in available_calibrations :
                                if pref_res in calib_name .lower ():
                                    fallback_name =calib_name 
                                    break 
                            if fallback_name :
                                break 
                    if not fallback_name :
                        fallback_name =available_calibrations [0 ]
                    coordinates =self .calibration_manager .get_calibration_by_name (fallback_name )
                    if coordinates :
                        converted_coords ={}
                        for coord_name ,coord_data in coordinates .items ():
                            if isinstance (coord_data ,list ):
                                converted_coords [coord_name ]=tuple (coord_data )
                            else :
                                converted_coords [coord_name ]=coord_data 
                        return converted_coords 
        except Exception as e :
            pass 
        fallback_coords ={'fish_button':(851 ,802 ),'white_diamond':(1176 ,805 ),'reel_bar':(757 ,728 ,1163 ,750 ),'completed_border':(1133 ,744 ),'close_button':(1108 ,337 ),'fish_caught_desc':(700 ,540 ,1035 ,685 ),'first_item':(830 ,409 ),'sell_button':(588 ,775 ),'confirm_button':(797 ,613 ),'mouse_idle_position':(999 ,190 ),'shaded_area':(951 ,731 ),'sell_fish_shop':(900 ,600 ),'collection_button':(950 ,650 ),'exit_collections':(1000 ,700 ),'exit_fish_shop':(1050 ,750 )}
        return fallback_coords 

    def save_calibration (self ):
        try :
            backup_file =None 
            if os .path .exists (self .config_file ):
                backup_file =self .config_file +'.backup'
                try :
                    shutil .copy2 (self .config_file ,backup_file )
                except Exception as e :
                    print (f'Warning: Could not create backup file: {e }')
            auto_reconnect_config =self .auto_reconnect_manager .get_config_dict ()
            config_data ={'coordinates':self .coordinates ,'current_resolution':self .current_resolution ,'webhook_url':self .webhook_url ,'ignore_common':self .ignore_common_fish ,'ignore_uncommon':self .ignore_uncommon_fish ,'ignore_rare':self .ignore_rare_fish ,'ignore_trash':self .ignore_trash ,'mouse_delay_enabled':self .mouse_delay_enabled ,'mouse_delay_ms':self .mouse_delay_ms ,'failsafe_enabled':self .failsafe_enabled ,'failsafe_timeout':self .failsafe_timeout ,'failsafe_reconnect_threshold':self .failsafe_reconnect_threshold ,'failsafe_reconnect_enabled':self .failsafe_reconnect_enabled ,'bar_game_tolerance':self .bar_game_tolerance ,'auto_sell_enabled':self .auto_sell_enabled ,'auto_sell_configuration':self .auto_sell_configuration ,'fish_count_until_auto_sell':self .fish_count_until_auto_sell ,'first_launch_warning_shown':self .first_launch_warning_shown ,'use_vip_paths':self .use_vip_paths ,'webhook_roblox_detected':self .webhook_roblox_detected ,'webhook_roblox_reconnected':self .webhook_roblox_reconnected ,'webhook_macro_started':self .webhook_macro_started ,'webhook_macro_stopped':self .webhook_macro_stopped ,'webhook_auto_sell_started':self .webhook_auto_sell_started ,'webhook_back_to_fishing':self .webhook_back_to_fishing ,'webhook_failsafe_triggered':self .webhook_failsafe_triggered ,'webhook_error_notifications':self .webhook_error_notifications ,'webhook_phase_changes':self .webhook_phase_changes ,'webhook_cycle_completion':self .webhook_cycle_completion ,'config_version':'2.1','save_timestamp':datetime .now ().isoformat (),**auto_reconnect_config }
            if not isinstance (config_data ['coordinates'],dict ):
                raise ValueError ('Coordinates data is not a dictionary')
            required_coords =['fish_button','white_diamond','reel_bar','completed_border','close_button','mouse_idle_position','shaded_area']
            for coord_key in required_coords :
                if coord_key not in config_data ['coordinates']:
                    print (f'Warning: Missing required coordinate: {coord_key }')
            temp_file =self .config_file +'.tmp'
            with open (temp_file ,'w')as f :
                json .dump (config_data ,f ,indent =2 )
            with open (temp_file ,'r')as f :
                test_load =json .load (f )
                if 'coordinates'not in test_load :
                    raise ValueError ('Verification failed: saved config missing coordinates')
            if os .name =='nt':
                if os .path .exists (self .config_file ):
                    os .remove (self .config_file )
                os .rename (temp_file ,self .config_file )
            else :
                os .rename (temp_file ,self .config_file )
        except Exception as e :
            error_msg =f'Error saving calibration: {e }'
            print (error_msg )
            if backup_file and os .path .exists (backup_file ):
                try :
                    shutil .copy2 (backup_file ,self .config_file )
                except Exception as restore_error :
                    print (f'Could not restore from backup: {restore_error }')
            temp_file =self .config_file +'.tmp'
            if os .path .exists (temp_file ):
                try :
                    os .remove (temp_file )
                except :
                    pass 
            if hasattr (self ,'send_error_notification'):
                self .send_error_notification ('Configuration Save Error',error_msg )

    def load_calibration (self ):
        try :
            if not os .path .exists (self .config_file ):
                print (f'Config file does not exist: {self .config_file }. Using default settings.')
                return 
            backup_file =self .config_file +'.backup'
            if os .path .exists (backup_file ):
                try :
                    config_mtime =os .path .getmtime (self .config_file )
                    backup_mtime =os .path .getmtime (backup_file )
                    if backup_mtime >config_mtime :
                        try :
                            with open (self .config_file ,'r')as f :
                                test_data =json .load (f )
                            if 'coordinates'not in test_data :
                                raise ValueError ('Main config missing coordinates')
                        except :
                            shutil .copy2 (backup_file ,self .config_file )
                except Exception as e :
                    pass 
            with open (self .config_file ,'r')as f :
                saved_data =json .load (f )
            if not isinstance (saved_data ,dict ):
                raise ValueError ('Config file is not a valid dictionary')
            if isinstance (saved_data ,dict )and 'coordinates'in saved_data :
                coords_loaded =0 
                for key ,coord in saved_data ['coordinates'].items ():
                    if key in self .coordinates :
                        if key in ['reel_bar','fish_caught_desc']and len (coord )==4 :
                            self .coordinates [key ]=coord 
                            coords_loaded +=1 
                        elif len (coord )==2 :
                            self .coordinates [key ]=coord 
                            coords_loaded +=1 
                if 'current_resolution'in saved_data :
                    self .current_resolution =saved_data ['current_resolution']
                if 'webhook_url'in saved_data :
                    self .webhook_url =saved_data ['webhook_url']
                if 'ignore_common'in saved_data :
                    self .ignore_common_fish =bool (saved_data ['ignore_common'])
                if 'ignore_uncommon'in saved_data :
                    self .ignore_uncommon_fish =bool (saved_data ['ignore_uncommon'])
                if 'ignore_rare'in saved_data :
                    self .ignore_rare_fish =bool (saved_data ['ignore_rare'])
                if 'ignore_trash'in saved_data :
                    self .ignore_trash =bool (saved_data ['ignore_trash'])
                if 'mouse_delay_enabled'in saved_data :
                    self .mouse_delay_enabled =bool (saved_data ['mouse_delay_enabled'])
                if 'mouse_delay_ms'in saved_data :
                    self .mouse_delay_ms =int (saved_data ['mouse_delay_ms'])
                if 'failsafe_enabled'in saved_data :
                    self .failsafe_enabled =bool (saved_data ['failsafe_enabled'])
                if 'failsafe_timeout'in saved_data :
                    timeout =int (saved_data ['failsafe_timeout'])
                    self .failsafe_timeout =max (20 ,timeout )
                if 'failsafe_reconnect_threshold'in saved_data :
                    threshold =int (saved_data ['failsafe_reconnect_threshold'])
                    self .failsafe_reconnect_threshold =max (2 ,threshold )
                if 'failsafe_reconnect_enabled'in saved_data :
                    self .failsafe_reconnect_enabled =bool (saved_data ['failsafe_reconnect_enabled'])
                if 'bar_game_tolerance'in saved_data :
                    self .bar_game_tolerance =int (saved_data ['bar_game_tolerance'])
                if 'auto_sell_enabled'in saved_data :
                    self .auto_sell_enabled =bool (saved_data ['auto_sell_enabled'])
                    if hasattr (self ,'auto_sell_manager'):
                        self .auto_sell_manager .set_auto_sell_enabled (self .auto_sell_enabled )
                if 'auto_sell_configuration'in saved_data :
                    self .auto_sell_configuration =saved_data ['auto_sell_configuration']
                else :
                    self .auto_sell_configuration ='Sell All (Recommended)'
                if 'fish_count_until_auto_sell'in saved_data :
                    self .fish_count_until_auto_sell =int (saved_data ['fish_count_until_auto_sell'])
                if 'first_launch_warning_shown'in saved_data :
                    self .first_launch_warning_shown =bool (saved_data ['first_launch_warning_shown'])
                self .auto_reconnect_manager .load_config (saved_data )
                if 'use_vip_paths'in saved_data :
                    self .use_vip_paths =bool (saved_data ['use_vip_paths'])
                elif 'disable_all_pathing'in saved_data :
                    disable_pathing =bool (saved_data ['disable_all_pathing'])
                    self .use_vip_paths =not disable_pathing 
                    print (f'Migrated disable_all_pathing ({disable_pathing }) to use_vip_paths ({self .use_vip_paths })')
                else :
                    self .use_vip_paths =True 
                if 'webhook_roblox_detected'in saved_data :
                    self .webhook_roblox_detected =bool (saved_data ['webhook_roblox_detected'])
                if 'webhook_roblox_reconnected'in saved_data :
                    self .webhook_roblox_reconnected =bool (saved_data ['webhook_roblox_reconnected'])
                if 'webhook_macro_started'in saved_data :
                    self .webhook_macro_started =bool (saved_data ['webhook_macro_started'])
                elif 'webhook_automation_started'in saved_data :
                    self .webhook_macro_started =bool (saved_data ['webhook_automation_started'])
                if 'webhook_macro_stopped'in saved_data :
                    self .webhook_macro_stopped =bool (saved_data ['webhook_macro_stopped'])
                elif 'webhook_automation_stopped'in saved_data :
                    self .webhook_macro_stopped =bool (saved_data ['webhook_automation_stopped'])
                if 'webhook_auto_sell_started'in saved_data :
                    self .webhook_auto_sell_started =bool (saved_data ['webhook_auto_sell_started'])
                if 'webhook_back_to_fishing'in saved_data :
                    self .webhook_back_to_fishing =bool (saved_data ['webhook_back_to_fishing'])
                if 'webhook_failsafe_triggered'in saved_data :
                    self .webhook_failsafe_triggered =bool (saved_data ['webhook_failsafe_triggered'])
                if 'webhook_error_notifications'in saved_data :
                    self .webhook_error_notifications =bool (saved_data ['webhook_error_notifications'])
                if 'webhook_phase_changes'in saved_data :
                    self .webhook_phase_changes =bool (saved_data ['webhook_phase_changes'])
                if 'webhook_cycle_completion'in saved_data :
                    self .webhook_cycle_completion =bool (saved_data ['webhook_cycle_completion'])
            else :
                coords_loaded =0 
                for key ,coord in saved_data .items ():
                    if key in self .coordinates :
                        if key in ['reel_bar','fish_caught_desc']and len (coord )==4 :
                            self .coordinates [key ]=coord 
                            coords_loaded +=1 
                        elif len (coord )==2 :
                            self .coordinates [key ]=coord 
                            coords_loaded +=1 
        except json .JSONDecodeError as e :
            error_msg =f'Config file is corrupted (JSON decode error): {e }'
            print (error_msg )
            backup_file =self .config_file +'.backup'
            if os .path .exists (backup_file ):
                try :
                    shutil .copy2 (backup_file ,self .config_file )
                    if not hasattr (self ,'_load_retry_attempted'):
                        self ._load_retry_attempted =True 
                        self .load_calibration ()
                        delattr (self ,'_load_retry_attempted')
                except Exception as restore_error :
                    print (f'Could not restore from backup: {restore_error }')
                    if hasattr (self ,'send_error_notification'):
                        self .send_error_notification ('Config Load Error',f'Corrupted config file and backup restore failed: {restore_error }')
            elif hasattr (self ,'send_error_notification'):
                self .send_error_notification ('Config Load Error',error_msg )
        except FileNotFoundError :
            print (f'Config file not found: {self .config_file }. Using default settings.')
        except PermissionError as e :
            error_msg =f'Permission denied accessing config file: {e }'
            print (error_msg )
            if hasattr (self ,'send_error_notification'):
                self .send_error_notification ('Config Permission Error',error_msg )
        except Exception as e :
            error_msg =f'Unexpected error loading calibration: {e }'
            print (error_msg )
            if hasattr (self ,'send_error_notification'):
                self .send_error_notification ('Config Load Error',error_msg )
        if hasattr (self ,'coord_labels_widgets')and hasattr (self ,'update_all_coordinate_labels'):
            try :
                self .update_all_coordinate_labels ()
            except Exception :
                pass 

    def get_mouse_position (self ):
        return autoit .mouse_get_pos ()

    def get_pixel_color (self ,x ,y ):
        screenshot =ImageGrab .grab (bbox =(x ,y ,x +1 ,y +1 ))
        return screenshot .getpixel ((0 ,0 ))

    def is_white_pixel (self ,color ,tolerance =10 ):
        r ,g ,b =color [:3 ]
        return all ((c >=255 -tolerance for c in [r ,g ,b ]))

    def pixel_search_white (self ,x ,y ,tolerance =10 ):
        try :
            color =self .get_pixel_color (x ,y )
            return color ==(255 ,255 ,255 )or self .is_white_pixel (color ,tolerance )
        except :
            return False 

    def pixel_search_color (self ,x1 ,y1 ,x2 ,y2 ,target_color ,tolerance =5 ):
        if self .numpy_available :
            try :
                screenshot =ImageGrab .grab (bbox =(x1 ,y1 ,x2 ,y2 ))
                img_array =self .np .array (screenshot )
                target_r ,target_g ,target_b =target_color [:3 ]
                r_diff =self .np .abs (img_array [:,:,0 ].astype (self .np .int16 )-target_r )<=tolerance 
                g_diff =self .np .abs (img_array [:,:,1 ].astype (self .np .int16 )-target_g )<=tolerance 
                b_diff =self .np .abs (img_array [:,:,2 ].astype (self .np .int16 )-target_b )<=tolerance 
                matches =r_diff &g_diff &b_diff 
                match_coords =self .np .where (matches )
                if len (match_coords [0 ])>0 :
                    return (x1 +match_coords [1 ][0 ],y1 +match_coords [0 ][0 ])
                return None 
            except :
                pass 
        try :
            screenshot =ImageGrab .grab (bbox =(x1 ,y1 ,x2 ,y2 ))
            width ,height =screenshot .size 
            sample_points =[(width //4 ,height //2 ),(width //2 ,height //2 ),(3 *width //4 ,height //2 ),(width //2 ,height //4 ),(width //2 ,3 *height //4 )]
            for x ,y in sample_points :
                if 0 <=x <width and 0 <=y <height :
                    pixel =screenshot .getpixel ((x ,y ))
                    if self .color_match (pixel ,target_color ,tolerance ):
                        return (x1 +x ,y1 +y )
            return None 
        except :
            return None 

    def color_match (self ,color1 ,color2 ,tolerance ):
        return all ((abs (c1 -c2 )<=tolerance for c1 ,c2 in zip (color1 ,color2 )))

    def load_fish_data (self ):
        try :
            response = requests.get('https://raw.githubusercontent.com/cresqnt-sys/FishScope-macro/main/fish-data.json')
            response.raise_for_status()
            self.fish_data = response.json()
        except Exception as e:
            self.fish_data = {}
            print(f'Failed loading fish data: {e}')

    def extract_fish_name (self ):
        if 'fish_caught_desc'not in self .coordinates :
            return ('Unknown Fish',None )
        try :
            desc_x1 ,desc_y1 ,desc_x2 ,desc_y2 =self .coordinates ['fish_caught_desc']
            screenshot =ImageGrab .grab (bbox =(desc_x1 ,desc_y1 ,desc_x2 ,desc_y2 ))
            try :
                screenshot .save ('debug_ocr_capture.png')
            except Exception as e :
                pass 
            fish_description =self .ocr_extract_tesseract (screenshot )
            if not fish_description .strip ():
                return ('Unknown Fish',None )
            fish_description =self .clean_ocr_text (fish_description )
            fish_name ,mutation =self .search_for_fish_name (fish_description )
            if fish_name !='Unknown Fish':
                return (fish_name ,mutation )
            return ('Unknown Fish',None )
        except Exception as e :
            print (f'Error in extract_fish_name: {e }')
            return ('Unknown Fish',None )

    def search_for_fish_name (self ,fish_description ):
        mutations =['Ruffled','Crusted','Slick','Rough','Charred','Shimmering','Tainted','Hollow','Lucid','Fragmented']
        mutation_found =None 
        for mutation in mutations :
            if mutation .lower ()in fish_description .lower ():
                mutation_found =mutation 
                fish_description =fish_description .lower ().replace (mutation .lower (),'').strip ()
                break 
        best_match =process .extractOne (fish_description ,self .fish_data .keys ())
        if best_match and best_match [1 ]>=60 :
            return (best_match [0 ],mutation_found )
        else :
            return ('Unknown Fish',mutation_found )

    def clean_ocr_text (self ,text ):
        text =text .lower ()
        replacements ={'0':'o','1':'l','2':'z','3':'e','4':'a','5':'s','6':'g','7':'t','8':'b','9':'q'}
        for wrong ,right in replacements .items ():
            text =text .replace (wrong ,right )
        return text 

    def ocr_extract_tesseract (self ,image ):
        try :
            result =pytesseract .image_to_string (image )
            return result 
        except pytesseract .TesseractNotFoundError :
            print ('Tesseract OCR not found. Attempting to reconfigure...')
            if setup_tesseract ():
                try :
                    result =pytesseract .image_to_string (image )
                    return result 
                except Exception as e :
                    pass 
            return 'Unknown Fish'
        except Exception as e :
            return 'Unknown Fish'

    def extract_fish_name_with_timeout (self ):
        try :
            result =self .run_with_timeout (self .extract_fish_name ,timeout_seconds =5 ,default_result =('Unknown Fish',None ))
            return result 
        except Exception as e :
            print (f'Error in extract_fish_name_with_timeout: {e }')
            return ('Unknown Fish',None )

    def send_webhook_message_with_timeout (self ,fish_name ,mutation ):
        try :
            self .run_with_timeout (self .send_webhook_message ,5 ,None ,fish_name ,mutation )
        except Exception as e :
            print (f'Error in send_webhook_message_with_timeout: {e }')

    def get_rarity_color (self ,rarity ):
        rarity_colors ={'Common':12566463 ,'Uncommon':5094750 ,'Rare':2063812 }
        return rarity_colors .get (rarity ,9127187 )

    def send_webhook_message (self ,fish_name ,mutation ):
        if not self .webhook_url :
            print ('Webhook URL is not set.')
            return 
        if fish_name =='Fishing Failed':
            return 
        if fish_name in self .fish_data :
            rarity =self .fish_data [fish_name ]['rarity']
            color =self .get_rarity_color (rarity )
            if rarity =='Trash':
                title ='You snagged some trash!'
                name ='Item'
            else :
                title ='Fish Caught!'
                name ='Fish'
        else :
            rarity ='Trash'
            color =9127187 
            title ='You snagged some trash!'
            name ='Item'
        if rarity =='Common'and self .ignore_common_fish :
            return 
        if rarity =='Uncommon'and self .ignore_uncommon_fish :
            return 
        if rarity =='Rare'and self .ignore_rare_fish :
            return 
        if rarity =='Trash'and self .ignore_trash :
            return 
        fields =[{'name':name ,'value':fish_name ,'inline':True },{'name':'Rarity','value':rarity ,'inline':True }]
        if mutation :
            fields .append ({'name':'Mutation','value':mutation ,'inline':True })
        embed ={'title':title ,'color':color ,'timestamp':datetime .now (timezone .utc ).isoformat ().replace ('+00:00','Z'),'fields':fields ,'thumbnail':{'url':'https://raw.githubusercontent.com/cresqnt-sys/FishScope-Macro/main/fishscope-nobg.png'},'footer':{'text':'FishScope Macro'}}
        data ={'embeds':[embed ]}
        try :
            response =self .run_with_timeout (requests .post ,5 ,None ,self .webhook_url ,json =data )
            if response and hasattr (response ,'status_code'):
                response .raise_for_status ()
                print (f'Webhook sent successfully: {response .status_code }')
            else :
                print ('Webhook timed out after 5 seconds, skipping...')
        except requests .exceptions .RequestException as e :
            print (f'Failed to send webhook: {e }')
            if hasattr (response ,'text'):
                print (f'Response content: {response .text }')
            print (f'Request data: {json .dumps (data ,indent =2 )}')
        except Exception as e :
            print (f'Error sending webhook: {e }')

    def send_webhook_message2 (self ,title ,description ,color =65280 ):
        if not self .webhook_url :
            return 
        embed ={'title':title ,'color':color ,'timestamp':datetime .now (timezone .utc ).isoformat ().replace ('+00:00','Z'),'fields':[{'name':'Status','value':description ,'inline':False }],'thumbnail':{'url':'https://raw.githubusercontent.com/cresqnt-sys/FishScope-Macro/main/fishscope-nobg.png'},'footer':{'text':'FishScope Macro'}}
        data ={'embeds':[embed ]}
        try :
            response =self .run_with_timeout (requests .post ,5 ,None ,self .webhook_url ,json =data )
            if response and hasattr (response ,'status_code'):
                response .raise_for_status ()
                print (f'Webhook sent successfully: {response .status_code }')
            else :
                print ('Webhook timed out after 5 seconds, skipping...')
        except requests .exceptions .RequestException as e :
            print (f'Failed to send webhook: {e }')
            if hasattr (response ,'text'):
                print (f'Response content: {response .text }')
            print (f'Request data: {json .dumps (data ,indent =2 )}')
        except Exception as e :
            print (f'Error sending webhook: {e }')

    def send_webhook_notification (self ,notification_type ,title ,description ,color =None ,extra_fields =None ):
        if not self .webhook_url :
            return 
        webhook_setting =getattr (self ,f'webhook_{notification_type }',True )
        if not webhook_setting :
            print (f"Webhook notification '{notification_type }' is disabled, skipping...")
            return 
        if color is None :
            color_map ={'roblox_detected':2664261 ,'roblox_reconnected':1548984 ,'macro_started':2664261 ,'macro_stopped':14431557 ,'auto_sell_started':16761095 ,'back_to_fishing':2148759 ,'failsafe_triggered':16612884 ,'error_notifications':14431557 ,'phase_changes':7291585 ,'cycle_completion':6689010 }
            color =color_map .get (notification_type ,7107965 )
        embed ={'title':title ,'color':color ,'timestamp':datetime .now (timezone .utc ).isoformat ().replace ('+00:00','Z'),'fields':[{'name':'Status','value':description ,'inline':False }],'thumbnail':{'url':'https://raw.githubusercontent.com/cresqnt-sys/FishScope-Macro/main/fishscope-nobg.png'},'footer':{'text':'FishScope Macro'}}
        if extra_fields :
            embed ['fields'].extend (extra_fields )
        data ={'embeds':[embed ]}
        try :
            response =self .run_with_timeout (requests .post ,5 ,None ,self .webhook_url ,json =data )
            if response and hasattr (response ,'status_code'):
                response .raise_for_status ()
                print (f"Webhook notification '{notification_type }' sent successfully: {response .status_code }")
            else :
                print (f"Webhook notification '{notification_type }' timed out after 5 seconds, skipping...")
        except requests .exceptions .RequestException as e :
            print (f"Failed to send webhook notification '{notification_type }': {e }")
            if hasattr (response ,'text'):
                print (f'Response content: {response .text }')
        except Exception as e :
            print (f"Error sending webhook notification '{notification_type }': {e }")

    def send_roblox_detected_notification (self ):
        self .send_webhook_notification ('roblox_detected','🎮 Roblox Process Detected','RobloxPlayerBeta.exe has been detected and is running')

    def send_roblox_reconnected_notification (self ):
        extra_fields =[]
        if self .auto_reconnect_time :
            extra_fields .append ({'name':'Reconnect Interval','value':f'{self .auto_reconnect_time } seconds','inline':True })
        self .send_webhook_notification ('roblox_reconnected','🔄 Roblox Reconnected','Auto-reconnection successful, resuming fishing macro',extra_fields =extra_fields )

    def send_macro_started_notification (self ):
        extra_fields =[{'name':'Fish Target','value':f'{self .fish_count_until_auto_sell } fish','inline':True }]
        if self .auto_sell_enabled :
            extra_fields .append ({'name':'Auto-Sell','value':'Enabled','inline':True })
        else :
            extra_fields .append ({'name':'Auto-Sell','value':'Disabled','inline':True })
        if self .use_vip_paths :
            extra_fields .append ({'name':'Mode','value':'VIP Paths (Fast)','inline':True })
        else :
            extra_fields .append ({'name':'Mode','value':'Non-VIP Paths (Standard)','inline':True })
        self .send_webhook_notification ('macro_started','▶️ Macro Started','FishScope macro has been started',extra_fields =extra_fields )

    def send_macro_stopped_notification (self ):
        elapsed_time =''
        if hasattr (self ,'start_time')and self .start_time :
            elapsed =time .time ()-self .start_time 
            hours =int (elapsed //3600 )
            minutes =int (elapsed %3600 //60 )
            seconds =int (elapsed %60 )
            elapsed_time =f'{hours :02d}:{minutes :02d}:{seconds :02d}'
        extra_fields =[]
        if elapsed_time :
            extra_fields .append ({'name':'Runtime','value':elapsed_time ,'inline':True })
        if hasattr (self ,'current_fish_count'):
            extra_fields .append ({'name':'Fish Caught','value':str (self .current_fish_count ),'inline':True })
        self .send_webhook_notification ('macro_stopped','⏹️ Macro Stopped','FishScope macro has been stopped',extra_fields =extra_fields )

    def send_automation_started_notification (self ):
        return self .send_macro_started_notification ()

    def send_automation_stopped_notification (self ):
        return self .send_macro_stopped_notification ()

    def send_auto_sell_started_notification (self ):
        extra_fields =[{'name':'Fish Count','value':f'{self .current_fish_count }','inline':True },{'name':'Selling','value':f'{self .fish_count_until_auto_sell } fish','inline':True }]
        self .send_webhook_notification ('auto_sell_started','💰 Auto-Sell Started','Starting auto-sell cycle at fish shop',extra_fields =extra_fields )

    def send_back_to_fishing_notification (self ):
        self .send_webhook_notification ('back_to_fishing','🎣 Back to Fishing','Auto-sell complete, returning to fishing location')

    def send_failsafe_triggered_notification (self ,reason ='Soft lock detected',consecutive_count =None ):
        extra_fields =[{'name':'Trigger Reason','value':reason ,'inline':True },{'name':'Timeout','value':f'{self .failsafe_timeout } seconds','inline':True }]
        if consecutive_count is not None :
            extra_fields .append ({'name':'Consecutive Count','value':f'{consecutive_count }/{self .failsafe_reconnect_threshold }','inline':True })
        self .send_webhook_notification ('failsafe_triggered','⚠️ Failsafe Triggered','Failsafe system activated to recover from issue',extra_fields =extra_fields )

    def send_failsafe_reconnect_notification (self ,consecutive_count ):
        extra_fields =[{'name':'Consecutive Failsafes','value':str (consecutive_count ),'inline':True },{'name':'Threshold','value':str (self .failsafe_reconnect_threshold ),'inline':True },{'name':'Action','value':'Initiating auto-reconnect','inline':False }]
        self .send_webhook_notification ('failsafe_triggered','🔄 Failsafe Auto-Reconnect','Multiple consecutive failsafes detected - triggering auto-reconnect',extra_fields =extra_fields )

    def send_error_notification (self ,error_type ,error_message ):
        extra_fields =[{'name':'Error Type','value':error_type ,'inline':True },{'name':'Details','value':error_message [:1000 ],'inline':False }]
        self .send_webhook_notification ('error_notifications','❌ Error Detected','An error occurred during macro execution',extra_fields =extra_fields )

    def send_phase_change_notification (self ,old_phase ,new_phase ):
        phase_descriptions ={'initialization':'Setting up macro and navigation','fishing':'Actively fishing for catches','pre_sell':'Preparing for auto-sell sequence','selling':'Selling caught fish at shop','post_sell':'Completing sell cycle'}
        extra_fields =[{'name':'Previous Phase','value':phase_descriptions .get (old_phase ,old_phase ),'inline':True },{'name':'Current Phase','value':phase_descriptions .get (new_phase ,new_phase ),'inline':True }]
        self .send_webhook_notification ('phase_changes','🔄 Phase Change',f'Macro phase changed from {old_phase } to {new_phase }',extra_fields =extra_fields )

    def send_cycle_completion_notification (self ,cycle_type ,fish_count =None ):
        extra_fields =[]
        if fish_count :
            extra_fields .append ({'name':'Fish Processed','value':str (fish_count ),'inline':True })
        descriptions ={'fishing':'Fishing cycle completed, target fish count reached','selling':'Auto-sell cycle completed successfully','full':'Complete macro cycle finished (fishing + selling)'}
        self .send_webhook_notification ('cycle_completion','✅ Cycle Complete',descriptions .get (cycle_type ,f'{cycle_type } cycle completed'),extra_fields =extra_fields )

    def setup_dpi_awareness (self ):
        try :
            ctypes .windll .shcore .SetProcessDpiAwareness (2 )
        except :
            try :
                ctypes .windll .user32 .SetProcessDPIAware ()
            except :
                pass 

    def get_dpi_scale_factor (self ):
        try :
            hdc =ctypes .windll .user32 .GetDC (0 )
            dpi_x =ctypes .windll .gdi32 .GetDeviceCaps (hdc ,88 )
            ctypes .windll .user32 .ReleaseDC (0 ,hdc )
            scale_factor =dpi_x /96.0 
            return scale_factor 
        except Exception :
            return 1.0 

    def get_effective_scale_factor (self ):
        if self .manual_scale_override is not None :
            return self .manual_scale_override /100.0 
        elif self .auto_scale_enabled :
            return self .dpi_scale_factor 
        else :
            return 1.0 

    def update_scaled_coordinates (self ):
        pass 

    def set_manual_scale_override (self ,percentage ):
        if percentage is None :
            self .manual_scale_override =None 
        else :
            self .manual_scale_override =percentage 
        self .update_scaled_coordinates ()

    def set_auto_scale_enabled (self ,enabled ):
        self .auto_scale_enabled =enabled 
        self .update_scaled_coordinates ()

    def check_emergency_stop (self ):
        return not self .toggle or not self .running 

    def apply_mouse_delay (self ):
        if self .check_emergency_stop ():
            return False 
        if self .mouse_delay_enabled and self .mouse_delay_ms >0 :
            delay_sec =self .mouse_delay_ms /1000.0 
            chunk_size =0.1 
            chunks =int (delay_sec /chunk_size )
            remainder =delay_sec %chunk_size 
            for _ in range (chunks ):
                if self .check_emergency_stop ():
                    return False 
                time .sleep (chunk_size )
            if remainder >0 :
                if self .check_emergency_stop ():
                    return False 
                time .sleep (remainder )
        return True 

    def perform_drag_up (self ):
        try :
            try :
                from screeninfo import get_monitors 
                monitor =get_monitors ()[0 ]
                screen_width =monitor .width 
                screen_height =monitor .height 
            except (ImportError ,IndexError ):
                screen_width ,screen_height =(1920 ,1080 )
            center_x =screen_width //2 
            start_y =int (screen_height *0.8 )
            end_y =int (screen_height *0.2 )
            autoit .mouse_move (x =center_x ,y =start_y ,speed =0 )
            time .sleep (0.1 )
            autoit .mouse_down ('right')
            time .sleep (0.1 )
            autoit .mouse_move (x =center_x ,y =end_y ,speed =10 )
            time .sleep (0.1 )
            autoit .mouse_up ('right')
        except Exception as e :
            pass 

    def run_external_script (self ,script_name ,delay =1 ):
        if not EXTERNAL_SCRIPTS_AVAILABLE :
            print (f'Warning: External scripts not available, skipping {script_name }')
            return False 
        if self .check_emergency_stop ():
            print (f'Emergency stop detected, cancelling {script_name }')
            return False 
        try :
            self .external_script_running =True 
            pre_script_toggle =self .toggle 
            pre_script_running =self .running 
            if script_name =='autoalign':
                auto_align_camera (delay =delay ,emergency_stop_check =self .check_emergency_stop )
            elif script_name =='fishinglocation':
                if self .use_vip_paths :
                    run_fishing_location_macro (fishing_location_actions ,delay =delay ,emergency_stop_check =self .check_emergency_stop )
                else :
                    run_nonvip_fishing_location_macro (nonvip_fishing_location_actions ,delay =delay ,emergency_stop_check =self .check_emergency_stop )
            elif script_name =='shoppath':
                if self .use_vip_paths :
                    run_shop_path_macro (shop_path_actions ,delay =delay ,emergency_stop_check =self .check_emergency_stop )
                else :
                    run_nonvip_shop_path_macro (nonvip_shop_path_actions ,delay =delay ,emergency_stop_check =self .check_emergency_stop )
            else :
                self .external_script_running =False 
                return False 
            if pre_script_toggle and (not self .toggle ):
                print (f'Warning: toggle was set to False during {script_name } execution')
            if pre_script_running and (not self .running ):
                print (f'Warning: running was set to False during {script_name } execution')
            if pre_script_toggle and pre_script_running :
                if self .toggle and self .running :
                    self .external_script_running =False 
                    return True 
                else :
                    self .external_script_running =False 
                    return False 
            elif not self .toggle or not self .running :
                self .external_script_running =False 
                return False 
            self .external_script_running =False 
            return True 
        except Exception as e :
            print (f'Error running {script_name }: {e }')
            self .external_script_running =False 
            return False 

    def click_coordinate (self ,coord_name ,delay =0.5 ):
        if self .check_emergency_stop ():
            print (f'Emergency stop detected, cancelling click on {coord_name }')
            return False 
        if coord_name not in self .coordinates :
            print (f"Warning: Coordinate '{coord_name }' not found")
            return False 
        try :
            coord =self .coordinates [coord_name ]
            if len (coord )>=2 :
                x ,y =(coord [0 ],coord [1 ])
                autoit .mouse_move (x ,y ,3 )
                if not self .apply_mouse_delay ():
                    print (f'Emergency stop detected during mouse delay for {coord_name }')
                    return False 
                time .sleep (0.3 )
                if self .check_emergency_stop ():
                    print (f'Emergency stop detected before clicking {coord_name }')
                    return False 
                autoit .mouse_click ('left')
                if not self .apply_mouse_delay ():
                    print (f'Emergency stop detected during post-click delay for {coord_name }')
                    return False 
                remaining_delay =delay 
                chunk_size =0.1 
                while remaining_delay >0 :
                    if self .check_emergency_stop ():
                        print (f'Emergency stop detected during {coord_name } delay')
                        return False 
                    sleep_time =min (chunk_size ,remaining_delay )
                    time .sleep (sleep_time )
                    remaining_delay -=sleep_time 
                return True 
            else :
                print (f"Warning: Invalid coordinates for '{coord_name }'")
                return False 
        except Exception as e :
            print (f'Error clicking {coord_name }: {e }')
            return False 

    def execute_failsafe (self ):
        if self .auto_reconnect_in_progress :
            print ('Skipping failsafe - auto reconnect in progress')
            return False 
        self .failsafe_consecutive_count +=1 
        print (f'Failsafe activated ({self .failsafe_consecutive_count }/{self .failsafe_reconnect_threshold }) - attempting to recover from soft lock...')
        if self .failsafe_reconnect_enabled and self .failsafe_consecutive_count >=self .failsafe_reconnect_threshold :
            print (f'Failsafe threshold reached ({self .failsafe_consecutive_count } consecutive triggers) - initiating auto-reconnect...')
            self .send_failsafe_reconnect_notification (self .failsafe_consecutive_count )
            self .failsafe_consecutive_count =0 
            if self .perform_auto_reconnect ():
                self .current_fish_count =0 
                self .automation_phase ='initialization'
                print ('Auto-reconnect successful after failsafe - resetting to initialization phase')
                return True 
            else :
                print ('Auto-reconnect failed after failsafe')
                return False 
        self .send_failsafe_triggered_notification ('White diamond timeout - attempting recovery',consecutive_count =self .failsafe_consecutive_count )
        close_x ,close_y =self .coordinates ['close_button']
        autoit .mouse_move (close_x ,close_y ,3 )
        time .sleep (0.3 )
        autoit .mouse_click ('left')
        self .apply_mouse_delay ()
        time .sleep (0.3 )
        confirm_x ,confirm_y =self .coordinates ['confirm_button']
        autoit .mouse_move (confirm_x ,confirm_y ,3 )
        time .sleep (0.15 )
        autoit .mouse_click ('left')
        self .apply_mouse_delay ()
        time .sleep (0.3 )
        fish_x ,fish_y =self .coordinates ['fish_button']
        autoit .mouse_move (fish_x ,fish_y ,3 )
        time .sleep (0.15 )
        autoit .mouse_click ('left')
        self .apply_mouse_delay ()
        time .sleep (0.15 )
        return False 

    def should_auto_reconnect (self ):
        return self .auto_reconnect_manager .should_auto_reconnect ()

    def get_auto_reconnect_time_remaining (self ):
        return self .auto_reconnect_manager .get_auto_reconnect_time_remaining ()

    def interruptible_sleep (self ,duration ):
        return self .auto_reconnect_manager .interruptible_sleep (duration ,self .check_emergency_stop )

    def perform_auto_reconnect (self ):
        return self .auto_reconnect_manager .perform_auto_reconnect (lambda :self .toggle )

    def mouse_automation_loop (self ):
        try :
            self .current_fish_count =0 
            self .automation_phase ='initialization'
            print ('Starting new macro sequence...')
            while self .running and self .toggle :
                if self .check_emergency_stop ():
                    print ('Emergency stop detected in main loop, exiting...')
                    break 
                if self .auto_reconnect_in_progress :
                    time .sleep (0.5 )
                    continue 
                if self .should_auto_reconnect ():
                    if self .perform_auto_reconnect ():
                        self .current_fish_count =0 
                        self .automation_phase ='initialization'
                        continue 
                    else :
                        print ('Auto reconnect failed, continuing with normal macro')
                try :
                    if self .automation_phase =='initialization'or self .automation_phase =='post_sell':
                        old_phase =self .automation_phase 
                        self .send_phase_change_notification (old_phase ,'initialization')
                        if not self .click_coordinate ('collection_button',1.0 ):
                            print ('Failed to click collection button, retrying...')
                            continue 
                        time .sleep (1.0 )
                        if not self .click_coordinate ('exit_collections',1.0 ):
                            print ('Failed to click exit collections, retrying...')
                            continue 
                        if not self .run_external_script ('autoalign',delay =2 ):
                            print ('Failed to run autoalign script')
                        time .sleep (1.0 )
                        if not self .run_external_script ('fishinglocation',delay =2 ):
                            print ('Failed to run fishing location script')
                        time .sleep (1.0 )
                        self .current_fish_count =0 
                        self .automation_phase ='fishing'
                    if self .automation_phase =='fishing':
                        if self .auto_sell_enabled and self .current_fish_count >=self .fish_count_until_auto_sell :
                            self .send_cycle_completion_notification ('fishing',self .current_fish_count )
                            self .automation_phase ='pre_sell'
                            continue 
                        elif not self .auto_sell_enabled :
                            pass 
                        fish_caught =self .perform_single_fishing_cycle ()
                        if fish_caught =='auto_reconnect':
                            if self .perform_auto_reconnect ():
                                self .current_fish_count =0 
                                self .automation_phase ='initialization'
                                continue 
                            else :
                                continue 
                        if fish_caught =='auto_reconnect_after_failsafe':
                            print ('Continuing macro after failsafe auto-reconnect')
                            continue 
                        if fish_caught :
                            self .current_fish_count +=1 
                    elif self .automation_phase =='pre_sell'and self .auto_sell_enabled :
                        self .send_auto_sell_started_notification ()
                        self .send_phase_change_notification ('fishing','pre_sell')
                        if not self .click_coordinate ('collection_button',1.0 ):
                            print ('Failed to click collection button for sell phase')
                            continue 
                        time .sleep (1.0 )
                        if not self .click_coordinate ('exit_collections',1.0 ):
                            print ('Failed to click exit collections for sell phase')
                            continue 
                        if not self .run_external_script ('autoalign',delay =2 ):
                            print ('Failed to run autoalign script for sell phase')
                        time .sleep (1.0 )
                        if not self .run_external_script ('shoppath',delay =2 ):
                            pass 
                        time .sleep (1.0 )
                        if not self .toggle or not self .running :
                            break 
                        self .perform_drag_up ()
                        time .sleep (4.0 )
                        if not self .toggle or not self .running :
                            break 
                        if not self .click_coordinate ('sell_fish_shop',1.0 ):
                            continue 
                        time .sleep (1.0 )
                        self .automation_phase ='selling'
                    elif self .automation_phase =='selling':
                        if self .auto_sell_configuration =='Sell All (Recommended)':
                            sell_count =51
                        else :
                            sell_count =self .fish_count_until_auto_sell 
                        self .send_phase_change_notification ('pre_sell','selling')
                        for i in range (sell_count ):
                            if self .check_emergency_stop ():
                                break 
                            if hasattr (self ,'auto_sell_manager'):
                                self .auto_sell_manager .set_auto_sell_enabled (True )
                                self .auto_sell_manager .set_first_loop (False )
                                self .auto_sell_manager .update_coordinates (self .coordinates )
                                if not self .auto_sell_manager .perform_manual_sell ():
                                    pass 
                            else :
                                break 
                            time .sleep (0.5 )
                        time .sleep (1.0 )
                        if not self .click_coordinate ('exit_fish_shop',1.0 ):
                            pass 
                        time .sleep (1.0 )
                        self .send_cycle_completion_notification ('selling',sell_count )
                        self .send_back_to_fishing_notification ()
                        self .automation_phase ='initialization'
                except Exception as e :
                    print (f"Error in macro phase '{self .automation_phase }': {e }")
                    self .send_error_notification (f'Macro Phase Error',f'Error in {self .automation_phase }: {str (e )}')
                    self .automation_phase ='initialization'
                    sleep_result =self .interruptible_sleep (2.0 )
                    if sleep_result =='auto_reconnect':
                        if self .perform_auto_reconnect ():
                            self .current_fish_count =0 
                            self .automation_phase ='initialization'
                            continue 
                        else :
                            print ('Auto reconnect failed, continuing with normal macro')
                    elif sleep_result ==False :
                        break 
                    continue 
        except Exception as e :
            print (f'Critical error in macro loop: {e }')
            self .send_error_notification ('Critical Macro Error',str (e ))
            print ('Macro loop terminated due to error')
        finally :
            print ('Macro loop ended')

    def perform_single_fishing_cycle (self ):
        try :
            fish_x ,fish_y =self .coordinates ['fish_button']
            autoit .mouse_move (fish_x ,fish_y ,3 )
            time .sleep (0.15 )
            autoit .mouse_click ('left')
            self .apply_mouse_delay ()
            time .sleep (0.15 )
            bar_color =None 
            white_diamond_start_time =time .time ()
            while True :
                if self .check_emergency_stop ():
                    print ('Emergency stop detected during white diamond wait')
                    return False 
                if self .should_auto_reconnect ():
                    return 'auto_reconnect'
                check_x ,check_y =self .coordinates ['white_diamond']
                if self .pixel_search_white (check_x ,check_y ):
                    self .failsafe_consecutive_count =0 
                    idle_x ,idle_y =self .coordinates ['mouse_idle_position']
                    autoit .mouse_move (idle_x ,idle_y ,3 )
                    time .sleep (0.025 )
                    shaded_x ,shaded_y =self .coordinates ['shaded_area']
                    bar_color =self .get_pixel_color (shaded_x ,shaded_y )
                    print (f'Detected bar color: {bar_color }')
                    break 
                elapsed_time =time .time ()-white_diamond_start_time 
                if self .failsafe_enabled and elapsed_time >self .failsafe_timeout :
                    if self .auto_reconnect_in_progress :
                        print (f'Failsafe check: Auto reconnect in progress, skipping failsafe (elapsed: {elapsed_time :.1f}s)')
                    else :
                        print (f'Failsafe triggered: No white diamond detected within {self .failsafe_timeout } seconds (elapsed: {elapsed_time :.1f}s)')
                        reconnect_happened =self .execute_failsafe ()
                        if reconnect_happened :
                            return 'auto_reconnect_after_failsafe'
                        else :
                            white_diamond_start_time =time .time ()
                            continue 
                time .sleep (0.05 )
            start_time =time .time ()
            loop_count =0 
            ready_to_stop =False 
            extra_clicks_after_ready =0 
            while True :
                if self .check_emergency_stop ():
                    print ('Emergency stop detected during reeling')
                    break 
                if time .time ()-start_time >9 :
                    break 
                if self .should_auto_reconnect ():
                    return 'auto_reconnect'
                loop_count +=1 
                if loop_count %50 ==0 :
                    completed_x ,completed_y =self .coordinates ['completed_border']
                    if self .pixel_search_white (completed_x ,completed_y ,tolerance =15 ):
                        time .sleep (1.0 )
                        break 
                search_area =self .coordinates ['reel_bar']
                found_pos =self .pixel_search_color (*search_area ,bar_color ,tolerance =5 )
                if found_pos is None :

                    autoit .mouse_click ('left')
                    ready_to_stop =False 
                    extra_clicks_after_ready =0 
                else :

                    if not ready_to_stop or extra_clicks_after_ready <1 :
                        autoit .mouse_click ('left')
                        if ready_to_stop :
                            extra_clicks_after_ready +=1 
                        else :
                            ready_to_stop =True 
            time .sleep (0.5 )
            try :
                fish_name ,mutation =self .extract_fish_name_with_timeout ()
                self .send_webhook_message_with_timeout (fish_name ,mutation )
            except Exception as e :
                print (f'Error in fish name extraction or webhook: {e }')
                print ('Continuing with macro execution...')
            time .sleep (0.3 )
            try :
                close_x ,close_y =self .coordinates ['close_button']
                autoit .mouse_move (close_x ,close_y ,3 )
                time .sleep (0.7 )
                autoit .mouse_click ('left')
                self .apply_mouse_delay ()
                time .sleep (0.15 )
                print ('Close button clicked successfully')
            except Exception as e :
                print (f'Error clicking close button: {e }')
            self .failsafe_consecutive_count =0 
            return True 
        except Exception as e :
            print (f'Error in single fishing cycle: {e }')
            return False 

    def start_automation (self ):
        if self .running :
            return 
        if not self .toggle :
            self .toggle =True 
            self .running =True 
            self .first_loop =True 
            self .cycle_count =0 
            self .start_time =time .time ()
            self .auto_reconnect_manager .start_timer ()
            self .current_fish_count =0 
            self .automation_phase ='initialization'
            self .in_sell_cycle =False 
            self .external_script_running =False 
            if WIN32_AVAILABLE :
                try :

                    def enum_windows_callback (hwnd ,windows ):
                        if win32gui .IsWindowVisible (hwnd ):
                            window_text =win32gui .GetWindowText (hwnd )
                            if 'Roblox'in window_text :
                                windows .append (hwnd )
                        return True 
                    windows =[]
                    win32gui .EnumWindows (enum_windows_callback ,windows )
                    if windows :
                        win32gui .SetForegroundWindow (windows [0 ])
                except :
                    pass 
            self .thread =threading .Thread (target =self .mouse_automation_loop )
            self .thread .daemon =True 
            self .thread .start ()
            self .send_macro_started_notification ()

    def stop_automation (self ):
        if hasattr (self ,'external_script_running')and self .external_script_running :
            print ('WARNING: External script is currently running. Stop will interrupt navigation.')
        print ('STOP ACTIVATED - Stopping macro...')
        self .toggle =False 
        self .running =False 
        self .first_loop =True 
        self .automation_phase ='initialization'
        self .current_fish_count =0 
        self .in_sell_cycle =False 
        self .external_script_running =False 
        try :
            self .send_macro_stopped_notification ()
        except Exception as e :
            print (f'Warning: Failed to send stop webhook: {e }')
        if self .thread and self .thread .is_alive ():
            print ('Waiting for macro thread to stop...')
            try :
                self .thread .join (timeout =3 )
                if self .thread .is_alive ():
                    print ('Warning: Macro thread did not stop gracefully within timeout')
                    print ('Thread may still be running in background - this is usually safe')
                else :
                    print ('Automation thread stopped successfully')
            except Exception as e :
                print (f'Error during thread cleanup: {e }')
        print ('Stop completed')

class SolsScopeLinkDialog (QDialog ):
    """Dialog for selecting which SolsScope link to open"""
    def __init__ (self ,parent =None ):
        super ().__init__ (parent )
        self .selected_link =None 
        self .dont_show_again =False 
        self .setup_ui ()

    def setup_ui (self ):
        self .setWindowTitle ('Open SolsScope Link')
        self .setModal (True )
        self .setFixedSize (400 ,250 )

        layout =QVBoxLayout (self )
        layout .setSpacing (15 )
        layout .setContentsMargins (20 ,20 ,20 ,20 )


        title =QLabel ('Select which link to open:')
        title .setStyleSheet ('color: white; font-size: 14px; font-weight: bold;')
        layout .addWidget (title )


        self .button_group =QButtonGroup (self )

        self .github_radio =QRadioButton ('GitHub Repository')
        self .github_radio .setStyleSheet ('color: white; font-size: 12px;')
        self .github_radio .setChecked (True )
        self .button_group .addButton (self .github_radio ,0 )
        layout .addWidget (self .github_radio )

        self .discord_radio =QRadioButton ('Discord Support Server')
        self .discord_radio .setStyleSheet ('color: white; font-size: 12px;')
        self .button_group .addButton (self .discord_radio ,1 )
        layout .addWidget (self .discord_radio )

        layout .addStretch ()


        button_layout =QHBoxLayout ()
        button_layout .addStretch ()

        open_btn =QPushButton ('Open')
        open_btn .clicked .connect (self .accept )
        open_btn .setStyleSheet ('''
            QPushButton {
                background-color: #4a9eff;
                color: white;
                border: none;
                padding: 8px 20px;
                border-radius: 5px;
                font-weight: 600;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #357abd;
            }
            QPushButton:pressed {
                background-color: #2c5aa0;
            }
        ''')
        button_layout .addWidget (open_btn )

        cancel_btn =QPushButton ('Cancel')
        cancel_btn .clicked .connect (self .reject )
        cancel_btn .setStyleSheet ('''
            QPushButton {
                background-color: #6c757d;
                color: white;
                border: none;
                padding: 8px 20px;
                border-radius: 5px;
                font-weight: 600;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #5a6268;
            }
        ''')
        button_layout .addWidget (cancel_btn )

        layout .addLayout (button_layout )


        dont_show_layout =QHBoxLayout ()
        dont_show_layout .addStretch ()

        dont_show_btn =QPushButton ("Don't show again")
        dont_show_btn .clicked .connect (self .on_dont_show_again )
        dont_show_btn .setStyleSheet ('''
            QPushButton {
                background-color: transparent;
                color: #888888;
                border: 1px solid #555555;
                padding: 6px 16px;
                border-radius: 5px;
                font-weight: 600;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #3a3a3a;
                color: #aaaaaa;
                border-color: #666666;
            }
        ''')
        dont_show_layout .addWidget (dont_show_btn )
        dont_show_layout .addStretch ()

        layout .addLayout (dont_show_layout )


        self .setStyleSheet ('''
            QDialog {
                background-color: #2d2d2d;
            }
            QRadioButton {
                spacing: 8px;
            }
            QRadioButton::indicator {
                width: 16px;
                height: 16px;
                border-radius: 8px;
                border: 2px solid #4a9eff;
                background-color: #1a1a1a;
            }
            QRadioButton::indicator:checked {
                background-color: #4a9eff;
                border: 2px solid #357abd;
            }
        ''')

    def get_selected_link (self ):
        if self .github_radio .isChecked ():
            return 'https://github.com/bazthedev/SolsScope/releases/latest'
        elif self .discord_radio .isChecked ():
            return 'https://discord.gg/6cuCu6ymkX'
        return None 

    def on_dont_show_again (self ):
        """Handle 'Don't show again' button click with confirmation"""
        reply =QMessageBox .question (
        self ,
        'Confirm',
        """Are you sure you want to hide the SolsScope ad permanently?

You can always find SolsScope by searching online.""",
        QMessageBox .StandardButton .Yes |QMessageBox .StandardButton .No ,
        QMessageBox .StandardButton .No 
        )

        if reply ==QMessageBox .StandardButton .Yes :
            self .dont_show_again =True 
            self .reject ()


class AdBanner (QWidget ):
    """Advertisement banner for SolsScope macro"""
    def __init__ (self ,parent =None ):
        super ().__init__ (parent )
        self .parent_window =parent 
        self .setup_ui ()

    def setup_ui (self ):
        self .setMinimumHeight (100 )
        self .setMaximumHeight (120 )

        layout =QHBoxLayout (self )
        layout .setContentsMargins (15 ,10 ,15 ,10 )
        layout .setSpacing (15 )


        image_label =QLabel ()
        # Use resource_path so the image is loaded correctly when bundled with PyInstaller
        image_path =resource_path('SolsScope.png')
        if os .path .exists (image_path ):
            pixmap =QPixmap (image_path )
            scaled_pixmap =pixmap .scaled (80 ,80 ,Qt .AspectRatioMode .KeepAspectRatio ,Qt .TransformationMode .SmoothTransformation )
            image_label .setPixmap (scaled_pixmap )
        else :
            image_label .setText ('🎯')
            image_label .setStyleSheet ('font-size: 48px;')
        image_label .setFixedSize (80 ,80 )
        layout .addWidget (image_label ,0 ,Qt .AlignmentFlag .AlignCenter )


        content_layout =QVBoxLayout ()
        content_layout .setSpacing (5 )

        title_label =QLabel ('SolsScope - Single Account Macro (AD)')
        title_label .setStyleSheet ('color: #4a9eff; font-size: 13px; font-weight: bold;')
        content_layout .addWidget (title_label )

        desc_label =QLabel ('Looking for a single account macro for Jesters, Crafting, Obby, Auto Questboard, Biome Detection, Auto Pop when glitch, Discord Bot Remote Control, Auto Calibration (One Click Setup), and more? Then check out SolsScope! All of the features work simultaneously with a clean and easy to use GUI. Although there is no Fishing in SolsScope yet, we are working on adding it so you can enjoy all the features in one! For now you can continue using FishScope for fishing while SolsScope for everything else!')
        desc_label .setWordWrap (True )
        desc_label .setStyleSheet ('color: #e0e0e0; font-size: 10px;')
        content_layout .addWidget (desc_label )

        layout .addLayout (content_layout ,1 )


        buttons_layout =QVBoxLayout ()
        buttons_layout .setSpacing (5 )


        click_btn =QPushButton ('Learn More')
        click_btn .clicked .connect (self .on_ad_clicked )
        click_btn .setFixedWidth (100 )
        click_btn .setFixedHeight (35 )
        click_btn .setStyleSheet ('''
            QPushButton {
                background-color: #4a9eff;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: 600;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #357abd;
            }
            QPushButton:pressed {
                background-color: #2c5aa0;
            }
        ''')
        buttons_layout .addWidget (click_btn ,0 ,Qt .AlignmentFlag .AlignCenter )


        dont_show_btn =QPushButton ("Don't show again")
        dont_show_btn .clicked .connect (self .on_dont_show_clicked )
        dont_show_btn .setFixedWidth (100 )
        dont_show_btn .setFixedHeight (25 )
        dont_show_btn .setStyleSheet ('''
            QPushButton {
                background-color: transparent;
                color: #888888;
                border: 1px solid #555555;
                padding: 4px 8px;
                border-radius: 4px;
                font-weight: 600;
                font-size: 9px;
            }
            QPushButton:hover {
                background-color: #3a3a3a;
                color: #aaaaaa;
                border-color: #666666;
            }
        ''')
        buttons_layout .addWidget (dont_show_btn ,0 ,Qt .AlignmentFlag .AlignCenter )

        layout .addLayout (buttons_layout )


        close_btn =QPushButton ('✕')
        close_btn .clicked .connect (self .on_close_clicked )
        close_btn .setFixedSize (24 ,24 )
        close_btn .setStyleSheet ('''
            QPushButton {
                background-color: transparent;
                color: #888888;
                border: none;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                color: #ff4444;
                background-color: rgba(255, 68, 68, 0.1);
                border-radius: 12px;
            }
        ''')
        layout .addWidget (close_btn ,0 ,Qt .AlignmentFlag .AlignTop )


        self .setStyleSheet ('''
            AdBanner {
                background-color: #2d2d2d;
                border: 2px solid #4a9eff;
                border-radius: 8px;
            }
        ''')

    def on_ad_clicked (self ):
        """Handle ad click - show link selection dialog"""
        dialog =SolsScopeLinkDialog (self )
        result =dialog .exec ()

        if result ==QDialog .DialogCode .Accepted :
            link =dialog .get_selected_link ()
            if link :
                QDesktopServices .openUrl (QUrl (link ))


        if dialog .dont_show_again :
            self .save_hide_preference ()
            self .hide ()
            if self .parent_window :
                QMessageBox .information (
                self .parent_window ,
                'Ad Hidden',
                'The SolsScope ad has been hidden permanently.'
                )

    def on_close_clicked (self ):
        """Handle close button click - just hide the ad"""
        self .hide ()

    def on_dont_show_clicked (self ):
        """Handle 'Don't show again' button click with confirmation"""
        reply =QMessageBox .question (
        self .parent_window if self .parent_window else self ,
        'Confirm',
        """Are you sure you want to hide the SolsScope ad permanently?

    You can always find SolsScope by searching online.""",
        QMessageBox .StandardButton .Yes |QMessageBox .StandardButton .No ,
        QMessageBox .StandardButton .No 
        )

        if reply ==QMessageBox .StandardButton .Yes :
            self .save_hide_preference ()
            self .hide ()
            if self .parent_window :
                QMessageBox .information (
                self .parent_window ,
                'Ad Hidden',
                'The SolsScope ad has been hidden permanently.'
                )

    def save_hide_preference (self ):
        """Save the preference to hide the ad permanently"""
        try :
            config_file =os .path .join (os .getcwd (),'fishscopeconfig.json')
            config ={}


            if os .path .exists (config_file ):
                try :
                    with open (config_file ,'r')as f :
                        config =json .load (f )
                except :
                    pass 


            config ['hide_solsscope_ad']=True 


            with open (config_file ,'w')as f :
                json .dump (config ,f ,indent =4 )
        except Exception as e :
            print (f'Error saving ad hide preference: {e }')


class CalibrationOverlay (QWidget ):
    coordinate_selected =pyqtSignal (int ,int )
    calibration_cancelled =pyqtSignal ()

    def __init__ (self ,message ='Click to calibrate coordinate'):
        super ().__init__ ()
        self .message =message 
        self .mouse_pos =QPoint (0 ,0 )
        self .click_feedback_timer =QTimer ()
        self .click_feedback_timer .timeout .connect (self .hide_click_feedback )
        self .show_click_feedback =False 
        self .click_pos =QPoint (0 ,0 )
        self .animation_timer =QTimer ()
        self .animation_timer .timeout .connect (self .update_animation )
        self .animation_timer .start (50 )
        self .animation_phase =0 
        self .setup_overlay ()

    def setup_overlay (self ):
        self .setWindowFlags (Qt .WindowType .FramelessWindowHint |Qt .WindowType .WindowStaysOnTopHint |Qt .WindowType .Tool )
        self .setAttribute (Qt .WidgetAttribute .WA_TranslucentBackground )
        app =QApplication .instance ()
        desktop =app .primaryScreen ().virtualGeometry ()
        self .setGeometry (desktop )
        self .setMouseTracking (True )
        self .setCursor (Qt .CursorShape .CrossCursor )
        self .setFocusPolicy (Qt .FocusPolicy .StrongFocus )

    def update_animation (self ):
        self .animation_phase =(self .animation_phase +1 )%100 
        self .update ()

    def wrap_text (self ,text ,font_metrics ,max_width ):
        words =text .split ()
        lines =[]
        current_line =''
        for word in words :
            test_line =current_line +(' 'if current_line else '')+word 
            if font_metrics .boundingRect (test_line ).width ()<=max_width :
                current_line =test_line 
            else :
                if current_line :
                    lines .append (current_line )
                current_line =word 
        if current_line :
            lines .append (current_line )
        return lines if lines else [text ]

    def paintEvent (self ,event ):
        painter =QPainter (self )
        painter .setRenderHint (QPainter .RenderHint .Antialiasing )
        painter .fillRect (self .rect (),QColor (0 ,0 ,0 ,30 ))
        panel_width =min (max (700 ,self .width ()//2 ),self .width ()-40 )
        panel_height =160 
        panel_x =(self .width ()-panel_width )//2 
        panel_y =30 
        shadow_offset =4 
        shadow_gradient =QLinearGradient (0 ,panel_y +shadow_offset ,0 ,panel_y +panel_height +shadow_offset )
        shadow_gradient .setColorAt (0 ,QColor (0 ,0 ,0 ,60 ))
        shadow_gradient .setColorAt (1 ,QColor (0 ,0 ,0 ,15 ))
        painter .setBrush (QBrush (shadow_gradient ))
        painter .setPen (Qt .PenStyle .NoPen )
        painter .drawRoundedRect (panel_x +shadow_offset ,panel_y +shadow_offset ,panel_width ,panel_height ,12 ,12 )
        gradient =QLinearGradient (0 ,panel_y ,0 ,panel_y +panel_height )
        gradient .setColorAt (0 ,QColor (45 ,45 ,45 ,180 ))
        gradient .setColorAt (1 ,QColor (25 ,25 ,25 ,180 ))
        painter .setBrush (QBrush (gradient ))
        pulse_intensity =0.3 +0.2 *abs (50 -self .animation_phase )/50.0 
        border_color =QColor (int (80 +40 *pulse_intensity ),int (120 +30 *pulse_intensity ),200 )
        painter .setPen (QPen (border_color ,2 ))
        painter .drawRoundedRect (panel_x ,panel_y ,panel_width ,panel_height ,12 ,12 )
        glow_alpha =int (80 +40 *pulse_intensity )
        painter .setPen (QPen (QColor (100 ,140 ,220 ,glow_alpha ),1 ))
        painter .drawRoundedRect (panel_x +1 ,panel_y +1 ,panel_width -2 ,panel_height -2 ,11 ,11 )
        painter .setPen (QColor (255 ,255 ,255 ))
        painter .setFont (QFont ('Segoe UI',16 ,QFont .Weight .Bold ))
        text_padding =20 
        available_width =panel_width -text_padding *2 
        title_lines =self .wrap_text (self .message ,painter .fontMetrics (),available_width )
        title_y_start =panel_y +25 
        for i ,line in enumerate (title_lines ):
            line_rect =painter .fontMetrics ().boundingRect (line )
            title_x =panel_x +(panel_width -line_rect .width ())//2 
            title_y =title_y_start +i *20 
            painter .drawText (title_x ,title_y ,line )
        painter .setFont (QFont ('Segoe UI',11 ))
        instruction ='Click anywhere on the screen to set coordinate'
        inst_lines =self .wrap_text (instruction ,painter .fontMetrics (),available_width )
        inst_y_start =title_y_start +len (title_lines )*20 +15 
        painter .setPen (QColor (200 ,200 ,200 ))
        for i ,line in enumerate (inst_lines ):
            line_rect =painter .fontMetrics ().boundingRect (line )
            inst_x =panel_x +(panel_width -line_rect .width ())//2 
            inst_y =inst_y_start +i *15 
            painter .drawText (inst_x ,inst_y ,line )
        painter .setFont (QFont ('Segoe UI',10 ))
        esc_text ='Press ESC to cancel'
        esc_rect =painter .fontMetrics ().boundingRect (esc_text )
        esc_x =panel_x +(panel_width -esc_rect .width ())//2 
        esc_y =inst_y_start +len (inst_lines )*15 +15 
        painter .setPen (QColor (180 ,180 ,180 ))
        painter .drawText (esc_x ,esc_y ,esc_text )
        coord_text =f'Mouse Position: ({self .mouse_pos .x ()}, {self .mouse_pos .y ()})'
        painter .setFont (QFont ('Segoe UI',10 ,QFont .Weight .Bold ))
        coord_rect =painter .fontMetrics ().boundingRect (coord_text )
        coord_y =panel_y +panel_height -25 
        coord_box_width =min (coord_rect .width ()+20 ,panel_width -20 )
        coord_box_height =22 
        coord_box_x =panel_x +(panel_width -coord_box_width )//2 
        coord_box_y =coord_y -16 
        coord_gradient =QLinearGradient (0 ,coord_box_y ,0 ,coord_box_y +coord_box_height )
        coord_gradient .setColorAt (0 ,QColor (60 ,120 ,200 ,150 ))
        coord_gradient .setColorAt (1 ,QColor (40 ,80 ,160 ,150 ))
        painter .setBrush (QBrush (coord_gradient ))
        painter .setPen (QPen (QColor (100 ,150 ,255 ,120 ),1 ))
        painter .drawRoundedRect (coord_box_x ,coord_box_y ,coord_box_width ,coord_box_height ,6 ,6 )
        text_x =coord_box_x +(coord_box_width -coord_rect .width ())//2 
        painter .setPen (QColor (255 ,255 ,255 ))
        painter .drawText (text_x ,coord_y ,coord_text )
        if self .show_click_feedback :
            local_pos =self .mapFromGlobal (self .click_pos )
            center_x =local_pos .x ()
            center_y =local_pos .y ()
            painter .setPen (QPen (QColor (0 ,255 ,100 ,100 ),8 ))
            painter .drawEllipse (center_x -30 ,center_y -30 ,60 ,60 )
            click_gradient =QLinearGradient (center_x -25 ,center_y -25 ,center_x +25 ,center_y +25 )
            click_gradient .setColorAt (0 ,QColor (50 ,255 ,150 ,200 ))
            click_gradient .setColorAt (1 ,QColor (0 ,200 ,100 ,200 ))
            painter .setBrush (QBrush (click_gradient ))
            painter .setPen (QPen (QColor (0 ,255 ,100 ),3 ))
            painter .drawEllipse (center_x -25 ,center_y -25 ,50 ,50 )
            painter .setPen (QPen (QColor (255 ,255 ,255 ),2 ))
            painter .drawLine (center_x -15 ,center_y ,center_x +15 ,center_y )
            painter .drawLine (center_x ,center_y -15 ,center_x ,center_y +15 )
            painter .setBrush (QBrush (QColor (255 ,50 ,50 )))
            painter .setPen (QPen (QColor (255 ,255 ,255 ),1 ))
            painter .drawEllipse (center_x -3 ,center_y -3 ,6 ,6 )

    def mouseMoveEvent (self ,event ):
        self .mouse_pos =QCursor .pos ()
        self .update ()

    def mousePressEvent (self ,event ):
        if event .button ()==Qt .MouseButton .LeftButton :
            global_pos =QCursor .pos ()
            click_x =global_pos .x ()
            click_y =global_pos .y ()
            self .click_pos =global_pos 
            self .show_click_feedback =True 
            self .update ()
            self .click_feedback_timer .start (200 )
            self .selected_coords =(click_x ,click_y )

    def hide_click_feedback (self ):
        self .click_feedback_timer .stop ()
        self .show_click_feedback =False 
        x ,y =self .selected_coords 
        self .coordinate_selected .emit (x ,y )
        self .close ()

    def closeEvent (self ,event ):
        self .animation_timer .stop ()
        self .click_feedback_timer .stop ()
        super ().closeEvent (event )

    def keyPressEvent (self ,event ):
        if event .key ()==Qt .Key .Key_Escape :
            self .calibration_cancelled .emit ()
            self .close ()

    def showEvent (self ,event ):
        super ().showEvent (event )
        self .setFocus ()
        self .activateWindow ()
        self .raise_ ()

class AdvancedCalibrationWindow (QMainWindow ):

    def __init__ (self ,automation ,parent =None ):
        super ().__init__ (parent )
        self .automation =automation 
        self .parent_window =parent 
        self .calibrating =False 
        self .current_calibration =None 
        self .reel_bar_step =1 
        self .reel_bar_coords =[]
        self .coord_labels ={'fish_button':'Fish Button - Click to start fishing','white_diamond':'White Diamond - Pixel that turns white when fish is caught','shaded_area':'Shaded Area - Pixel location to sample bar color from (should be on the reel bar)','reel_bar':'Reel Bar - The Reel progress bar','completed_border':'Completed Border - A pixel of the completed screen border','close_button':'Close Button - Close the successfully caught fish','first_item':'First Item - Click the first item','confirm_button':'Confirm Button - Confirm the sale','mouse_idle_position':'Mouse Idle Position - Where mouse will normally be. Must be in a place without UI.'}
        self .coord_labels_widgets ={}
        self .setup_ui ()
        self .apply_clean_theme ()

    def setup_ui (self ):
        self .setWindowTitle ('Advanced Calibrations - FishScope Macro')
        self .setFixedSize (700 ,700 )
        if os .path .exists ('icon.ico'):
            self .setWindowIcon (QIcon ('icon.ico'))
        central_widget =QWidget ()
        self .setCentralWidget (central_widget )
        main_layout =QVBoxLayout (central_widget )
        main_layout .setSpacing (10 )
        main_layout .setContentsMargins (15 ,15 ,15 ,15 )
        header_layout =QVBoxLayout ()
        header_layout .setSpacing (4 )
        title_label =QLabel ('Advanced Calibrations')
        title_font =QFont ('Segoe UI',18 ,QFont .Weight .Bold )
        title_label .setFont (title_font )
        title_label .setAlignment (Qt .AlignmentFlag .AlignCenter )
        title_label .setStyleSheet ('color: #ffffff; margin: 4px 0;')
        header_layout .addWidget (title_label )
        subtitle_label =QLabel ('Customize coordinate positions for your specific setup')
        subtitle_font =QFont ('Segoe UI',10 )
        subtitle_label .setFont (subtitle_font )
        subtitle_label .setAlignment (Qt .AlignmentFlag .AlignCenter )
        subtitle_label .setStyleSheet ('color: #888888; margin-bottom: 10px;')
        header_layout .addWidget (subtitle_label )
        main_layout .addLayout (header_layout )
        scroll_area =QScrollArea ()
        scroll_area .setWidgetResizable (True )
        scroll_area .setVerticalScrollBarPolicy (Qt .ScrollBarPolicy .ScrollBarAsNeeded )
        scroll_area .setHorizontalScrollBarPolicy (Qt .ScrollBarPolicy .ScrollBarAlwaysOff )
        scroll_widget =QWidget ()
        scroll_layout =QVBoxLayout (scroll_widget )
        scroll_layout .setSpacing (10 )
        scroll_layout .setContentsMargins (0 ,0 ,0 ,0 )
        calibration_group =QGroupBox ('Coordinate Calibration')
        calibration_layout =QVBoxLayout (calibration_group )
        calibration_layout .setContentsMargins (12 ,15 ,12 ,12 )
        calibration_layout .setSpacing (6 )
        calib_info =QLabel ("Click 'Calibrate' for each coordinate to set up automation points")
        calib_info .setStyleSheet ('color: #888888; font-size: 11px; margin-bottom: 6px;')
        calibration_layout .addWidget (calib_info )
        scroll_area_calibration =QScrollArea ()
        scroll_area_calibration .setWidgetResizable (True )
        scroll_area_calibration .setVerticalScrollBarPolicy (Qt .ScrollBarPolicy .ScrollBarAsNeeded )
        scroll_area_calibration .setHorizontalScrollBarPolicy (Qt .ScrollBarPolicy .ScrollBarAlwaysOff )
        scroll_widget_calibration =QWidget ()
        scroll_layout_calibration =QVBoxLayout (scroll_widget_calibration )
        scroll_layout_calibration .setSpacing (3 )
        scroll_layout_calibration .setContentsMargins (4 ,4 ,4 ,4 )
        for coord_name ,description in self .coord_labels .items ():
            self .create_calibration_row (scroll_layout_calibration ,coord_name ,description )
        scroll_widget_calibration .setMinimumHeight (520 )
        scroll_area_calibration .setWidget (scroll_widget_calibration )
        calibration_layout .addWidget (scroll_area_calibration )
        scroll_layout .addWidget (calibration_group )
        close_layout =QHBoxLayout ()
        close_layout .addStretch ()
        close_btn =QPushButton ('Close')
        close_btn .clicked .connect (self .close )
        close_btn .setStyleSheet ('\n            QPushButton {\n                background-color: #6c757d;\n                color: white;\n                font-weight: 600;\n                padding: 10px 20px;\n                font-size: 13px;\n                border: none;\n                border-radius: 6px;\n                min-width: 100px;\n            }\n            QPushButton:hover {\n                background-color: #5a6268;\n            }\n            QPushButton:pressed {\n                background-color: #545b62;\n            }\n        ')
        close_layout .addWidget (close_btn )
        close_layout .addStretch ()
        scroll_layout .addLayout (close_layout )
        scroll_area .setWidget (scroll_widget )
        main_layout .addWidget (scroll_area )

    def create_calibration_row (self ,parent_layout ,coord_name ,description ):
        frame =QFrame ()
        frame .setFixedHeight (50 )
        frame .setStyleSheet ('\n            QFrame {\n                background-color: #2d2d2d;\n                border: 1px solid #404040;\n                border-radius: 6px;\n                margin: 1px;\n            }\n        ')
        frame_layout =QHBoxLayout (frame )
        frame_layout .setContentsMargins (12 ,8 ,12 ,8 )
        frame_layout .setSpacing (10 )
        info_layout =QVBoxLayout ()
        info_layout .setSpacing (2 )
        name_label =QLabel (description .split (' - ')[0 ])
        name_label .setStyleSheet ('color: #ffffff; font-weight: 600; font-size: 12px;')
        info_layout .addWidget (name_label )
        coord_label =QLabel (self .get_coord_text (coord_name ))
        coord_label .setStyleSheet ("color: #888888; font-size: 10px; font-family: 'Consolas', monospace;")
        info_layout .addWidget (coord_label )
        frame_layout .addLayout (info_layout )
        frame_layout .addStretch ()
        calib_btn =QPushButton ('Calibrate')
        calib_btn .clicked .connect (lambda :self .start_calibration (coord_name ))
        calib_btn .setFixedWidth (85 )
        calib_btn .setStyleSheet ('\n            QPushButton {\n                background-color: #4a9eff;\n                color: white;\n                border: none;\n                padding: 6px 12px;\n                border-radius: 5px;\n                font-weight: 600;\n                font-size: 11px;\n            }\n            QPushButton:hover {\n                background-color: #357abd;\n            }\n            QPushButton:pressed {\n                background-color: #2c5aa0;\n            }\n        ')
        frame_layout .addWidget (calib_btn )
        parent_layout .addWidget (frame )
        self .coord_labels_widgets [coord_name ]=coord_label 

    def get_coord_text (self ,coord_name ):
        if coord_name in self .automation .coordinates :
            coord =self .automation .coordinates [coord_name ]
            if coord_name in ['reel_bar','fish_caught_desc']and len (coord )==4 :
                return f'({coord [0 ]}, {coord [1 ]}, {coord [2 ]}, {coord [3 ]})'
            elif len (coord )==2 :
                return f'({coord [0 ]}, {coord [1 ]})'
        return 'Not set'

    def start_calibration (self ,coord_name ):
        if self .calibrating :
            return 
        self .calibrating =True 
        self .current_calibration =coord_name 
        self .hide ()
        if coord_name =='reel_bar':
            display_name =self .coord_labels [coord_name ].split (' - ')[0 ]
            message =f'{display_name } - Step 1: TOP-LEFT corner'
            self .reel_bar_step =1 
        elif coord_name =='fish_caught_desc':
            display_name =self .coord_labels [coord_name ].split (' - ')[0 ]
            message =f'Calibrating: {display_name } - Click the top-left corner of the description area'
            self .fish_caught_desc_step =1 
        else :
            display_name =self .coord_labels [coord_name ].split (' - ')[0 ]
            message =f'Calibrating: {display_name }'
        self .overlay =CalibrationOverlay (message )
        self .overlay .coordinate_selected .connect (self .on_calibration_click )
        self .overlay .calibration_cancelled .connect (self .cancel_calibration )
        self .overlay .show ()

    def on_calibration_click (self ,x ,y ):
        if self .current_calibration =='reel_bar':
            if self .reel_bar_step ==1 :
                self .reel_bar_coords =[x ,y ]
                self .reel_bar_step =2 
                self .overlay .close ()
                display_name =self .coord_labels ['reel_bar'].split (' - ')[0 ]
                message =f'{display_name } - Step 2: BOTTOM-RIGHT corner'
                self .overlay =CalibrationOverlay (message )
                self .overlay .coordinate_selected .connect (self .on_calibration_click )
                self .overlay .calibration_cancelled .connect (self .cancel_calibration )
                self .overlay .show ()
                return 
            else :
                new_coords =(self .reel_bar_coords [0 ],self .reel_bar_coords [1 ],x ,y )
                self .parent_window .update_coordinate_and_ui ('reel_bar',new_coords )
        elif self .current_calibration =='fish_caught_desc':
            if self .fish_caught_desc_step ==1 :
                self .fish_caught_desc_top_left =(x ,y )
                self .fish_caught_desc_step =2 
                self .overlay .close ()
                display_name =self .coord_labels ['fish_caught_desc'].split (' - ')[0 ]
                message =f'Calibrating: {display_name } - Click the bottom-right corner of the description area'
                self .overlay =CalibrationOverlay (message )
                self .overlay .coordinate_selected .connect (self .on_calibration_click )
                self .overlay .calibration_cancelled .connect (self .cancel_calibration )
                self .overlay .show ()
                return 
            else :
                self .fish_caught_desc_bottom_right =(x ,y )
                new_coords =(self .fish_caught_desc_top_left [0 ],self .fish_caught_desc_top_left [1 ],self .fish_caught_desc_bottom_right [0 ],self .fish_caught_desc_bottom_right [1 ])
                self .parent_window .update_coordinate_and_ui ('fish_caught_desc',new_coords )
        else :
            self .parent_window .update_coordinate_and_ui (self .current_calibration ,(x ,y ))
        self .overlay .close ()
        self .complete_calibration ()

    def complete_calibration (self ):
        self .calibrating =False 
        coord_label =self .coord_labels_widgets [self .current_calibration ]
        coord_label .setText (self .get_coord_text (self .current_calibration ))
        self .automation .save_calibration ()
        self .current_calibration =None 
        self .show ()
        self .raise_ ()
        self .activateWindow ()

    def cancel_calibration (self ):
        self .calibrating =False 
        self .current_calibration =None 
        self .show ()
        self .raise_ ()
        self .activateWindow ()

    def apply_clean_theme (self ):
        self .setStyleSheet ("\n            QMainWindow {\n                background-color: #1a1a1a;\n                color: #e0e0e0;\n                font-family: 'Segoe UI', Arial, sans-serif;\n            }\n            QLabel {\n                color: #e0e0e0;\n                background-color: transparent;\n            }\n            QPushButton {\n                background-color: #2d2d2d;\n                color: #e0e0e0;\n                border: 1px solid #404040;\n                padding: 8px 16px;\n                border-radius: 6px;\n                font-weight: 500;\n                font-size: 13px;\n            }\n            QPushButton:hover {\n                background-color: #3a3a3a;\n                border-color: #555555;\n            }\n            QPushButton:pressed {\n                background-color: #252525;\n                border-color: #606060;\n            }\n            QFrame {\n                background-color: #2d2d2d;\n                border: 1px solid #404040;\n                border-radius: 8px;\n            }\n            QScrollArea {\n                background-color: #1a1a1a;\n                border: 1px solid #404040;\n                border-radius: 6px;\n            }\n            QScrollArea QWidget {\n                background-color: #2d2d2d;\n            }\n            QGroupBox {\n                font-weight: 600;\n                font-size: 14px;\n                color: #e0e0e0;\n                border: 2px solid #404040;\n                border-radius: 8px;\n                margin-top: 10px;\n                padding-top: 10px;\n            }\n            QGroupBox::title {\n                subcontrol-origin: margin;\n                left: 10px;\n                padding: 0 8px 0 8px;\n                background-color: #1a1a1a;\n            }\n        ")

class CalibrationUI (QMainWindow ):

    def __init__ (self ,automation ):
        super ().__init__ ()
        self .automation =automation 
        self .calibrating =False 
        self .current_calibration =None 
        self .reel_bar_step =1 
        self .reel_bar_coords =[]
        self .advanced_calibration_window =None 
        self .tesseract_popup_shown =False 
        self .auto_updater =AutoUpdater (self )
        self .ui_update_timer =QTimer ()
        self .ui_update_timer .timeout .connect (self .update_auto_reconnect_display )
        self .ui_update_timer .start (1000 )
        try :
            success ,message ,calibration_data =self .automation .calibration_manager .update_calibrations (force_update =True )
            if success :
                print ('Calibrations downloaded')
            else :
                print (f'Calibrations failed to download, server might be down: {message }')
        except Exception as e :
            print (f'Warning: Error refreshing calibrations on launch: {e }')
        self .load_dynamic_calibrations ()
        self .setup_ui ()
        self .apply_clean_theme ()

    def load_dynamic_calibrations (self ):
        try :
            calibration_names =self .automation .calibration_manager .get_available_calibrations ()
            self .premade_calibrations ={}
            for name in calibration_names :
                coordinates =self .automation .calibration_manager .get_calibration_by_name (name )
                if coordinates :
                    converted_coords ={}
                    for coord_name ,coord_data in coordinates .items ():
                        if isinstance (coord_data ,list ):
                            converted_coords [coord_name ]=tuple (coord_data )
                        else :
                            converted_coords [coord_name ]=coord_data 
                    self .premade_calibrations [name ]=converted_coords 
            pass 
        except Exception as e :
            print (f'Error loading dynamic calibrations: {e }')
            self .premade_calibrations ={}

    def should_hide_ad (self ):
        """Check if user has chosen to hide the advertisement permanently"""
        try :
            config_file =self .automation .config_file 
            if os .path .exists (config_file ):
                with open (config_file ,'r')as f :
                    config_data =json .load (f )
                return config_data .get ('hide_solsscope_ad',False )
        except Exception as e :
            print (f'Error checking ad preference: {e }')
        return False 

    def update_coordinate_and_ui (self ,coord_name ,coord_value ):
        if coord_name in self .automation .coordinates :
            self .automation .coordinates [coord_name ]=coord_value 
            if hasattr (self ,'coord_labels_widgets')and coord_name in self .coord_labels_widgets :
                coord_label =self .coord_labels_widgets [coord_name ]
                coord_label .setText (self .get_coord_text (coord_name ))
            if hasattr (self ,'shop_coord_labels')and coord_name in self .shop_coord_labels :
                coord_label =self .shop_coord_labels [coord_name ]
                coord_label .setText (self .get_shop_coord_text (coord_name ))

    def on_webhook_url_changed (self ,text ):
        self .automation .webhook_url =text 
        self .automation .save_calibration ()

    def update_ignore_common (self ,state ):
        self .automation .ignore_common_fish =state ==Qt .CheckState .Checked .value 
        self .automation .save_calibration ()

    def update_ignore_uncommon (self ,state ):
        self .automation .ignore_uncommon_fish =state ==Qt .CheckState .Checked .value 
        self .automation .save_calibration ()

    def update_ignore_rare (self ,state ):
        self .automation .ignore_rare_fish =state ==Qt .CheckState .Checked .value 
        self .automation .save_calibration ()

    def update_ignore_trash (self ,state ):
        self .automation .ignore_trash =state ==Qt .CheckState .Checked .value 
        self .automation .save_calibration ()

    def update_webhook_roblox_detected (self ,state ):
        self .automation .webhook_roblox_detected =state ==Qt .CheckState .Checked .value 
        self .automation .save_calibration ()

    def update_webhook_roblox_reconnected (self ,state ):
        self .automation .webhook_roblox_reconnected =state ==Qt .CheckState .Checked .value 
        self .automation .save_calibration ()

    def update_webhook_macro_started (self ,state ):
        self .automation .webhook_macro_started =state ==Qt .CheckState .Checked .value 
        self .automation .save_calibration ()

    def update_webhook_macro_stopped (self ,state ):
        self .automation .webhook_macro_stopped =state ==Qt .CheckState .Checked .value 
        self .automation .save_calibration ()

    def update_webhook_auto_sell_started (self ,state ):
        self .automation .webhook_auto_sell_started =state ==Qt .CheckState .Checked .value 
        self .automation .save_calibration ()

    def update_webhook_back_to_fishing (self ,state ):
        self .automation .webhook_back_to_fishing =state ==Qt .CheckState .Checked .value 
        self .automation .save_calibration ()

    def update_webhook_failsafe_triggered (self ,state ):
        self .automation .webhook_failsafe_triggered =state ==Qt .CheckState .Checked .value 
        self .automation .save_calibration ()

    def update_webhook_error_notifications (self ,state ):
        self .automation .webhook_error_notifications =state ==Qt .CheckState .Checked .value 
        self .automation .save_calibration ()

    def update_webhook_phase_changes (self ,state ):
        self .automation .webhook_phase_changes =state ==Qt .CheckState .Checked .value 
        self .automation .save_calibration ()

    def update_webhook_cycle_completion (self ,state ):
        self .automation .webhook_cycle_completion =state ==Qt .CheckState .Checked .value 
        self .automation .save_calibration ()

    def test_webhook (self ):
        if not self .automation .webhook_url :
            msg =QMessageBox (self )
            msg .setWindowTitle ('No Webhook URL')
            msg .setText ('Please enter a webhook URL before testing.')
            msg .setIcon (QMessageBox .Icon .Warning )
            msg .setStyleSheet ('\n                QMessageBox {\n                    background-color: #2d2d2d;\n                    color: white;\n                }\n                QMessageBox QPushButton {\n                    background-color: #fd7e14;\n                    color: white;\n                    border: 1px solid #e8650e;\n                    padding: 8px 16px;\n                    border-radius: 4px;\n                    min-width: 80px;\n                    font-weight: bold;\n                }\n                QMessageBox QPushButton:hover {\n                    background-color: #e8650e;\n                }\n            ')
            msg .exec ()
            return 
        try :
            embed ={'title':'🧪 Test Webhook','color':1548984 ,'timestamp':datetime .now (timezone .utc ).isoformat ().replace ('+00:00','Z'),'fields':[{'name':'Status','value':'This is a test message to verify your webhook is working correctly!','inline':False }],'thumbnail':{'url':'https://raw.githubusercontent.com/cresqnt-sys/FishScope-Macro/main/fishscope-nobg.png'},'footer':{'text':'FishScope Macro - Test Message'}}
            data ={'embeds':[embed ]}
            response =requests .post (self .automation .webhook_url ,json =data )
            response .raise_for_status ()
            msg =QMessageBox (self )
            msg .setWindowTitle ('Test Sent')
            msg .setText ('Test webhook sent successfully! Check your Discord channel.')
            msg .setIcon (QMessageBox .Icon .Information )
            msg .setStyleSheet ('\n                QMessageBox {\n                    background-color: #2d2d2d;\n                    color: white;\n                }\n                QMessageBox QPushButton {\n                    background-color: #28a745;\n                    color: white;\n                    border: 1px solid #218838;\n                    padding: 8px 16px;\n                    border-radius: 4px;\n                    min-width: 80px;\n                    font-weight: bold;\n                }\n                QMessageBox QPushButton:hover {\n                    background-color: #218838;\n                }\n            ')
            msg .exec ()
        except Exception as e :
            msg =QMessageBox (self )
            msg .setWindowTitle ('Test Failed')
            msg .setText (f'Failed to send test webhook:\n{str (e )}')
            msg .setIcon (QMessageBox .Icon .Critical )
            msg .setStyleSheet ('\n                QMessageBox {\n                    background-color: #2d2d2d;\n                    color: white;\n                }\n                QMessageBox QPushButton {\n                    background-color: #dc3545;\n                    color: white;\n                    border: 1px solid #c82333;\n                    padding: 8px 16px;\n                    border-radius: 4px;\n                    min-width: 80px;\n                    font-weight: bold;\n                }\n                QMessageBox QPushButton:hover {\n                    background-color: #c82333;\n                }\n            ')
            msg .exec ()

    def on_tab_changed (self ,index ):
        tab_text =self .tab_widget .tabText (index )
        if tab_text =='Webhook':
            self .check_tesseract_on_webhook_tab ()

    def check_tesseract_on_webhook_tab (self ):
        if self .tesseract_popup_shown :
            return 
        try :
            if shutil .which ('tesseract'):
                return 
            if hasattr (pytesseract .pytesseract ,'tesseract_cmd')and pytesseract .pytesseract .tesseract_cmd :
                if os .path .exists (pytesseract .pytesseract .tesseract_cmd ):
                    return 
            if setup_tesseract ():
                return 
            self .show_tesseract_missing_popup ()
        except Exception as e :
            print (f'Error checking for Tesseract: {e }')
            self .show_tesseract_missing_popup ()

    def show_tesseract_missing_popup (self ):
        self .tesseract_popup_shown =True 
        msg =QMessageBox (self )
        msg .setWindowTitle ('Tesseract OCR Not Found')
        msg .setText ('Tesseract OCR is required for fish detection in webhooks!')
        msg .setInformativeText ('Tesseract OCR was not detected on your system. Without Tesseract, the macro cannot identify caught fish for webhook notifications.\n\nPlease download and install Tesseract from the link below, then restart the application.')
        msg .setDetailedText ('Download link: https://github.com/UB-Mannheim/tesseract/wiki\n\nInstallation instructions:\n1. Click the link above or visit the GitHub page\n2. Download the Windows installer for your system (32-bit or 64-bit)\n3. Run the installer and follow the installation wizard\n4. Restart FishScope Macro after installation\n\nThe macro will automatically detect Tesseract in common installation directories:\n• C:\\Program Files\\Tesseract-OCR\\\n• C:\\Program Files (x86)\\Tesseract-OCR\\\n• User AppData directories')
        msg .setIcon (QMessageBox .Icon .Warning )
        download_button =msg .addButton ('Open Download Page',QMessageBox .ButtonRole .ActionRole )
        ok_button =msg .addButton ('OK',QMessageBox .ButtonRole .AcceptRole )
        msg .setStyleSheet ('\n            QMessageBox {\n                background-color: #2d2d2d;\n                color: white;\n                min-width: 400px;\n            }\n            QMessageBox QPushButton {\n                background-color: #fd7e14;\n                color: white;\n                border: 1px solid #e8650e;\n                padding: 8px 16px;\n                border-radius: 4px;\n                min-width: 100px;\n                font-weight: bold;\n            }\n            QMessageBox QPushButton:hover {\n                background-color: #e8650e;\n            }\n            QMessageBox QLabel {\n                color: white;\n            }\n        ')
        result =msg .exec ()
        if msg .clickedButton ()==download_button :
            webbrowser .open ('https://github.com/UB-Mannheim/tesseract/wiki')

    def enable_all_notifications (self ):
        self .automation .webhook_roblox_detected =True 
        self .automation .webhook_roblox_reconnected =True 
        self .automation .webhook_automation_started =True 
        self .automation .webhook_automation_stopped =True 
        self .automation .webhook_auto_sell_started =True 
        self .automation .webhook_back_to_fishing =True 
        self .automation .webhook_failsafe_triggered =True 
        self .automation .webhook_error_notifications =True 
        self .automation .webhook_phase_changes =True 
        self .automation .webhook_cycle_completion =True 
        self .webhook_roblox_detected_checkbox .setChecked (True )
        self .webhook_roblox_reconnected_checkbox .setChecked (True )
        self .webhook_automation_started_checkbox .setChecked (True )
        self .webhook_automation_stopped_checkbox .setChecked (True )
        self .webhook_auto_sell_started_checkbox .setChecked (True )
        self .webhook_back_to_fishing_checkbox .setChecked (True )
        self .webhook_failsafe_triggered_checkbox .setChecked (True )
        self .webhook_error_notifications_checkbox .setChecked (True )
        self .webhook_phase_changes_checkbox .setChecked (True )
        self .webhook_cycle_completion_checkbox .setChecked (True )
        self .automation .save_calibration ()

    def disable_all_notifications (self ):
        self .automation .webhook_roblox_detected =False 
        self .automation .webhook_roblox_reconnected =False 
        self .automation .webhook_automation_started =False 
        self .automation .webhook_automation_stopped =False 
        self .automation .webhook_auto_sell_started =False 
        self .automation .webhook_back_to_fishing =False 
        self .automation .webhook_failsafe_triggered =False 
        self .automation .webhook_error_notifications =False 
        self .automation .webhook_phase_changes =False 
        self .automation .webhook_cycle_completion =False 
        self .webhook_roblox_detected_checkbox .setChecked (False )
        self .webhook_roblox_reconnected_checkbox .setChecked (False )
        self .webhook_automation_started_checkbox .setChecked (False )
        self .webhook_automation_stopped_checkbox .setChecked (False )
        self .webhook_auto_sell_started_checkbox .setChecked (False )
        self .webhook_back_to_fishing_checkbox .setChecked (False )
        self .webhook_failsafe_triggered_checkbox .setChecked (False )
        self .webhook_error_notifications_checkbox .setChecked (False )
        self .webhook_phase_changes_checkbox .setChecked (False )
        self .webhook_cycle_completion_checkbox .setChecked (False )
        self .automation .save_calibration ()

    def update_auto_sell_enabled (self ,state ):
        self .automation .auto_sell_enabled =state ==Qt .CheckState .Checked .value 
        if hasattr (self .automation ,'auto_sell_manager'):
            self .automation .auto_sell_manager .set_auto_sell_enabled (self .automation .auto_sell_enabled )
        self .automation .save_calibration ()

    def update_auto_sell_configuration (self ,text ):
        self .automation .auto_sell_configuration =text 
        self .automation .save_calibration ()

    def update_fish_count_until_auto_sell (self ,value ):
        self .automation .fish_count_until_auto_sell =value 
        self .automation .save_calibration ()

    def update_vip_paths (self ,state ):
        self .automation .use_vip_paths =state ==Qt .CheckState .Checked .value 
        self .automation .save_calibration ()

    def update_auto_reconnect_enabled (self ,state ):
        self .automation .auto_reconnect_enabled =state ==Qt .CheckState .Checked .value 
        self .automation .save_calibration ()

    def update_auto_reconnect_time (self ,value ):
        self .automation .auto_reconnect_time =value *60 
        self .automation .save_calibration ()

    def update_window_mode (self ,text ):
        self .automation .roblox_window_mode ='windowed'if text =='Windowed'else 'fullscreen'
        self .automation .save_calibration ()

    def update_backslash_sequence_delay (self ,value ):
        self .automation .backslash_sequence_delay =value 
        self .automation .save_calibration ()

    def test_auto_reconnect (self ):
        try :
            self .test_reconnect_btn .setEnabled (False )
            self .test_reconnect_btn .setText ('Testing...')
            from PyQt6 .QtWidgets import QMessageBox 
            reply =QMessageBox .question (self ,'Test Auto Reconnect','This will immediately trigger the auto reconnect sequence.\n\n• Roblox will be closed\n• Private server will be launched (if link provided)\n• Full reconnect sequence will execute\n\nContinue?',QMessageBox .StandardButton .Yes |QMessageBox .StandardButton .No ,QMessageBox .StandardButton .No )
            if reply ==QMessageBox .StandardButton .Yes :
                if self .automation .running :
                    self .automation .stop_automation ()
                import threading 

                def run_test ():
                    try :
                        success =self .automation .auto_reconnect_manager .test_auto_reconnect ()
                        if success :
                            print ('Test auto reconnect completed successfully')
                        else :
                            print ('Test auto reconnect failed')
                    except Exception as e :
                        print (f'Error during test auto reconnect: {e }')
                    finally :

                        def re_enable_button ():
                            self .test_reconnect_btn .setEnabled (True )
                            self .test_reconnect_btn .setText ('Test Auto Reconnect')
                        QTimer .singleShot (1000 ,re_enable_button )
                test_thread =threading .Thread (target =run_test ,daemon =True )
                test_thread .start ()
            else :
                self .test_reconnect_btn .setEnabled (True )
                self .test_reconnect_btn .setText ('Test Auto Reconnect')
        except Exception as e :
            print (f'Error in test_auto_reconnect: {e }')
            self .test_reconnect_btn .setEnabled (True )
            self .test_reconnect_btn .setText ('Test Auto Reconnect')

    def validate_private_server_link (self ,link ):
        link =link .strip ()
        if not link :
            return {'valid':True ,'message':'','type':'empty'}
        if 'share?code='in link and 'roblox.com'in link :
            return {'valid':False ,'message':'Share link detected - conversion required','type':'share_link','link':link }
        if 'privateServerLinkCode='in link and 'roblox.com'in link :
            return {'valid':True ,'message':'Valid private server link','type':'private_server'}
        if link .startswith ('roblox://')and 'placeId='in link :
            return {'valid':True ,'message':'Valid roblox:// protocol link','type':'roblox_protocol'}
        if 'roblox.com'in link :
            return {'valid':False ,'message':'Invalid Roblox link format','type':'invalid_roblox'}
        return {'valid':False ,'message':'Not a valid Roblox link','type':'invalid'}

    def show_share_link_instructions (self ,share_link ):
        msg =QMessageBox (self )
        msg .setWindowTitle ('Share Link Detected')
        msg .setIcon (QMessageBox .Icon .Information )
        instructions =f"Share Link Conversion Required\n\nYou've entered a share link:\n{share_link }\n\nTo convert this to a proper private server link, please follow these steps:\n\n1. Copy the share link you entered\n2. Open your web browser \n3. Paste the link in the address bar and press Enter\n4. Roblox will redirect you to the game page\n5. Copy the NEW URL from the address bar (it should contain 'privateServerLinkCode=')\n6. Come back here and paste the new URL\n\nThe new URL should look like:\nhttps://www.roblox.com/games/XXXXXXX/Game-Name?privateServerLinkCode=XXXXXXXXXX\n\nClick OK to acknowledge these instructions."
        msg .setText (instructions )
        msg .setStandardButtons (QMessageBox .StandardButton .Ok )
        msg .setStyleSheet ('\n            QMessageBox {\n                background-color: #2d2d2d;\n                color: white;\n                font-size: 12px;\n                min-width: 500px;\n            }\n            QMessageBox QPushButton {\n                background-color: #17a2b8;\n                color: white;\n                border: 1px solid #138496;\n                padding: 8px 16px;\n                border-radius: 4px;\n                font-weight: bold;\n                min-width: 80px;\n            }\n            QMessageBox QPushButton:hover {\n                background-color: #138496;\n            }\n        ')
        msg .exec ()

    def update_private_server_link (self ,text ):
        validation =self .validate_private_server_link (text )
        self .update_link_validation_display (validation )
        if validation ['type']=='share_link':
            self .private_server_input .clear ()
            self .show_share_link_instructions (validation ['link'])
            return 
        self .automation .roblox_private_server_link =text 
        self .automation .save_calibration ()

    def update_link_validation_display (self ,validation ):
        if not hasattr (self ,'link_status_label'):
            return 
        if validation ['type']=='empty':
            self .link_status_label .setText ('')
            self .link_status_label .hide ()
        elif validation ['valid']:
            self .link_status_label .setText ('✓ '+validation ['message'])
            self .link_status_label .setStyleSheet ('color: #28a745; font-size: 10px; font-weight: 500;')
            self .link_status_label .show ()
        else :
            self .link_status_label .setText ('⚠ '+validation ['message'])
            if validation ['type']=='share_link':
                self .link_status_label .setStyleSheet ('color: #fd7e14; font-size: 10px; font-weight: 500;')
            else :
                self .link_status_label .setStyleSheet ('color: #dc3545; font-size: 10px; font-weight: 500;')
            self .link_status_label .show ()

    def update_auto_reconnect_display (self ):
        if not hasattr (self ,'timer_label'):
            return 
        if not self .automation .auto_reconnect_enabled or not self .automation .running :
            self .timer_label .setText ('Time until reconnect: --:--')
            return 
        remaining_seconds =self .automation .get_auto_reconnect_time_remaining ()
        if remaining_seconds is None :
            self .timer_label .setText ('Time until reconnect: --:--')
            return 
        total_minutes =remaining_seconds /60 
        if remaining_seconds <=0 :
            self .timer_label .setText ('Time until reconnect: Reconnecting...')
            self .timer_label .setStyleSheet ('color: #dc3545; font-size: 11px; font-weight: 500;')
        elif remaining_seconds <=60 :
            seconds =int (remaining_seconds )
            self .timer_label .setText (f'Time until reconnect: {seconds } sec')
            self .timer_label .setStyleSheet ('color: #fd7e14; font-size: 11px; font-weight: 500;')
        else :
            self .timer_label .setText (f'Time until reconnect: {total_minutes :.1f} min')
            self .timer_label .setStyleSheet ('color: #4a9eff; font-size: 11px; font-weight: 500;')

    def update_mouse_delay_enabled (self ,state ):
        self .automation .mouse_delay_enabled =state ==Qt .CheckState .Checked .value 
        self .automation .save_calibration ()

    def update_mouse_delay_amount (self ,value ):
        self .automation .mouse_delay_ms =value 
        self .automation .save_calibration ()

    def update_failsafe_enabled (self ,state ):
        self .automation .failsafe_enabled =state ==Qt .CheckState .Checked .value 
        self .automation .save_calibration ()

    def update_failsafe_timeout (self ,value ):
        if value <20 :
            value =20 
            self .failsafe_timeout_spinbox .setValue (20 )
        self .automation .failsafe_timeout =value 
        self .automation .save_calibration ()

    def update_failsafe_reconnect_enabled (self ,state ):
        self .automation .failsafe_reconnect_enabled =state ==Qt .CheckState .Checked .value 
        self .automation .save_calibration ()

    def update_failsafe_reconnect_threshold (self ,value ):
        if value <2 :
            value =2 
            self .failsafe_reconnect_threshold_spinbox .setValue (2 )
        self .automation .failsafe_reconnect_threshold =value 
        self .automation .save_calibration ()

    def open_advanced_calibrations (self ):
        if self .advanced_calibration_window is None :
            self .advanced_calibration_window =AdvancedCalibrationWindow (self .automation ,self )
        self .advanced_calibration_window .show ()
        self .advanced_calibration_window .raise_ ()
        self .advanced_calibration_window .activateWindow ()

    def get_display_scale (self ):
        try :
            import ctypes 
            hdc =ctypes .windll .user32 .GetDC (0 )
            dpi =ctypes .windll .gdi32 .GetDeviceCaps (hdc ,88 )
            ctypes .windll .user32 .ReleaseDC (0 ,hdc )
            scale_percentage =round (dpi /96.0 *100 )
            return scale_percentage 
        except Exception :
            return 100 

    def check_display_scale (self ):
        scale =self .get_display_scale ()
        if scale !=100 :
            msg =QMessageBox (self )
            msg .setWindowTitle ('Display Scale Warning')
            msg .setText (f'Display Scale Detection\n\nYour current display scale is {scale }%.\n\nThis macro was designed for 100% display scale. Using a different scale may cause coordinate calibrations to be inaccurate. We have some scalled configurations available, but they may not work perfectly.\n\nIt is highly recommended to change your display scale to 100% for optimal performance.\n\nClick OK to open Display Settings.')
            msg .setIcon (QMessageBox .Icon .Warning )
            msg .setStandardButtons (QMessageBox .StandardButton .Ok |QMessageBox .StandardButton .Cancel )
            msg .setDefaultButton (QMessageBox .StandardButton .Ok )
            msg .setStyleSheet ('\n                QMessageBox {\n                    background-color: #2d2d2d;\n                    color: white;\n                    font-size: 12px;\n                }\n                QMessageBox QPushButton {\n                    background-color: #fd7e14;\n                    color: white;\n                    border: 1px solid #e8650e;\n                    padding: 8px 16px;\n                    border-radius: 4px;\n                    min-width: 80px;\n                    font-weight: bold;\n                }\n                QMessageBox QPushButton:hover {\n                    background-color: #e8650e;\n                }\n            ')
            result =msg .exec ()
            if result ==QMessageBox .StandardButton .Ok :
                self .open_display_settings ()

    def open_display_settings (self ):
        try :
            import subprocess 
            subprocess .run (['start','ms-settings:display'],shell =True ,check =False )
        except Exception as e :
            print (f'Failed to open display settings: {e }')
            try :
                subprocess .run (['control','desk.cpl'],shell =True ,check =False )
            except Exception as e2 :
                print (f'Failed to open legacy display settings: {e2 }')

    def show_first_launch_warning (self ):
        if not self .automation .first_launch_warning_shown :
            msg =QMessageBox (self )
            msg .setWindowTitle ('Important Warning - Custom Fonts')
            msg .setText ('⚠️ IMPORTANT WARNING ⚠️\n\nUsing Custom Fonts in Roblox will break this macro!\n\nThe macro relies on pixel detection in the shaded area of the fishing bar to determine the correct color for the reeling minigame. Custom fonts can block or interfere with these critical pixels, causing the macro to fail during the fishing process.\n\nPlease ensure that Custom Fonts are DISABLED in Blox/Fish/Voidstrap settings before using this macro.\n\nClick OK to acknowledge this warning.')
            msg .setIcon (QMessageBox .Icon .Warning )
            msg .setStandardButtons (QMessageBox .StandardButton .Ok )
            msg .setDefaultButton (QMessageBox .StandardButton .Ok )
            msg .setStyleSheet ('\n                QMessageBox {\n                    background-color: #2d2d2d;\n                    color: white;\n                    font-size: 12px;\n                    min-width: 500px;\n                }\n                QMessageBox QPushButton {\n                    background-color: #dc3545;\n                    color: white;\n                    border: 1px solid #c82333;\n                    padding: 8px 16px;\n                    border-radius: 4px;\n                    font-weight: bold;\n                    min-width: 80px;\n                }\n                QMessageBox QPushButton:hover {\n                    background-color: #c82333;\n                }\n                QMessageBox QPushButton:pressed {\n                    background-color: #bd2130;\n                }\n            ')
            result =msg .exec ()
            if result ==QMessageBox .StandardButton .Ok :
                self .automation .first_launch_warning_shown =True 
                self .automation .save_calibration ()

    def create_fish_desc_calibration_row (self ,parent_layout ):
        frame =QFrame ()
        frame .setFixedHeight (50 )
        frame .setStyleSheet ('\n            QFrame {\n                background-color: #2d2d2d;\n                border: 1px solid #404040;\n                border-radius: 6px;\n                margin: 1px;\n            }\n        ')
        frame_layout =QHBoxLayout (frame )
        frame_layout .setContentsMargins (12 ,8 ,12 ,8 )
        frame_layout .setSpacing (10 )
        info_layout =QVBoxLayout ()
        info_layout .setSpacing (2 )
        name_label =QLabel ('Fish Caught Description')
        name_label .setStyleSheet ('color: #ffffff; font-weight: 600; font-size: 12px;')
        info_layout .addWidget (name_label )
        coord_label =QLabel (self .get_fish_desc_coord_text ())
        coord_label .setStyleSheet ("color: #888888; font-size: 10px; font-family: 'Consolas', monospace;")
        info_layout .addWidget (coord_label )
        frame_layout .addLayout (info_layout )
        frame_layout .addStretch ()
        calib_btn =QPushButton ('Calibrate')
        calib_btn .clicked .connect (self .start_fish_desc_calibration )
        calib_btn .setFixedWidth (85 )
        calib_btn .setStyleSheet ('\n            QPushButton {\n                background-color: #4a9eff;\n                color: white;\n                border: none;\n                padding: 6px 12px;\n                border-radius: 5px;\n                font-weight: 600;\n                font-size: 11px;\n            }\n            QPushButton:hover {\n                background-color: #357abd;\n            }\n            QPushButton:pressed {\n                background-color: #2c5aa0;\n            }\n        ')
        frame_layout .addWidget (calib_btn )
        parent_layout .addWidget (frame )
        self .fish_desc_coord_label =coord_label 

    def create_shop_calibration_rows (self ,parent_layout ):
        shop_coords ={'sell_button':'Sell or Sell All Button','sell_fish_shop':'Sell Fish Shop','collection_button':'Collection Button','exit_collections':'Exit Collections','exit_fish_shop':'Exit Fish Shop'}
        self .shop_coord_labels ={}
        for coord_name ,display_name in shop_coords .items ():
            frame =QFrame ()
            frame .setFixedHeight (50 )
            frame .setStyleSheet ('\n                QFrame {\n                    background-color: #2d2d2d;\n                    border: 1px solid #404040;\n                    border-radius: 6px;\n                    margin: 1px;\n                }\n            ')
            frame_layout =QHBoxLayout (frame )
            frame_layout .setContentsMargins (12 ,8 ,12 ,8 )
            frame_layout .setSpacing (10 )
            info_layout =QVBoxLayout ()
            info_layout .setSpacing (2 )
            name_label =QLabel (display_name )
            name_label .setStyleSheet ('color: #ffffff; font-weight: 600; font-size: 12px;')
            info_layout .addWidget (name_label )
            coord_label =QLabel (self .get_shop_coord_text (coord_name ))
            coord_label .setStyleSheet ("color: #888888; font-size: 10px; font-family: 'Consolas', monospace;")
            info_layout .addWidget (coord_label )
            frame_layout .addLayout (info_layout )
            frame_layout .addStretch ()
            calib_btn =QPushButton ('Calibrate')
            calib_btn .clicked .connect (lambda checked ,name =coord_name :self .start_shop_calibration (name ))
            calib_btn .setFixedWidth (85 )
            calib_btn .setStyleSheet ('\n                QPushButton {\n                    background-color: #4a9eff;\n                    color: white;\n                    border: none;\n                    padding: 6px 12px;\n                    border-radius: 5px;\n                    font-weight: 600;\n                    font-size: 11px;\n                }\n                QPushButton:hover {\n                    background-color: #357abd;\n                }\n                QPushButton:pressed {\n                    background-color: #2c5aa0;\n                }\n            ')
            frame_layout .addWidget (calib_btn )
            parent_layout .addWidget (frame )
            self .shop_coord_labels [coord_name ]=coord_label 

    def get_shop_coord_text (self ,coord_name ):
        if coord_name in self .automation .coordinates :
            coord =self .automation .coordinates [coord_name ]
            if len (coord )==2 :
                return f'({coord [0 ]}, {coord [1 ]})'
        return 'Not set'

    def start_shop_calibration (self ,coord_name ):
        if self .calibrating :
            return 
        self .calibrating =True 
        self .current_calibration =coord_name 
        self .hide ()
        coord_display_names ={'sell_fish_shop':'Sell Fish Shop','collection_button':'Collection Button','exit_collections':'Exit Collections','exit_fish_shop':'Exit Fish Shop'}
        display_name =coord_display_names .get (coord_name ,coord_name )
        message =f'Calibrating: {display_name }'
        self .overlay =CalibrationOverlay (message )
        self .overlay .coordinate_selected .connect (self .on_shop_calibration_click )
        self .overlay .calibration_cancelled .connect (self .cancel_shop_calibration )
        self .overlay .show ()

    def on_shop_calibration_click (self ,x ,y ):
        self .automation .coordinates [self .current_calibration ]=(x ,y )
        self .overlay .close ()
        self .complete_shop_calibration ()

    def complete_shop_calibration (self ):
        self .calibrating =False 
        if self .current_calibration in self .shop_coord_labels :
            coord_label =self .shop_coord_labels [self .current_calibration ]
            coord_label .setText (self .get_shop_coord_text (self .current_calibration ))
        self .automation .save_calibration ()
        self .current_calibration =None 
        self .show ()
        self .raise_ ()
        self .activateWindow ()

    def cancel_shop_calibration (self ):
        self .calibrating =False 
        self .current_calibration =None 
        self .show ()
        self .raise_ ()
        self .activateWindow ()

    def get_fish_desc_coord_text (self ):
        if 'fish_caught_desc'in self .automation .coordinates :
            coord =self .automation .coordinates ['fish_caught_desc']
            if len (coord )==4 :
                return f'({coord [0 ]}, {coord [1 ]}, {coord [2 ]}, {coord [3 ]})'
        return 'Not set'

    def start_fish_desc_calibration (self ):
        if self .calibrating :
            return 
        self .calibrating =True 
        self .current_calibration ='fish_caught_desc'
        self .hide ()
        message ='Fish Caught Description - Click the top-left corner of the description area'
        self .fish_caught_desc_step =1 
        self .overlay =CalibrationOverlay (message )
        self .overlay .coordinate_selected .connect (self .on_fish_desc_calibration_click )
        self .overlay .calibration_cancelled .connect (self .cancel_fish_desc_calibration )
        self .overlay .show ()

    def on_fish_desc_calibration_click (self ,x ,y ):
        if self .fish_caught_desc_step ==1 :
            self .fish_caught_desc_top_left =(x ,y )
            self .fish_caught_desc_step =2 
            self .overlay .close ()
            message ='Fish Caught Description - Click the bottom-right corner of the description area'
            self .overlay =CalibrationOverlay (message )
            self .overlay .coordinate_selected .connect (self .on_fish_desc_calibration_click )
            self .overlay .calibration_cancelled .connect (self .cancel_fish_desc_calibration )
            self .overlay .show ()
            return 
        else :
            self .fish_caught_desc_bottom_right =(x ,y )
            self .automation .coordinates ['fish_caught_desc']=(self .fish_caught_desc_top_left [0 ],self .fish_caught_desc_top_left [1 ],self .fish_caught_desc_bottom_right [0 ],self .fish_caught_desc_bottom_right [1 ])
        self .overlay .close ()
        self .complete_fish_desc_calibration ()

    def complete_fish_desc_calibration (self ):
        self .calibrating =False 
        self .fish_desc_coord_label .setText (self .get_fish_desc_coord_text ())
        self .automation .save_calibration ()
        self .current_calibration =None 
        self .show ()
        self .raise_ ()
        self .activateWindow ()

    def cancel_fish_desc_calibration (self ):
        self .calibrating =False 
        self .current_calibration =None 
        self .show ()
        self .raise_ ()
        self .activateWindow ()

    def apply_clean_theme (self ):
        self .setStyleSheet ("\n            QMainWindow {\n                background-color: #1a1a1a;\n                color: #e0e0e0;\n                font-family: 'Segoe UI', Arial, sans-serif;\n            }\n            QLabel {\n                color: #e0e0e0;\n                background-color: transparent;\n            }\n            QPushButton {\n                background-color: #2d2d2d;\n                color: #e0e0e0;\n                border: 1px solid #404040;\n                padding: 8px 16px;\n                border-radius: 6px;\n                font-weight: 500;\n                font-size: 13px;\n            }\n            QPushButton:hover {\n                background-color: #3a3a3a;\n                border-color: #555555;\n            }\n            QPushButton:pressed {\n                background-color: #252525;\n                border-color: #606060;\n            }\n            QFrame {\n                background-color: #2d2d2d;\n                border: 1px solid #404040;\n                border-radius: 8px;\n            }\n            QScrollArea {\n                background-color: transparent;\n                border: none;\n            }\n            QScrollArea QWidget {\n                background-color: transparent;\n            }\n            QScrollBar:vertical {\n                background-color: #2d2d2d;\n                width: 12px;\n                border-radius: 6px;\n                margin: 0;\n            }\n            QScrollBar::handle:vertical {\n                background-color: #555555;\n                border-radius: 6px;\n                min-height: 20px;\n                margin: 2px;\n            }\n            QScrollBar::handle:vertical:hover {\n                background-color: #4a9eff;\n            }\n            QScrollBar::add-line:vertical,\n            QScrollBar::sub-line:vertical {\n                height: 0;\n                width: 0;\n            }\n            QGroupBox {\n                font-weight: 600;\n                font-size: 14px;\n                color: #e0e0e0;\n                border: 2px solid #404040;\n                border-radius: 8px;\n                margin-top: 10px;\n                padding-top: 10px;\n            }\n            QGroupBox::title {\n                subcontrol-origin: margin;\n                left: 10px;\n                padding: 0 8px 0 8px;\n                background-color: #1a1a1a;\n            }\n            QTabWidget::pane {\n                border: 1px solid #404040;\n                background-color: #2d2d2d;\n                border-radius: 6px;\n                margin-top: 2px;\n            }\n            QTabBar::tab {\n                background-color: #404040;\n                color: #e0e0e0;\n                border: 1px solid #555555;\n                padding: 10px 20px;\n                margin-right: 2px;\n                border-top-left-radius: 6px;\n                border-top-right-radius: 6px;\n                font-weight: 500;\n                min-width: 80px;\n                font-size: 12px;\n            }\n            QTabBar::tab:selected {\n                background-color: #4a9eff;\n                color: white;\n                font-weight: 600;\n                border-color: #4a9eff;\n            }\n            QTabBar::tab:hover:!selected {\n                background-color: #555555;\n                border-color: #666666;\n            }\n            QTabWidget::tab-bar {\n                alignment: center;\n            }\n            QLineEdit {\n                background-color: #2d2d2d;\n                color: #e0e0e0;\n                border: 1px solid #555555;\n                border-radius: 6px;\n                padding: 6px 10px;\n                font-size: 11px;\n            }\n            QLineEdit:focus {\n                border-color: #4a9eff;\n            }\n            QCheckBox {\n                color: #e0e0e0;\n                font-size: 11px;\n            }\n            QCheckBox::indicator {\n                width: 16px;\n                height: 16px;\n                border: 2px solid #555555;\n                border-radius: 3px;\n                background-color: #2d2d2d;\n            }\n            QCheckBox::indicator:checked {\n                background-color: #4a9eff;\n                border-color: #4a9eff;\n            }\n            QCheckBox::indicator:hover {\n                border-color: #4a9eff;\n            }\n            QSpinBox {\n                background-color: #2d2d2d;\n                color: #e0e0e0;\n                border: 1px solid #555555;\n                border-radius: 4px;\n                padding: 4px 8px;\n                font-size: 11px;\n                min-width: 80px;\n            }\n            QSpinBox:focus {\n                border-color: #4a9eff;\n            }\n            QSpinBox::up-button, QSpinBox::down-button {\n                background-color: #404040;\n                border: 1px solid #555555;\n                width: 16px;\n                border-radius: 2px;\n            }\n            QSpinBox::up-button:hover, QSpinBox::down-button:hover {\n                background-color: #4a9eff;\n            }\n            QComboBox {\n                background-color: #2d2d2d;\n                color: #e0e0e0;\n                border: 1px solid #555555;\n                border-radius: 6px;\n                padding: 6px 10px;\n                font-size: 11px;\n                min-width: 180px;\n            }\n            QComboBox:focus {\n                border-color: #4a9eff;\n            }\n            QComboBox::drop-down {\n                border: none;\n                width: 20px;\n            }\n            QComboBox::down-arrow {\n                image: none;\n                border-left: 5px solid transparent;\n                border-right: 5px solid transparent;\n                border-top: 5px solid #e0e0e0;\n                margin-right: 5px;\n            }\n            QComboBox QAbstractItemView {\n                background-color: #2d2d2d;\n                color: #e0e0e0;\n                border: 1px solid #555555;\n                selection-background-color: #4a9eff;\n                border-radius: 4px;\n            }\n        ")

    def setup_ui (self ):
        self .setWindowTitle ('FishScope Macro')
        self .setFixedSize (700 ,700 )
        if os .path .exists ('icon.ico'):
            self .setWindowIcon (QIcon ('icon.ico'))
        central_widget =QWidget ()
        self .setCentralWidget (central_widget )
        main_layout =QVBoxLayout (central_widget )
        main_layout .setSpacing (10 )
        main_layout .setContentsMargins (15 ,15 ,15 ,15 )
        header_layout =QVBoxLayout ()
        header_layout .setSpacing (4 )
        title_label =QLabel ('FishScope Macro')
        title_font =QFont ('Segoe UI',18 ,QFont .Weight .Bold )
        title_label .setFont (title_font )
        title_label .setAlignment (Qt .AlignmentFlag .AlignCenter )
        title_label .setStyleSheet ('color: #ffffff; margin: 4px 0;')
        header_layout .addWidget (title_label )
        subtitle_label =QLabel ('<a href="https://www.roblox.com/games/1980495071/Donations-D" style="color: #4a9eff; text-decoration: none;">Feel free to donate</a>')
        subtitle_font =QFont ('Segoe UI',8 )
        subtitle_label .setFont (subtitle_font )
        subtitle_label .setAlignment (Qt .AlignmentFlag .AlignCenter )
        subtitle_label .setStyleSheet ('color: #888888; margin-bottom: 6px;')
        subtitle_label .setOpenExternalLinks (True )
        header_layout .addWidget (subtitle_label )
        main_layout .addLayout (header_layout )
        self .tab_widget =QTabWidget ()
        self .tab_widget .setStyleSheet ('\n            QTabWidget::pane {\n                border: 1px solid #404040;\n                background-color: #2d2d2d;\n                border-radius: 6px;\n            }\n            QTabBar::tab {\n                background-color: #404040;\n                color: #e0e0e0;\n                border: 1px solid #555555;\n                padding: 8px 16px;\n                margin-right: 2px;\n                border-top-left-radius: 6px;\n                border-top-right-radius: 6px;\n                font-weight: 500;\n                min-width: 80px;\n            }\n            QTabBar::tab:selected {\n                background-color: #4a9eff;\n                color: white;\n                font-weight: 600;\n            }\n            QTabBar::tab:hover:!selected {\n                background-color: #555555;\n            }\n            QTabWidget::tab-bar {\n                alignment: center;\n            }\n        ')
        self .create_controls_tab ()
        self .create_auto_reconnect_tab ()
        self .create_calibrations_tab ()
        self .create_webhook_tab ()
        self .create_settings_tab ()
        self .tab_widget .currentChanged .connect (self .on_tab_changed )
        main_layout .addWidget (self .tab_widget )


        self .ad_banner =None 
        if not self .should_hide_ad ():
            self .ad_banner =AdBanner (self )
            main_layout .addWidget (self .ad_banner )

        footer_layout =QHBoxLayout ()
        footer_layout .setContentsMargins (0 ,10 ,0 ,0 )
        footer_layout .setSpacing (12 )
        creator_label =QLabel ('Created by: cresqnt')
        creator_label .setStyleSheet ('color: #888888; font-size: 11px;')
        footer_layout .addWidget (creator_label )
        discord_label =QLabel ('<a href="https://discord.gg/6cuCu6ymkX" style="color: #4a9eff; text-decoration: none;">Discord for help: .gg/6cuCu6ymkX</a>')
        discord_label .setStyleSheet ('color: #4a9eff; font-size: 9px;')
        discord_label .setOpenExternalLinks (True )
        footer_layout .addWidget (discord_label )
        footer_layout .addStretch ()
        main_layout .addLayout (footer_layout )
        QTimer .singleShot (1000 ,self .check_display_scale )

    def create_controls_tab (self ):
        controls_tab =QWidget ()
        self .tab_widget .addTab (controls_tab ,'Controls')
        scroll_area =QScrollArea ()
        scroll_area .setWidgetResizable (True )
        scroll_area .setVerticalScrollBarPolicy (Qt .ScrollBarPolicy .ScrollBarAsNeeded )
        scroll_area .setHorizontalScrollBarPolicy (Qt .ScrollBarPolicy .ScrollBarAlwaysOff )
        scroll_widget =QWidget ()
        scroll_layout =QVBoxLayout (scroll_widget )
        scroll_layout .setSpacing (15 )
        scroll_layout .setContentsMargins (10 ,10 ,10 ,10 )
        control_group =QGroupBox ('Macro Controls')
        control_layout =QVBoxLayout (control_group )
        control_layout .setSpacing (8 )
        control_layout .setContentsMargins (12 ,15 ,12 ,12 )
        hotkey_info_layout =QHBoxLayout ()
        hotkey_info_layout .setSpacing (15 )
        f1_label =QLabel ('F1 - Start')
        f1_label .setStyleSheet ('color: #28a745; font-weight: 500; font-size: 11px;')
        hotkey_info_layout .addWidget (f1_label )
        f2_label =QLabel ('F2 - Stop')
        f2_label .setStyleSheet ('color: #dc3545; font-weight: 500; font-size: 11px;')
        hotkey_info_layout .addWidget (f2_label )
        hotkey_info_layout .addStretch ()
        control_layout .addLayout (hotkey_info_layout )
        button_layout =QHBoxLayout ()
        button_layout .setSpacing (10 )
        self .start_btn =QPushButton ('Start Macro')
        self .start_btn .clicked .connect (self .automation .start_automation )
        self .start_btn .setStyleSheet ('\n            QPushButton {\n                background-color: #28a745;\n                color: white;\n                font-weight: 600;\n                padding: 10px 20px;\n                font-size: 13px;\n                border: none;\n                border-radius: 6px;\n            }\n            QPushButton:hover {\n                background-color: #218838;\n            }\n            QPushButton:pressed {\n                background-color: #1e7e34;\n            }\n        ')
        button_layout .addWidget (self .start_btn )
        self .stop_btn =QPushButton ('Stop Macro')
        self .stop_btn .clicked .connect (self .automation .stop_automation )
        self .stop_btn .setStyleSheet ('\n            QPushButton {\n                background-color: #dc3545;\n                color: white;\n                font-weight: 600;\n                padding: 10px 20px;\n                font-size: 13px;\n                border: none;\n                border-radius: 6px;\n            }\n            QPushButton:hover {\n                background-color: #c82333;\n            }\n            QPushButton:pressed {\n                background-color: #bd2130;\n            }\n        ')
        button_layout .addWidget (self .stop_btn )
        control_layout .addLayout (button_layout )
        scroll_layout .addWidget (control_group )
        notice_group =QGroupBox ('Important Setup Notice')
        notice_layout =QVBoxLayout (notice_group )
        notice_layout .setContentsMargins (12 ,15 ,12 ,12 )
        notice_layout .setSpacing (8 )
        notice_text =QLabel ("⚠️ BEFORE STARTING THE MACRO:\n\n1. Configure Calibrations: Go to the 'Calibrations' tab and apply the correct calibration for your screen resolution and scale. Without proper calibrations, the macro will not work correctly. By defult, the macro is calibrated for the SELL ALL mode, in order to use the Legacy Sell mode you must calibrate the Sell Button to the normal sell button.\n\n2. Adjust Settings: Visit the 'Settings' tab to configure auto-sell behavior and other preferences according to your needs.\n\nAuto-Sell Modes Explained:\n• Legacy Mode: Sells the same number of times as fish caught (e.g., catch 10 fish → sell 10 times)\n• Sell All Mode (Recommended): Always sells exactly 51 times regardless of fish count\n\n✅ Sell All mode is recommended because it significantly reduces the time spent selling fish, making the macro more efficient overall.")
        notice_text .setWordWrap (True )
        notice_text .setStyleSheet ('\n            QLabel {\n                color: #f8d7da;\n                background-color: #2c1b1e;\n                border: 2px solid #721c24;\n                border-radius: 6px;\n                padding: 12px;\n                font-size: 11px;\n                line-height: 1.4;\n                margin: 2px;\n            }\n        ')
        notice_layout .addWidget (notice_text )
        scroll_layout .addWidget (notice_group )
        scroll_layout .addStretch ()
        scroll_area .setWidget (scroll_widget )
        tab_layout =QVBoxLayout (controls_tab )
        tab_layout .setContentsMargins (0 ,0 ,0 ,0 )
        tab_layout .addWidget (scroll_area )

    def create_auto_reconnect_tab (self ):
        auto_reconnect_tab =QWidget ()
        self .tab_widget .addTab (auto_reconnect_tab ,'Auto Reconnect')
        scroll_area =QScrollArea ()
        scroll_area .setWidgetResizable (True )
        scroll_area .setVerticalScrollBarPolicy (Qt .ScrollBarPolicy .ScrollBarAsNeeded )
        scroll_area .setHorizontalScrollBarPolicy (Qt .ScrollBarPolicy .ScrollBarAlwaysOff )
        scroll_widget =QWidget ()
        scroll_layout =QVBoxLayout (scroll_widget )
        scroll_layout .setSpacing (15 )
        scroll_layout .setContentsMargins (10 ,10 ,10 ,10 )
        auto_reconnect_group =QGroupBox ('Auto Reconnect Settings')
        auto_reconnect_layout =QVBoxLayout (auto_reconnect_group )
        auto_reconnect_layout .setSpacing (8 )
        auto_reconnect_layout .setContentsMargins (12 ,15 ,12 ,12 )
        reconnect_info =QLabel ('Automatically reconnect to private server after specified time')
        reconnect_info .setStyleSheet ('color: #888888; font-size: 11px; margin-bottom: 6px;')
        auto_reconnect_layout .addWidget (reconnect_info )
        reconnect_enable_layout =QHBoxLayout ()
        reconnect_enable_layout .setSpacing (10 )
        self .auto_reconnect_checkbox =QCheckBox ('Enable Auto Reconnect')
        self .auto_reconnect_checkbox .setChecked (self .automation .auto_reconnect_enabled )
        self .auto_reconnect_checkbox .stateChanged .connect (self .update_auto_reconnect_enabled )
        self .auto_reconnect_checkbox .setStyleSheet ('\n            QCheckBox {\n                color: #e0e0e0;\n                font-size: 11px;\n                font-weight: 500;\n            }\n            QCheckBox::indicator {\n                width: 16px;\n                height: 16px;\n                border: 2px solid #555555;\n                border-radius: 3px;\n                background-color: #2d2d2d;\n            }\n            QCheckBox::indicator:checked {\n                background-color: #4a9eff;\n                border-color: #4a9eff;\n            }\n        ')
        reconnect_enable_layout .addWidget (self .auto_reconnect_checkbox )
        reconnect_enable_layout .addStretch ()
        auto_reconnect_layout .addLayout (reconnect_enable_layout )
        time_layout =QHBoxLayout ()
        time_layout .setSpacing (10 )
        time_label =QLabel ('Time until reconnect (minutes):')
        time_label .setStyleSheet ('color: #e0e0e0; font-size: 11px;')
        time_layout .addWidget (time_label )
        self .auto_reconnect_time_spinbox =QSpinBox ()
        self .auto_reconnect_time_spinbox .setRange (1 ,1440 )
        self .auto_reconnect_time_spinbox .setValue (self .automation .auto_reconnect_time //60 )
        self .auto_reconnect_time_spinbox .setSuffix (' min')
        self .auto_reconnect_time_spinbox .valueChanged .connect (self .update_auto_reconnect_time )
        self .auto_reconnect_time_spinbox .setStyleSheet ('\n            QSpinBox {\n                background-color: #2d2d2d;\n                color: #e0e0e0;\n                border: 1px solid #555555;\n                border-radius: 4px;\n                padding: 4px 8px;\n                font-size: 11px;\n                min-width: 80px;\n            }\n            QSpinBox::up-button, QSpinBox::down-button {\n                background-color: #404040;\n                border: 1px solid #555555;\n                width: 16px;\n            }\n            QSpinBox::up-button:hover, QSpinBox::down-button:hover {\n                background-color: #4a9eff;\n            }\n        ')
        time_layout .addWidget (self .auto_reconnect_time_spinbox )
        time_layout .addStretch ()
        auto_reconnect_layout .addLayout (time_layout )
        server_link_layout =QVBoxLayout ()
        server_link_layout .setSpacing (5 )
        server_link_label =QLabel ('Roblox Private Server Link:')
        server_link_label .setStyleSheet ('color: #e0e0e0; font-size: 11px;')
        server_link_layout .addWidget (server_link_label )
        self .private_server_input =QLineEdit ()
        self .private_server_input .setPlaceholderText ('https://www.roblox.com/games/16732694052?privateServerLinkCode=...')
        self .private_server_input .setText (self .automation .roblox_private_server_link )
        self .private_server_input .textChanged .connect (self .update_private_server_link )
        self .private_server_input .setStyleSheet ('\n            QLineEdit {\n                background-color: #2d2d2d;\n                color: #e0e0e0;\n                border: 1px solid #555555;\n                border-radius: 6px;\n                padding: 6px 10px;\n                font-size: 11px;\n            }\n            QLineEdit:focus {\n                border-color: #4a9eff;\n            }\n        ')
        server_link_layout .addWidget (self .private_server_input )
        self .link_status_label =QLabel ('')
        self .link_status_label .setStyleSheet ('color: #888888; font-size: 10px;')
        self .link_status_label .hide ()
        server_link_layout .addWidget (self .link_status_label )
        auto_reconnect_layout .addLayout (server_link_layout )
        window_mode_layout =QHBoxLayout ()
        window_mode_layout .setSpacing (10 )
        window_mode_label =QLabel ('Roblox when launched:')
        window_mode_label .setStyleSheet ('color: #e0e0e0; font-size: 11px;')
        window_mode_layout .addWidget (window_mode_label )
        self .window_mode_combo =QComboBox ()
        self .window_mode_combo .addItems (['Windowed','Fullscreen'])
        self .window_mode_combo .setCurrentText ('Windowed'if self .automation .roblox_window_mode =='windowed'else 'Fullscreen')
        self .window_mode_combo .currentTextChanged .connect (self .update_window_mode )
        self .window_mode_combo .setStyleSheet ('\n            QComboBox {\n                background-color: #3d3d3d;\n                border: 1px solid #555555;\n                border-radius: 4px;\n                padding: 4px 8px;\n                color: #e0e0e0;\n                font-size: 11px;\n                min-width: 100px;\n            }\n            QComboBox::drop-down {\n                border: none;\n                width: 20px;\n            }\n            QComboBox::down-arrow {\n                image: none;\n                border-left: 5px solid transparent;\n                border-right: 5px solid transparent;\n                border-top: 5px solid #888888;\n                margin-right: 5px;\n            }\n            QComboBox QAbstractItemView {\n                background-color: #3d3d3d;\n                border: 1px solid #555555;\n                selection-background-color: #4a9eff;\n                color: #e0e0e0;\n            }\n        ')
        window_mode_layout .addWidget (self .window_mode_combo )
        window_mode_layout .addStretch ()
        auto_reconnect_layout .addLayout (window_mode_layout )
        delay_layout =QHBoxLayout ()
        delay_layout .setSpacing (10 )
        delay_label =QLabel ('Key sequence delay (seconds):')
        delay_label .setStyleSheet ('color: #e0e0e0; font-size: 11px;')
        delay_layout .addWidget (delay_label )
        self .backslash_delay_spinbox =QSpinBox ()
        self .backslash_delay_spinbox .setRange (60 ,300 )
        self .backslash_delay_spinbox .setValue (int (self .automation .backslash_sequence_delay ))
        self .backslash_delay_spinbox .setSuffix (' sec')
        self .backslash_delay_spinbox .valueChanged .connect (self .update_backslash_sequence_delay )
        self .backslash_delay_spinbox .setStyleSheet ('\n            QSpinBox {\n                background-color: #3d3d3d;\n                border: 1px solid #555555;\n                border-radius: 4px;\n                padding: 4px 8px;\n                color: #e0e0e0;\n                font-size: 11px;\n                min-width: 100px;\n            }\n            QSpinBox:focus {\n                border-color: #4a9eff;\n            }\n            QSpinBox::up-button, QSpinBox::down-button {\n                background-color: #404040;\n                border: 1px solid #555555;\n                width: 16px;\n                border-radius: 2px;\n            }\n            QSpinBox::up-button:hover, QSpinBox::down-button:hover {\n                background-color: #4a9eff;\n            }\n        ')
        delay_layout .addWidget (self .backslash_delay_spinbox )
        delay_layout .addStretch ()
        auto_reconnect_layout .addLayout (delay_layout )
        timer_layout =QHBoxLayout ()
        timer_layout .setSpacing (10 )
        self .timer_label =QLabel ('Time until reconnect: --:--')
        self .timer_label .setStyleSheet ('color: #4a9eff; font-size: 11px; font-weight: 500;')
        timer_layout .addWidget (self .timer_label )
        timer_layout .addStretch ()
        auto_reconnect_layout .addLayout (timer_layout )
        test_reconnect_layout =QHBoxLayout ()
        test_reconnect_layout .setSpacing (10 )
        self .test_reconnect_btn =QPushButton ('Test Auto Reconnect')
        self .test_reconnect_btn .clicked .connect (self .test_auto_reconnect )
        self .test_reconnect_btn .setStyleSheet ('\n            QPushButton {\n                background-color: #17a2b8;\n                color: white;\n                font-weight: 500;\n                padding: 8px 16px;\n                font-size: 11px;\n                border: none;\n                border-radius: 5px;\n                min-width: 140px;\n            }\n            QPushButton:hover {\n                background-color: #138496;\n            }\n            QPushButton:pressed {\n                background-color: #117a8b;\n            }\n            QPushButton:disabled {\n                background-color: #6c757d;\n                color: #adb5bd;\n            }\n        ')
        test_reconnect_layout .addWidget (self .test_reconnect_btn )
        test_reconnect_layout .addStretch ()
        auto_reconnect_layout .addLayout (test_reconnect_layout )
        reconnect_note =QLabel ('ℹ Once reconnected, detects RobloxPlayerBeta.exe → waits → sends \\ → Enter → \\ sequence. If you have a slow PC, increase the delay time.')
        reconnect_note .setStyleSheet ('color: #888888; font-size: 9px; font-style: italic; margin-top: 5px;')
        auto_reconnect_layout .addWidget (reconnect_note )
        scroll_layout .addWidget (auto_reconnect_group )
        if self .automation .roblox_private_server_link :
            validation =self .validate_private_server_link (self .automation .roblox_private_server_link )
            self .update_link_validation_display (validation )
        scroll_layout .addStretch ()
        scroll_area .setWidget (scroll_widget )
        tab_layout =QVBoxLayout (auto_reconnect_tab )
        tab_layout .setContentsMargins (0 ,0 ,0 ,0 )
        tab_layout .addWidget (scroll_area )

    def create_calibrations_tab (self ):
        calibrations_tab =QWidget ()
        self .tab_widget .addTab (calibrations_tab ,'Calibrations')
        scroll_area =QScrollArea ()
        scroll_area .setWidgetResizable (True )
        scroll_area .setVerticalScrollBarPolicy (Qt .ScrollBarPolicy .ScrollBarAsNeeded )
        scroll_area .setHorizontalScrollBarPolicy (Qt .ScrollBarPolicy .ScrollBarAlwaysOff )
        scroll_widget =QWidget ()
        scroll_layout =QVBoxLayout (scroll_widget )
        scroll_layout .setSpacing (15 )
        scroll_layout .setContentsMargins (10 ,10 ,10 ,10 )
        premade_group =QGroupBox ('Premade Calibrations')
        premade_layout =QVBoxLayout (premade_group )
        premade_layout .setContentsMargins (12 ,15 ,12 ,12 )
        premade_layout .setSpacing (8 )
        premade_info =QLabel ('Select a premade calibration to quickly set up coordinates')
        premade_info .setStyleSheet ('color: #888888; font-size: 11px; margin-bottom: 6px;')
        premade_layout .addWidget (premade_info )
        premade_selector_layout =QHBoxLayout ()
        premade_selector_layout .setSpacing (10 )
        premade_label =QLabel ('Configuration:')
        premade_label .setStyleSheet ('color: #e0e0e0; font-weight: 500;')
        premade_selector_layout .addWidget (premade_label )
        self .premade_combo =QComboBox ()
        self .calibration_combo =self .premade_combo 
        self .premade_combo .addItem ('Select a premade calibration...')
        for config_name in self .premade_calibrations .keys ():
            self .premade_combo .addItem (config_name )
        self .premade_combo .setStyleSheet ('\n            QComboBox {\n                background-color: #2d2d2d;\n                color: #e0e0e0;\n                border: 1px solid #555555;\n                border-radius: 6px;\n                padding: 6px 10px;\n                font-size: 11px;\n                min-width: 180px;\n            }\n            QComboBox::drop-down {\n                border: none;\n                width: 20px;\n            }\n            QComboBox::down-arrow {\n                image: none;\n                border-left: 5px solid transparent;\n                border-right: 5px solid transparent;\n                border-top: 5px solid #e0e0e0;\n                margin-right: 5px;\n            }\n            QComboBox QAbstractItemView {\n                background-color: #2d2d2d;\n                color: #e0e0e0;\n                border: 1px solid #555555;\n                selection-background-color: #4a9eff;\n            }\n        ')
        premade_selector_layout .addWidget (self .premade_combo )
        apply_premade_btn =QPushButton ('Apply')
        apply_premade_btn .clicked .connect (self .apply_premade_calibration )
        apply_premade_btn .setStyleSheet ('\n            QPushButton {\n                background-color: #28a745;\n                color: white;\n                font-weight: 600;\n                padding: 6px 14px;\n                font-size: 11px;\n                border: none;\n                border-radius: 6px;\n                min-width: 80px;\n            }\n            QPushButton:hover {\n                background-color: #218838;\n            }\n            QPushButton:pressed {\n                background-color: #1e7e34;\n            }\n        ')
        premade_selector_layout .addWidget (apply_premade_btn )
        premade_selector_layout .addStretch ()
        premade_layout .addLayout (premade_selector_layout )
        scroll_layout .addWidget (premade_group )
        calibrations_group =QGroupBox ('Custom Calibrations')
        calibrations_layout =QVBoxLayout (calibrations_group )
        calibrations_layout .setContentsMargins (12 ,15 ,12 ,12 )
        calibrations_layout .setSpacing (8 )
        calibrations_info =QLabel ('Configure coordinate positions for specific game elements')
        calibrations_info .setStyleSheet ('color: #888888; font-size: 11px; margin-bottom: 6px;')
        calibrations_layout .addWidget (calibrations_info )
        fish_desc_label =QLabel ('Fish Caught Description:')
        fish_desc_label .setStyleSheet ('color: #e0e0e0; font-weight: 500; margin-top: 5px;')
        calibrations_layout .addWidget (fish_desc_label )
        fish_desc_info =QLabel ('Calibrate the area where fish descriptions appear for OCR extraction')
        fish_desc_info .setStyleSheet ('color: #888888; font-size: 11px; margin-bottom: 6px;')
        calibrations_layout .addWidget (fish_desc_info )
        self .create_fish_desc_calibration_row (calibrations_layout )
        calibrations_layout .addWidget (QLabel (''))
        shop_label =QLabel ('Shop & Sell Calibrations:')
        shop_label .setStyleSheet ('color: #e0e0e0; font-weight: 500; margin-top: 10px;')
        calibrations_layout .addWidget (shop_label )
        shop_info =QLabel ('Configure coordinates for shop interactions and selling')
        shop_info .setStyleSheet ('color: #888888; font-size: 11px; margin-bottom: 6px;')
        calibrations_layout .addWidget (shop_info )
        self .create_shop_calibration_rows (calibrations_layout )
        config_io_layout =QHBoxLayout ()
        config_io_layout .setSpacing (10 )
        config_io_label =QLabel ('Config Import/Export:')
        config_io_label .setStyleSheet ('color: #e0e0e0; font-weight: 500; font-size: 12px;')
        config_io_layout .addWidget (config_io_label )
        import_config_btn =QPushButton ('Import Config')
        import_config_btn .clicked .connect (self .import_config )
        import_config_btn .setStyleSheet ('\n            QPushButton {\n                background-color: #17a2b8;\n                color: white;\n                font-weight: 600;\n                padding: 8px 16px;\n                font-size: 12px;\n                border: none;\n                border-radius: 6px;\n                min-width: 120px;\n            }\n            QPushButton:hover {\n                background-color: #138496;\n            }\n            QPushButton:pressed {\n                background-color: #0f6674;\n            }\n        ')
        config_io_layout .addWidget (import_config_btn )
        export_config_btn =QPushButton ('Export Config')
        export_config_btn .clicked .connect (self .export_config )
        export_config_btn .setStyleSheet ('\n            QPushButton {\n                background-color: #28a745;\n                color: white;\n                font-weight: 600;\n                padding: 8px 16px;\n                font-size: 12px;\n                border: none;\n                border-radius: 6px;\n                min-width: 120px;\n            }\n            QPushButton:hover {\n                background-color: #218838;\n            }\n            QPushButton:pressed {\n                background-color: #1e7e34;\n            }\n        ')
        config_io_layout .addWidget (export_config_btn )
        config_io_layout .addStretch ()
        calibrations_layout .addLayout (config_io_layout )
        calibrations_layout .addWidget (QLabel (''))
        advanced_calib_layout =QHBoxLayout ()
        advanced_calib_layout .setSpacing (10 )
        advanced_calib_label =QLabel ('Advanced (Custom Calibrations):')
        advanced_calib_label .setStyleSheet ('color: #e0e0e0; font-weight: 500; font-size: 12px;')
        advanced_calib_layout .addWidget (advanced_calib_label )
        advanced_calib_btn =QPushButton ('Open Calibrations')
        advanced_calib_btn .clicked .connect (self .open_advanced_calibrations )
        advanced_calib_btn .setStyleSheet ('\n            QPushButton {\n                background-color: #6f42c1;\n                color: white;\n                font-weight: 600;\n                padding: 8px 16px;\n                font-size: 12px;\n                border: none;\n                border-radius: 6px;\n                min-width: 140px;\n            }\n            QPushButton:hover {\n                background-color: #5a32a3;\n            }\n            QPushButton:pressed {\n                background-color: #4c2a85;\n            }\n        ')
        advanced_calib_layout .addWidget (advanced_calib_btn )
        advanced_calib_layout .addStretch ()
        calibrations_layout .addLayout (advanced_calib_layout )
        scroll_layout .addWidget (calibrations_group )
        buttons_layout =QHBoxLayout ()
        buttons_layout .setSpacing (12 )
        buttons_layout .addStretch ()
        reset_btn =QPushButton ('Reset to Defaults')
        reset_btn .clicked .connect (self .reset_to_defaults )
        reset_btn .setStyleSheet ('\n            QPushButton {\n                background-color: #fd7e14;\n                color: white;\n                font-weight: 600;\n                padding: 8px 16px;\n                font-size: 12px;\n                border: none;\n                border-radius: 6px;\n            }\n            QPushButton:hover {\n                background-color: #e8650e;\n            }\n            QPushButton:pressed {\n                background-color: #d15a0a;\n            }\n        ')
        buttons_layout .addWidget (reset_btn )
        buttons_layout .addStretch ()
        scroll_layout .addLayout (buttons_layout )
        scroll_layout .addStretch ()
        scroll_area .setWidget (scroll_widget )
        tab_layout =QVBoxLayout (calibrations_tab )
        tab_layout .setContentsMargins (0 ,0 ,0 ,0 )
        tab_layout .addWidget (scroll_area )

    def create_webhook_tab (self ):
        webhook_tab =QWidget ()
        self .tab_widget .addTab (webhook_tab ,'Webhook')
        scroll_area =QScrollArea ()
        scroll_area .setWidgetResizable (True )
        scroll_area .setVerticalScrollBarPolicy (Qt .ScrollBarPolicy .ScrollBarAsNeeded )
        scroll_area .setHorizontalScrollBarPolicy (Qt .ScrollBarPolicy .ScrollBarAlwaysOff )
        scroll_widget =QWidget ()
        scroll_layout =QVBoxLayout (scroll_widget )
        scroll_layout .setSpacing (15 )
        scroll_layout .setContentsMargins (10 ,10 ,10 ,10 )
        webhook_group =QGroupBox ('Webhook Settings')
        webhook_layout =QVBoxLayout (webhook_group )
        webhook_layout .setContentsMargins (12 ,15 ,12 ,12 )
        webhook_layout .setSpacing (8 )
        webhook_label =QLabel ('Webhook URL:')
        webhook_label .setStyleSheet ('color: #e0e0e0; font-weight: 500;')
        webhook_layout .addWidget (webhook_label )
        self .webhook_input =QLineEdit ()
        self .webhook_input .setPlaceholderText ('Enter your discord webhook URL here')
        self .webhook_input .setText (self .automation .webhook_url )
        self .webhook_input .setStyleSheet ('\n            QLineEdit {\n                background-color: #2d2d2d;\n                color: #e0e0e0;\n                border: 1px solid #555555;\n                border-radius: 6px;\n                padding: 6px 10px;\n                font-size: 11px;\n            }\n        ')
        self .webhook_input .textChanged .connect (self .on_webhook_url_changed )
        webhook_layout .addWidget (self .webhook_input )
        scroll_layout .addWidget (webhook_group )
        notifications_group =QGroupBox ('Notification Types')
        notifications_layout =QVBoxLayout (notifications_group )
        notifications_layout .setContentsMargins (12 ,15 ,12 ,12 )
        notifications_layout .setSpacing (8 )
        notifications_info =QLabel ('Enable or disable specific types of webhook notifications')
        notifications_info .setStyleSheet ('color: #888888; font-size: 11px; margin-bottom: 8px;')
        notifications_layout .addWidget (notifications_info )
        process_section =QLabel ('Process & Connection Events')
        process_section .setStyleSheet ('color: #4a9eff; font-weight: 600; font-size: 12px; margin-top: 8px;')
        notifications_layout .addWidget (process_section )
        self .webhook_roblox_detected_checkbox =QCheckBox ('Roblox Process Detected')
        self .webhook_roblox_detected_checkbox .setChecked (self .automation .webhook_roblox_detected )
        self .webhook_roblox_detected_checkbox .stateChanged .connect (self .update_webhook_roblox_detected )
        self .webhook_roblox_detected_checkbox .setStyleSheet (self .get_checkbox_style ())
        notifications_layout .addWidget (self .webhook_roblox_detected_checkbox )
        self .webhook_roblox_reconnected_checkbox =QCheckBox ('Roblox Reconnection Events')
        self .webhook_roblox_reconnected_checkbox .setChecked (self .automation .webhook_roblox_reconnected )
        self .webhook_roblox_reconnected_checkbox .stateChanged .connect (self .update_webhook_roblox_reconnected )
        self .webhook_roblox_reconnected_checkbox .setStyleSheet (self .get_checkbox_style ())
        notifications_layout .addWidget (self .webhook_roblox_reconnected_checkbox )
        automation_section =QLabel ('Macro Events')
        automation_section .setStyleSheet ('color: #28a745; font-weight: 600; font-size: 12px; margin-top: 12px;')
        notifications_layout .addWidget (automation_section )
        self .webhook_macro_started_checkbox =QCheckBox ('Macro Started')
        self .webhook_macro_started_checkbox .setChecked (self .automation .webhook_macro_started )
        self .webhook_macro_started_checkbox .stateChanged .connect (self .update_webhook_macro_started )
        self .webhook_macro_started_checkbox .setStyleSheet (self .get_checkbox_style ())
        notifications_layout .addWidget (self .webhook_macro_started_checkbox )
        self .webhook_macro_stopped_checkbox =QCheckBox ('Macro Stopped')
        self .webhook_macro_stopped_checkbox .setChecked (self .automation .webhook_macro_stopped )
        self .webhook_macro_stopped_checkbox .stateChanged .connect (self .update_webhook_macro_stopped )
        self .webhook_macro_stopped_checkbox .setStyleSheet (self .get_checkbox_style ())
        notifications_layout .addWidget (self .webhook_macro_stopped_checkbox )
        self .webhook_auto_sell_started_checkbox =QCheckBox ('Auto-Sell Started')
        self .webhook_auto_sell_started_checkbox .setChecked (self .automation .webhook_auto_sell_started )
        self .webhook_auto_sell_started_checkbox .stateChanged .connect (self .update_webhook_auto_sell_started )
        self .webhook_auto_sell_started_checkbox .setStyleSheet (self .get_checkbox_style ())
        notifications_layout .addWidget (self .webhook_auto_sell_started_checkbox )
        self .webhook_back_to_fishing_checkbox =QCheckBox ('Back to Fishing')
        self .webhook_back_to_fishing_checkbox .setChecked (self .automation .webhook_back_to_fishing )
        self .webhook_back_to_fishing_checkbox .stateChanged .connect (self .update_webhook_back_to_fishing )
        self .webhook_back_to_fishing_checkbox .setStyleSheet (self .get_checkbox_style ())
        notifications_layout .addWidget (self .webhook_back_to_fishing_checkbox )
        system_section =QLabel ('System Events')
        system_section .setStyleSheet ('color: #fd7e14; font-weight: 600; font-size: 12px; margin-top: 12px;')
        notifications_layout .addWidget (system_section )
        self .webhook_failsafe_triggered_checkbox =QCheckBox ('Failsafe Triggered')
        self .webhook_failsafe_triggered_checkbox .setChecked (self .automation .webhook_failsafe_triggered )
        self .webhook_failsafe_triggered_checkbox .stateChanged .connect (self .update_webhook_failsafe_triggered )
        self .webhook_failsafe_triggered_checkbox .setStyleSheet (self .get_checkbox_style ())
        notifications_layout .addWidget (self .webhook_failsafe_triggered_checkbox )
        self .webhook_error_notifications_checkbox =QCheckBox ('Error Notifications')
        self .webhook_error_notifications_checkbox .setChecked (self .automation .webhook_error_notifications )
        self .webhook_error_notifications_checkbox .stateChanged .connect (self .update_webhook_error_notifications )
        self .webhook_error_notifications_checkbox .setStyleSheet (self .get_checkbox_style ())
        notifications_layout .addWidget (self .webhook_error_notifications_checkbox )
        progress_section =QLabel ('Progress & Status Events')
        progress_section .setStyleSheet ('color: #6f42c1; font-weight: 600; font-size: 12px; margin-top: 12px;')
        notifications_layout .addWidget (progress_section )
        self .webhook_phase_changes_checkbox =QCheckBox ('Phase Changes (Can be spammy)')
        self .webhook_phase_changes_checkbox .setChecked (self .automation .webhook_phase_changes )
        self .webhook_phase_changes_checkbox .stateChanged .connect (self .update_webhook_phase_changes )
        self .webhook_phase_changes_checkbox .setStyleSheet (self .get_checkbox_style ())
        notifications_layout .addWidget (self .webhook_phase_changes_checkbox )
        self .webhook_cycle_completion_checkbox =QCheckBox ('Cycle Completions')
        self .webhook_cycle_completion_checkbox .setChecked (self .automation .webhook_cycle_completion )
        self .webhook_cycle_completion_checkbox .stateChanged .connect (self .update_webhook_cycle_completion )
        self .webhook_cycle_completion_checkbox .setStyleSheet (self .get_checkbox_style ())
        notifications_layout .addWidget (self .webhook_cycle_completion_checkbox )
        scroll_layout .addWidget (notifications_group )
        filtering_group =QGroupBox ('Fish Filtering')
        filtering_layout =QVBoxLayout (filtering_group )
        filtering_layout .setContentsMargins (12 ,15 ,12 ,12 )
        filtering_layout .setSpacing (8 )
        filtering_info =QLabel ('Choose which fish types to ignore in webhook notifications')
        filtering_info .setStyleSheet ('color: #888888; font-size: 11px; margin-bottom: 8px;')
        filtering_layout .addWidget (filtering_info )
        self .ignore_common_checkbox =QCheckBox ('Ignore Common Fish')
        self .ignore_common_checkbox .setChecked (self .automation .ignore_common_fish )
        self .ignore_common_checkbox .stateChanged .connect (self .update_ignore_common )
        self .ignore_common_checkbox .setStyleSheet (self .get_checkbox_style ())
        filtering_layout .addWidget (self .ignore_common_checkbox )
        self .ignore_uncommon_checkbox =QCheckBox ('Ignore Uncommon Fish')
        self .ignore_uncommon_checkbox .setChecked (self .automation .ignore_uncommon_fish )
        self .ignore_uncommon_checkbox .stateChanged .connect (self .update_ignore_uncommon )
        self .ignore_uncommon_checkbox .setStyleSheet (self .get_checkbox_style ())
        filtering_layout .addWidget (self .ignore_uncommon_checkbox )
        self .ignore_rare_checkbox =QCheckBox ('Ignore Rare Fish')
        self .ignore_rare_checkbox .setChecked (self .automation .ignore_rare_fish )
        self .ignore_rare_checkbox .stateChanged .connect (self .update_ignore_rare )
        self .ignore_rare_checkbox .setStyleSheet (self .get_checkbox_style ())
        filtering_layout .addWidget (self .ignore_rare_checkbox )
        self .ignore_trash_checkbox =QCheckBox ('Ignore Trash')
        self .ignore_trash_checkbox .setChecked (self .automation .ignore_trash )
        self .ignore_trash_checkbox .stateChanged .connect (self .update_ignore_trash )
        self .ignore_trash_checkbox .setStyleSheet (self .get_checkbox_style ())
        filtering_layout .addWidget (self .ignore_trash_checkbox )
        scroll_layout .addWidget (filtering_group )
        webhook_controls_group =QGroupBox ('Webhook Controls')
        webhook_controls_layout =QVBoxLayout (webhook_controls_group )
        webhook_controls_layout .setContentsMargins (12 ,15 ,12 ,12 )
        webhook_controls_layout .setSpacing (8 )
        controls_info =QLabel ('Quick actions for webhook management')
        controls_info .setStyleSheet ('color: #888888; font-size: 11px; margin-bottom: 8px;')
        webhook_controls_layout .addWidget (controls_info )
        controls_button_layout =QHBoxLayout ()
        controls_button_layout .setSpacing (10 )
        test_webhook_btn =QPushButton ('Test Webhook')
        test_webhook_btn .clicked .connect (self .test_webhook )
        test_webhook_btn .setStyleSheet ('\n            QPushButton {\n                background-color: #17a2b8;\n                color: white;\n                font-weight: 600;\n                padding: 8px 16px;\n                font-size: 11px;\n                border: none;\n                border-radius: 6px;\n            }\n            QPushButton:hover {\n                background-color: #138496;\n            }\n            QPushButton:pressed {\n                background-color: #0f6674;\n            }\n        ')
        controls_button_layout .addWidget (test_webhook_btn )
        enable_all_btn =QPushButton ('Enable All')
        enable_all_btn .clicked .connect (self .enable_all_notifications )
        enable_all_btn .setStyleSheet ('\n            QPushButton {\n                background-color: #28a745;\n                color: white;\n                font-weight: 600;\n                padding: 8px 16px;\n                font-size: 11px;\n                border: none;\n                border-radius: 6px;\n            }\n            QPushButton:hover {\n                background-color: #218838;\n            }\n            QPushButton:pressed {\n                background-color: #1e7e34;\n            }\n        ')
        controls_button_layout .addWidget (enable_all_btn )
        disable_all_btn =QPushButton ('Disable All')
        disable_all_btn .clicked .connect (self .disable_all_notifications )
        disable_all_btn .setStyleSheet ('\n            QPushButton {\n                background-color: #dc3545;\n                color: white;\n                font-weight: 600;\n                padding: 8px 16px;\n                font-size: 11px;\n                border: none;\n                border-radius: 6px;\n            }\n            QPushButton:hover {\n                background-color: #c82333;\n            }\n            QPushButton:pressed {\n                background-color: #bd2130;\n            }\n        ')
        controls_button_layout .addWidget (disable_all_btn )
        controls_button_layout .addStretch ()
        webhook_controls_layout .addLayout (controls_button_layout )
        scroll_layout .addWidget (webhook_controls_group )
        scroll_layout .addStretch ()
        scroll_area .setWidget (scroll_widget )
        tab_layout =QVBoxLayout (webhook_tab )
        tab_layout .setContentsMargins (0 ,0 ,0 ,0 )
        tab_layout .addWidget (scroll_area )

    def get_checkbox_style (self ):
        return '\n            QCheckBox {\n                color: #e0e0e0;\n                font-size: 11px;\n                margin: 3px 0;\n            }\n            QCheckBox::indicator {\n                width: 16px;\n                height: 16px;\n                border: 2px solid #555555;\n                border-radius: 3px;\n                background-color: #2d2d2d;\n            }\n            QCheckBox::indicator:checked {\n                background-color: #4a9eff;\n                border-color: #4a9eff;\n            }\n        '

    def create_settings_tab (self ):
        settings_tab =QWidget ()
        self .tab_widget .addTab (settings_tab ,'Settings')
        scroll_area =QScrollArea ()
        scroll_area .setWidgetResizable (True )
        scroll_area .setVerticalScrollBarPolicy (Qt .ScrollBarPolicy .ScrollBarAsNeeded )
        scroll_area .setHorizontalScrollBarPolicy (Qt .ScrollBarPolicy .ScrollBarAlwaysOff )
        scroll_widget =QWidget ()
        scroll_layout =QVBoxLayout (scroll_widget )
        scroll_layout .setSpacing (15 )
        scroll_layout .setContentsMargins (10 ,10 ,10 ,10 )
        auto_sell_group =QGroupBox ('Auto-Sell Configuration')
        auto_sell_layout =QVBoxLayout (auto_sell_group )
        auto_sell_layout .setContentsMargins (12 ,15 ,12 ,12 )
        auto_sell_layout .setSpacing (8 )
        auto_sell_info =QLabel ('Configure automatic selling behavior')
        auto_sell_info .setStyleSheet ('color: #888888; font-size: 11px; margin-bottom: 6px;')
        auto_sell_layout .addWidget (auto_sell_info )
        self .auto_sell_checkbox =QCheckBox ('Enable Auto-Sell')
        self .auto_sell_checkbox .setChecked (self .automation .auto_sell_enabled )
        self .auto_sell_checkbox .stateChanged .connect (self .update_auto_sell_enabled )
        self .auto_sell_checkbox .setStyleSheet ('\n            QCheckBox {\n                color: #e0e0e0;\n                font-size: 11px;\n                margin: 3px 0;\n            }\n            QCheckBox::indicator {\n                width: 16px;\n                height: 16px;\n                border: 2px solid #555555;\n                border-radius: 3px;\n                background-color: #2d2d2d;\n            }\n            QCheckBox::indicator:checked {\n                background-color: #28a745;\n                border-color: #28a745;\n            }\n        ')
        auto_sell_layout .addWidget (self .auto_sell_checkbox )
        config_layout =QHBoxLayout ()
        config_layout .setSpacing (10 )
        config_label =QLabel ('Auto-Sell Mode:')
        config_label .setStyleSheet ('color: #e0e0e0; font-size: 11px;')
        config_layout .addWidget (config_label )
        self .auto_sell_config_combo =QComboBox ()
        self .auto_sell_config_combo .addItems (['Legacy','Sell All (Recommended)'])
        self .auto_sell_config_combo .setCurrentText (self .automation .auto_sell_configuration )
        self .auto_sell_config_combo .currentTextChanged .connect (self .update_auto_sell_configuration )
        self .auto_sell_config_combo .setStyleSheet ('\n            QComboBox {\n                background-color: #2d2d2d;\n                color: #e0e0e0;\n                border: 1px solid #555555;\n                border-radius: 6px;\n                padding: 6px 10px;\n                font-size: 11px;\n                min-width: 180px;\n            }\n            QComboBox::drop-down {\n                border: none;\n                width: 20px;\n            }\n            QComboBox::down-arrow {\n                image: none;\n                border-left: 5px solid transparent;\n                border-right: 5px solid transparent;\n                border-top: 5px solid #e0e0e0;\n                margin-right: 5px;\n            }\n            QComboBox QAbstractItemView {\n                background-color: #2d2d2d;\n                color: #e0e0e0;\n                border: 1px solid #555555;\n                selection-background-color: #4a9eff;\n            }\n        ')
        config_layout .addWidget (self .auto_sell_config_combo )
        config_layout .addStretch ()
        auto_sell_layout .addLayout (config_layout )
        config_explanation =QLabel ('• Legacy: Sells the same number of times as fish caught\n• Sell All: Always sells exactly 51 times (recommended)')
        config_explanation .setWordWrap (True )
        config_explanation .setStyleSheet ('\n            QLabel {\n                color: #17a2b8;\n                background-color: #1c2b2f;\n                border: 1px solid #28536b;\n                border-radius: 4px;\n                padding: 8px;\n                font-size: 10px;\n                margin-top: 5px;\n            }\n        ')
        auto_sell_layout .addWidget (config_explanation )
        fish_count_layout =QHBoxLayout ()
        fish_count_layout .setSpacing (10 )
        fish_count_label =QLabel ('Fish Caught Until Auto Sell:')
        fish_count_label .setStyleSheet ('color: #e0e0e0; font-size: 11px;')
        fish_count_layout .addWidget (fish_count_label )
        self .fish_count_spinbox =QSpinBox ()
        self .fish_count_spinbox .setRange (1 ,100 )
        self .fish_count_spinbox .setValue (getattr (self .automation ,'fish_count_until_auto_sell',10 ))
        self .fish_count_spinbox .setSuffix (' fish')
        self .fish_count_spinbox .valueChanged .connect (self .update_fish_count_until_auto_sell )
        self .fish_count_spinbox .setStyleSheet ('\n            QSpinBox {\n                background-color: #2d2d2d;\n                color: #e0e0e0;\n                border: 1px solid #555555;\n                border-radius: 4px;\n                padding: 4px 8px;\n                font-size: 11px;\n                min-width: 80px;\n            }\n            QSpinBox::up-button, QSpinBox::down-button {\n                background-color: #404040;\n                border: 1px solid #555555;\n                width: 16px;\n            }\n            QSpinBox::up-button:hover, QSpinBox::down-button:hover {\n                background-color: #4a9eff;\n            }\n        ')
        fish_count_layout .addWidget (self .fish_count_spinbox )
        fish_count_layout .addStretch ()
        auto_sell_layout .addLayout (fish_count_layout )
        scroll_layout .addWidget (auto_sell_group )
        pathing_group =QGroupBox ('Pathing Settings')
        pathing_layout =QVBoxLayout (pathing_group )
        pathing_layout .setContentsMargins (12 ,15 ,12 ,12 )
        pathing_layout .setSpacing (8 )
        pathing_info =QLabel ('For players without the VIP gamepass (NOT VIP+, VIP)')
        pathing_info .setStyleSheet ('color: #888888; font-size: 11px; margin-bottom: 6px;')
        pathing_layout .addWidget (pathing_info )
        self .vip_paths_checkbox =QCheckBox ('Use VIP Paths (Faster with VIP Gamepass)')
        self .vip_paths_checkbox .setChecked (self .automation .use_vip_paths )
        self .vip_paths_checkbox .stateChanged .connect (self .update_vip_paths )
        self .vip_paths_checkbox .setStyleSheet ('\n            QCheckBox {\n                color: #e0e0e0;\n                font-size: 11px;\n                margin: 3px 0;\n            }\n            QCheckBox::indicator {\n                width: 16px;\n                height: 16px;\n                border: 2px solid #555555;\n                border-radius: 3px;\n                background-color: #2d2d2d;\n            }\n            QCheckBox::indicator:checked {\n                background-color: #28a745;\n                border-color: #28a745;\n            }\n        ')
        pathing_layout .addWidget (self .vip_paths_checkbox )
        pathing_info_msg =QLabel ('✓ When enabled: Uses fast VIP (NOT +) paths\n✗ When disabled: Uses slower non-VIP paths')
        pathing_info_msg .setWordWrap (True )
        pathing_info_msg .setStyleSheet ('\n            QLabel {\n                color: #155724;\n                background-color: #d4edda;\n                border: 1px solid #c3e6cb;\n                border-radius: 4px;\n                padding: 8px;\n                font-size: 10px;\n                margin-top: 5px;\n            }\n        ')
        pathing_layout .addWidget (pathing_info_msg )
        scroll_layout .addWidget (pathing_group )
        failsafe_group =QGroupBox ('Failsafe System')
        failsafe_layout =QVBoxLayout (failsafe_group )
        failsafe_layout .setContentsMargins (12 ,15 ,12 ,12 )
        failsafe_layout .setSpacing (8 )
        failsafe_info =QLabel ('Prevents macro from getting soft-locked')
        failsafe_info .setStyleSheet ('color: #888888; font-size: 11px; margin-bottom: 6px;')
        failsafe_layout .addWidget (failsafe_info )
        self .failsafe_checkbox =QCheckBox ('Enable Failsafe System')
        self .failsafe_checkbox .setChecked (self .automation .failsafe_enabled )
        self .failsafe_checkbox .stateChanged .connect (self .update_failsafe_enabled )
        self .failsafe_checkbox .setStyleSheet ('\n            QCheckBox {\n                color: #e0e0e0;\n                font-size: 11px;\n                margin: 3px 0;\n            }\n            QCheckBox::indicator {\n                width: 16px;\n                height: 16px;\n                border: 2px solid #555555;\n                border-radius: 3px;\n                background-color: #2d2d2d;\n            }\n            QCheckBox::indicator:checked {\n                background-color: #4a9eff;\n                border-color: #4a9eff;\n            }\n        ')
        failsafe_layout .addWidget (self .failsafe_checkbox )
        timeout_layout =QHBoxLayout ()
        timeout_layout .setSpacing (10 )
        timeout_label =QLabel ('Timeout (seconds):')
        timeout_label .setStyleSheet ('color: #e0e0e0; font-size: 11px;')
        timeout_layout .addWidget (timeout_label )
        self .failsafe_timeout_spinbox =QSpinBox ()
        self .failsafe_timeout_spinbox .setRange (20 ,60 )
        self .failsafe_timeout_spinbox .setValue (self .automation .failsafe_timeout )
        self .failsafe_timeout_spinbox .setSuffix (' sec')
        self .failsafe_timeout_spinbox .valueChanged .connect (self .update_failsafe_timeout )
        self .failsafe_timeout_spinbox .setStyleSheet ('\n            QSpinBox {\n                background-color: #2d2d2d;\n                color: #e0e0e0;\n                border: 1px solid #555555;\n                border-radius: 4px;\n                padding: 4px 8px;\n                font-size: 11px;\n                min-width: 80px;\n            }\n            QSpinBox::up-button, QSpinBox::down-button {\n                background-color: #404040;\n                border: 1px solid #555555;\n                width: 16px;\n            }\n            QSpinBox::up-button:hover, QSpinBox::down-button:hover {\n                background-color: #4a9eff;\n            }\n        ')
        timeout_layout .addWidget (self .failsafe_timeout_spinbox )
        timeout_layout .addStretch ()
        failsafe_layout .addLayout (timeout_layout )
        self .failsafe_reconnect_checkbox =QCheckBox ('Enable Auto-Reconnect on Repeated Failsafes')
        self .failsafe_reconnect_checkbox .setChecked (self .automation .failsafe_reconnect_enabled )
        self .failsafe_reconnect_checkbox .stateChanged .connect (self .update_failsafe_reconnect_enabled )
        self .failsafe_reconnect_checkbox .setStyleSheet ('\n            QCheckBox {\n                color: #e0e0e0;\n                font-size: 11px;\n                margin: 3px 0;\n            }\n            QCheckBox::indicator {\n                width: 16px;\n                height: 16px;\n                border: 2px solid #555555;\n                border-radius: 3px;\n                background-color: #2d2d2d;\n            }\n            QCheckBox::indicator:checked {\n                background-color: #4a9eff;\n                border-color: #4a9eff;\n            }\n        ')
        failsafe_layout .addWidget (self .failsafe_reconnect_checkbox )
        reconnect_threshold_layout =QHBoxLayout ()
        reconnect_threshold_layout .setSpacing (10 )
        reconnect_threshold_label =QLabel ('Reconnect after failsafes:')
        reconnect_threshold_label .setStyleSheet ('color: #e0e0e0; font-size: 11px;')
        reconnect_threshold_layout .addWidget (reconnect_threshold_label )
        self .failsafe_reconnect_threshold_spinbox =QSpinBox ()
        self .failsafe_reconnect_threshold_spinbox .setRange (2 ,20 )
        self .failsafe_reconnect_threshold_spinbox .setValue (self .automation .failsafe_reconnect_threshold )
        self .failsafe_reconnect_threshold_spinbox .setSuffix (' times')
        self .failsafe_reconnect_threshold_spinbox .valueChanged .connect (self .update_failsafe_reconnect_threshold )
        self .failsafe_reconnect_threshold_spinbox .setStyleSheet ('\n            QSpinBox {\n                background-color: #2d2d2d;\n                color: #e0e0e0;\n                border: 1px solid #555555;\n                border-radius: 4px;\n                padding: 4px 8px;\n                font-size: 11px;\n                min-width: 80px;\n            }\n            QSpinBox::up-button, QSpinBox::down-button {\n                background-color: #404040;\n                border: 1px solid #555555;\n                width: 16px;\n            }\n            QSpinBox::up-button:hover, QSpinBox::down-button:hover {\n                background-color: #4a9eff;\n            }\n        ')
        reconnect_threshold_layout .addWidget (self .failsafe_reconnect_threshold_spinbox )
        reconnect_threshold_layout .addStretch ()
        failsafe_layout .addLayout (reconnect_threshold_layout )
        scroll_layout .addWidget (failsafe_group )
        mouse_delay_group =QGroupBox ('Mouse Delay Settings')
        mouse_delay_layout =QVBoxLayout (mouse_delay_group )
        mouse_delay_layout .setContentsMargins (12 ,15 ,12 ,12 )
        mouse_delay_layout .setSpacing (8 )
        mouse_delay_info =QLabel ('Add extra delay after mouse clicks to prevent issues with fast clicking')
        mouse_delay_info .setStyleSheet ('color: #888888; font-size: 11px; margin-bottom: 6px;')
        mouse_delay_layout .addWidget (mouse_delay_info )
        self .mouse_delay_checkbox =QCheckBox ('Enable Additional Mouse Delay')
        self .mouse_delay_checkbox .setChecked (self .automation .mouse_delay_enabled )
        self .mouse_delay_checkbox .stateChanged .connect (self .update_mouse_delay_enabled )
        self .mouse_delay_checkbox .setStyleSheet ('\n            QCheckBox {\n                color: #e0e0e0;\n                font-size: 11px;\n                margin: 3px 0;\n            }\n            QCheckBox::indicator {\n                width: 16px;\n                height: 16px;\n                border: 2px solid #555555;\n                border-radius: 3px;\n                background-color: #2d2d2d;\n            }\n            QCheckBox::indicator:checked {\n                background-color: #4a9eff;\n                border-color: #4a9eff;\n            }\n        ')
        mouse_delay_layout .addWidget (self .mouse_delay_checkbox )
        delay_amount_layout =QHBoxLayout ()
        delay_amount_layout .setSpacing (10 )
        delay_amount_label =QLabel ('Delay Amount (ms):')
        delay_amount_label .setStyleSheet ('color: #e0e0e0; font-size: 11px;')
        delay_amount_layout .addWidget (delay_amount_label )
        self .mouse_delay_spinbox =QSpinBox ()
        self .mouse_delay_spinbox .setRange (0 ,2000 )
        self .mouse_delay_spinbox .setValue (self .automation .mouse_delay_ms )
        self .mouse_delay_spinbox .setSuffix (' ms')
        self .mouse_delay_spinbox .valueChanged .connect (self .update_mouse_delay_amount )
        self .mouse_delay_spinbox .setStyleSheet ('\n            QSpinBox {\n                background-color: #2d2d2d;\n                color: #e0e0e0;\n                border: 1px solid #555555;\n                border-radius: 4px;\n                padding: 4px 8px;\n                font-size: 11px;\n                min-width: 80px;\n            }\n            QSpinBox::up-button, QSpinBox::down-button {\n                background-color: #404040;\n                border: 1px solid #555555;\n                width: 16px;\n            }\n            QSpinBox::up-button:hover, QSpinBox::down-button:hover {\n                background-color: #4a9eff;\n            }\n        ')
        delay_amount_layout .addWidget (self .mouse_delay_spinbox )
        delay_amount_layout .addStretch ()
        mouse_delay_layout .addLayout (delay_amount_layout )
        scroll_layout .addWidget (mouse_delay_group )
        settings_info_layout =QVBoxLayout ()
        settings_info_layout .setSpacing (10 )
        auto_save_label =QLabel ('Settings are automatically saved to fishscopeconfig.json')
        auto_save_label .setStyleSheet ('color: #888888; font-size: 12px;')
        auto_save_label .setAlignment (Qt .AlignmentFlag .AlignCenter )
        settings_info_layout .addWidget (auto_save_label )
        settings_buttons_layout =QHBoxLayout ()
        settings_buttons_layout .setSpacing (12 )
        settings_buttons_layout .addStretch ()
        update_btn =QPushButton ('Check for Updates')
        update_btn .clicked .connect (self .check_for_updates )
        update_btn .setStyleSheet ('\n            QPushButton {\n                background-color: #17a2b8;\n                color: white;\n                font-weight: 600;\n                padding: 8px 16px;\n                font-size: 12px;\n                border: none;\n                border-radius: 6px;\n            }\n            QPushButton:hover {\n                background-color: #138496;\n            }\n            QPushButton:pressed {\n                background-color: #0f6674;\n            }\n        ')
        settings_buttons_layout .addWidget (update_btn )
        save_config_btn =QPushButton ('Save Config')
        save_config_btn .clicked .connect (self .automation .save_calibration )
        save_config_btn .setStyleSheet ('\n            QPushButton {\n                background-color: #28a745;\n                color: white;\n                font-weight: 600;\n                padding: 8px 16px;\n                font-size: 12px;\n                border: none;\n                border-radius: 6px;\n            }\n            QPushButton:hover {\n                background-color: #218838;\n            }\n            QPushButton:pressed {\n                background-color: #1e7e34;\n            }\n        ')
        settings_buttons_layout .addWidget (save_config_btn )
        settings_buttons_layout .addStretch ()
        settings_info_layout .addLayout (settings_buttons_layout )
        scroll_layout .addLayout (settings_info_layout )
        scroll_layout .addStretch ()
        scroll_area .setWidget (scroll_widget )
        tab_layout =QVBoxLayout (settings_tab )
        tab_layout .setContentsMargins (0 ,0 ,0 ,0 )
        tab_layout .addWidget (scroll_area )

    def apply_premade_calibration (self ,config_name =None ):
        if config_name :
            selected_text =config_name 
        else :
            selected_text =self .premade_combo .currentText ()
        if selected_text =='Select a premade calibration...'or selected_text not in self .premade_calibrations :
            msg =QMessageBox (self )
            msg .setWindowTitle ('No Selection')
            msg .setText ('Please select a premade calibration from the dropdown.')
            msg .setIcon (QMessageBox .Icon .Warning )
            msg .setStyleSheet ('\n                QMessageBox {\n                    background-color: #2d2d2d;\n                    color: white;\n                }\n                QMessageBox QPushButton {\n                    background-color: #fd7e14;\n                    color: white;\n                    border: 1px solid #e8650e;\n                    padding: 8px 16px;\n                    border-radius: 4px;\n                    min-width: 80px;\n                    font-weight: bold;\n                }\n                QMessageBox QPushButton:hover {\n                    background-color: #e8650e;\n                }\n            ')
            msg .exec ()
            return 
        if not config_name :
            msg =QMessageBox (self )
            msg .setWindowTitle ('Apply Premade Calibration')
            msg .setText (f"Are you sure you want to apply the '{selected_text }' calibration?\n\nThis will overwrite your current coordinate settings.")
            msg .setStandardButtons (QMessageBox .StandardButton .Yes |QMessageBox .StandardButton .No )
            msg .setDefaultButton (QMessageBox .StandardButton .No )
            msg .setStyleSheet ('\n                QMessageBox {\n                    background-color: #2d2d2d;\n                    color: white;\n                }\n                QMessageBox QPushButton {\n                    background-color: #4a4a4a;\n                    color: white;\n                    border: 1px solid #666666;\n                    padding: 6px 12px;\n                    border-radius: 3px;\n                    min-width: 60px;\n                }\n            ')
            if msg .exec ()!=QMessageBox .StandardButton .Yes :
                return 
        premade_coords =self .premade_calibrations [selected_text ]
        for coord_name ,coord_value in premade_coords .items ():
            if coord_name in self .automation .coordinates :
                self .update_coordinate_and_ui (coord_name ,coord_value )
        self .update_all_coordinate_labels ()
        self .automation .save_calibration ()
        if not config_name :
            self .premade_combo .setCurrentIndex (0 )
        success_msg =QMessageBox (self )
        success_msg .setWindowTitle ('Calibration Applied')
        success_msg .setText (f"'{selected_text }' calibration has been applied successfully!\n\nSettings have been automatically saved.")
        success_msg .setIcon (QMessageBox .Icon .Information )
        success_msg .setStyleSheet ('\n            QMessageBox {\n                background-color: #2d2d2d;\n                color: white;\n            }\n            QMessageBox QPushButton {\n                background-color: #28a745;\n                color: white;\n                border: 1px solid #218838;\n                padding: 8px 16px;\n                border-radius: 4px;\n                min-width: 80px;\n                font-weight: bold;\n            }\n            QMessageBox QPushButton:hover {\n                background-color: #218838;\n            }\n        ')
        success_msg .exec ()

    def reset_to_defaults (self ):
        msg =QMessageBox ()
        msg .setWindowTitle ('Reset to Defaults')
        msg .setText ('Are you sure you want to reset all coordinates to default values?\nThis will overwrite your current calibration.')
        msg .setStandardButtons (QMessageBox .StandardButton .Yes |QMessageBox .StandardButton .No )
        msg .setDefaultButton (QMessageBox .StandardButton .No )
        msg .setStyleSheet ('\n            QMessageBox {\n                background-color: #2d2d2d;\n                color: white;\n            }\n            QMessageBox QPushButton {\n                background-color: #4a4a4a;\n                color: white;\n                border: 1px solid #666666;\n                padding: 6px 12px;\n                border-radius: 3px;\n                min-width: 60px;\n            }\n        ')
        if msg .exec ()==QMessageBox .StandardButton .Yes :
            self .automation .current_resolution =self .automation .detect_resolution ()
            new_coordinates =self .automation .get_coordinates_for_resolution (self .automation .current_resolution )
            for coord_name ,coord_value in new_coordinates .items ():
                if coord_name in self .automation .coordinates :
                    self .update_coordinate_and_ui (coord_name ,coord_value )
            self .automation .save_calibration ()
            self .update_all_coordinate_labels ()
            success_msg =QMessageBox ()
            success_msg .setWindowTitle ('Reset Complete')
            success_msg .setText ('All coordinates have been reset to defaults and auto-saved!')
            success_msg .setStyleSheet ('\n                QMessageBox {\n                    background-color: #2d2d2d;\n                    color: white;\n                }\n                QMessageBox QPushButton {\n                    background-color: #4a4a4a;\n                    color: white;\n                    border: 1px solid #666666;\n                    padding: 6px 12px;\n                    border-radius: 3px;\n                    min-width: 60px;\n                }\n            ')
            success_msg .exec ()

    def update_all_coordinate_labels (self ):
        if hasattr (self ,'coord_labels_widgets')and hasattr (self ,'coord_labels'):
            for coord_name in self .coord_labels .keys ():
                if coord_name in self .coord_labels_widgets :
                    coord_label =self .coord_labels_widgets [coord_name ]
                    coord_label .setText (self .get_coord_text (coord_name ))
        if hasattr (self ,'shop_coord_labels'):
            for coord_name in self .shop_coord_labels .keys ():
                coord_label =self .shop_coord_labels [coord_name ]
                coord_label .setText (self .get_shop_coord_text (coord_name ))

    def set_1080p_windowed_config (self ):
        self .apply_premade_calibration ('1920x1080 | Windowed')

    def check_for_updates (self ):
        self .auto_updater .check_for_updates (silent =False )

    def import_config (self ):
        from PyQt6 .QtWidgets import QFileDialog ,QMessageBox ,QDialog ,QVBoxLayout ,QHBoxLayout ,QLabel ,QCheckBox ,QPushButton ,QScrollArea ,QWidget ,QFrame 
        from PyQt6 .QtCore import Qt 
        import json 
        file_path ,_ =QFileDialog .getOpenFileName (self ,'Import Configuration','','JSON Files (*.json);;All Files (*)')
        if not file_path :
            return 
        try :
            with open (file_path ,'r',encoding ='utf-8')as f :
                imported_config =json .load (f )
            if not isinstance (imported_config ,dict ):
                QMessageBox .warning (self ,'Invalid Configuration','The imported configuration file is not a valid JSON object.\n\nPlease check the file and try again.')
                return 
            if 'coordinates'not in imported_config :
                QMessageBox .warning (self ,'Invalid Configuration',"The imported configuration file is missing the 'coordinates' section.\n\nPlease check the file and try again.")
                return 
            if not isinstance (imported_config ['coordinates'],dict ):
                QMessageBox .warning (self ,'Invalid Configuration',"The imported configuration file has an invalid 'coordinates' format.\n\nPlease check the file and try again.")
                return 
            current_version =getattr (self .automation ,'config_version','1.0')
            imported_version =imported_config .get ('version','1.0')
            if imported_version !=current_version :
                reply =QMessageBox .question (self ,'Version Mismatch',f'The imported configuration was created with version {imported_version }, but you are running version {current_version }.\n\nSome settings may not be compatible. Continue with import?',QMessageBox .StandardButton .Yes |QMessageBox .StandardButton .No ,QMessageBox .StandardButton .No )
                if reply ==QMessageBox .StandardButton .No :
                    return 
            preview_dialog =QDialog (self )
            preview_dialog .setWindowTitle ('Import Configuration - Select Items to Import')
            preview_dialog .setModal (True )
            preview_dialog .resize (600 ,500 )
            layout =QVBoxLayout (preview_dialog )
            header_label =QLabel ('Select which configuration items to import:')
            header_label .setStyleSheet ('font-weight: bold; font-size: 14px; margin-bottom: 10px;')
            layout .addWidget (header_label )
            scroll_area =QScrollArea ()
            scroll_widget =QWidget ()
            scroll_layout =QVBoxLayout (scroll_widget )
            checkboxes ={}
            current_config =self .automation .coordinates .copy ()
            coord_frame =QFrame ()
            coord_frame .setStyleSheet ('QFrame { border: 1px solid #555; border-radius: 5px; margin: 5px; }')
            coord_layout =QVBoxLayout (coord_frame )
            coord_title =QLabel ('Coordinates:')
            coord_title .setStyleSheet ('font-weight: bold; font-size: 12px;')
            coord_layout .addWidget (coord_title )
            for coord_name ,coord_value in imported_config .get ('coordinates',{}).items ():
                checkbox =QCheckBox (f'{coord_name }: {coord_value }')
                checkbox .setChecked (True )
                checkboxes [f'coord_{coord_name }']=checkbox 
                coord_layout .addWidget (checkbox )
            scroll_layout .addWidget (coord_frame )
            settings_frame =QFrame ()
            settings_frame .setStyleSheet ('QFrame { border: 1px solid #555; border-radius: 5px; margin: 5px; }')
            settings_layout =QVBoxLayout (settings_frame )
            settings_title =QLabel ('Settings:')
            settings_title .setStyleSheet ('font-weight: bold; font-size: 12px;')
            settings_layout .addWidget (settings_title )
            settings_to_check =[('webhook_url','Webhook URL'),('ignore_common_fish','Ignore Common Fish'),('ignore_uncommon_fish','Ignore Uncommon Fish'),('ignore_rare_fish','Ignore Rare Fish'),('ignore_trash','Ignore Trash'),('auto_sell_enabled','Auto Sell Enabled'),('auto_sell_configuration','Auto Sell Configuration'),('fish_count_until_auto_sell','Fish Count Until Auto Sell'),('use_vip_paths','Use VIP Paths'),('auto_reconnect_enabled','Auto Reconnect Enabled'),('auto_reconnect_time','Auto Reconnect Time'),('roblox_window_mode','Roblox Window Mode'),('roblox_private_server_link','Private Server Link'),('mouse_delay_enabled','Mouse Delay Enabled'),('mouse_delay_ms','Mouse Delay MS'),('failsafe_enabled','Failsafe Enabled'),('failsafe_timeout','Failsafe Timeout'),('failsafe_reconnect_enabled','Failsafe Reconnect Enabled'),('failsafe_reconnect_threshold','Failsafe Reconnect Threshold'),('backslash_sequence_delay','Backslash Sequence Delay')]
            for setting_key ,setting_display in settings_to_check :
                if setting_key in imported_config :
                    current_value =getattr (self .automation ,setting_key ,None )
                    imported_value =imported_config [setting_key ]
                    if isinstance (imported_value ,bool ):
                        display_value ='Enabled'if imported_value else 'Disabled'
                    elif isinstance (imported_value ,str )and len (imported_value )>50 :
                        display_value =imported_value [:47 ]+'...'
                    else :
                        display_value =str (imported_value )
                    checkbox =QCheckBox (f'{setting_display }: {display_value }')
                    checkbox .setChecked (True )
                    checkboxes [f'setting_{setting_key }']=checkbox 
                    settings_layout .addWidget (checkbox )
            scroll_layout .addWidget (settings_frame )
            scroll_layout .addStretch ()
            scroll_area .setWidget (scroll_widget )
            scroll_area .setWidgetResizable (True )
            layout .addWidget (scroll_area )
            button_layout =QHBoxLayout ()
            import_btn =QPushButton ('Import Selected')
            import_btn .clicked .connect (preview_dialog .accept )
            import_btn .setStyleSheet ('\n                QPushButton {\n                    background-color: #28a745;\n                    color: white;\n                    border: none;\n                    padding: 8px 16px;\n                    border-radius: 4px;\n                    font-weight: bold;\n                }\n                QPushButton:hover {\n                    background-color: #218838;\n                }\n            ')
            button_layout .addWidget (import_btn )
            cancel_btn =QPushButton ('Cancel')
            cancel_btn .clicked .connect (preview_dialog .reject )
            cancel_btn .setStyleSheet ('\n                QPushButton {\n                    background-color: #6c757d;\n                    color: white;\n                    border: none;\n                    padding: 8px 16px;\n                    border-radius: 4px;\n                }\n                QPushButton:hover {\n                    background-color: #5a6268;\n                }\n            ')
            button_layout .addWidget (cancel_btn )
            layout .addLayout (button_layout )
            preview_dialog .setStyleSheet ('\n                QDialog {\n                    background-color: #2d2d2d;\n                    color: white;\n                }\n                QLabel {\n                    color: white;\n                }\n                QCheckBox {\n                    color: white;\n                }\n                QCheckBox::indicator {\n                    width: 16px;\n                    height: 16px;\n                    border: 2px solid #555;\n                    border-radius: 3px;\n                    background-color: #2d2d2d;\n                }\n                QCheckBox::indicator:checked {\n                    background-color: #4a9eff;\n                    border-color: #4a9eff;\n                }\n                QFrame {\n                    background-color: #1a1a1a;\n                }\n            ')
            if preview_dialog .exec ()==QDialog .DialogCode .Accepted :
                imported_count =0 
                for key ,checkbox in checkboxes .items ():
                    if key .startswith ('coord_')and checkbox .isChecked ():
                        coord_name =key [6 :]
                        if coord_name in imported_config .get ('coordinates',{}):
                            coord_value =imported_config ['coordinates'][coord_name ]
                            self .update_coordinate_and_ui (coord_name ,coord_value )
                            imported_count +=1 
                for key ,checkbox in checkboxes .items ():
                    if key .startswith ('setting_')and checkbox .isChecked ():
                        setting_key =key [8 :]
                        if setting_key in imported_config :
                            setattr (self .automation ,setting_key ,imported_config [setting_key ])
                            imported_count +=1 
                self .automation .save_calibration ()
                self .update_all_coordinate_labels ()
                QMessageBox .information (self ,'Import Complete',f"Successfully imported {imported_count } configuration items from '{file_path .split ('/')[-1 ]}'.")
        except json .JSONDecodeError as e :
            QMessageBox .critical (self ,'Invalid JSON',f'The selected file is not a valid JSON file:\n\n{str (e )}')
        except Exception as e :
            QMessageBox .critical (self ,'Import Error',f'An error occurred while importing the configuration:\n\n{str (e )}')

    def export_config (self ):
        from PyQt6 .QtWidgets import QFileDialog ,QMessageBox 
        import json 
        file_path ,_ =QFileDialog .getSaveFileName (self ,'Export Configuration','fishscope_config.json','JSON Files (*.json);;All Files (*)')
        if not file_path :
            return 
        try :
            config_to_export ={'version':getattr (self .automation ,'config_version','1.0'),'export_timestamp':datetime .now ().isoformat (),'coordinates':self .automation .coordinates .copy (),'webhook_url':getattr (self .automation ,'webhook_url',''),'ignore_common_fish':getattr (self .automation ,'ignore_common_fish',False ),'ignore_uncommon_fish':getattr (self .automation ,'ignore_uncommon_fish',False ),'ignore_rare_fish':getattr (self .automation ,'ignore_rare_fish',False ),'ignore_trash':getattr (self .automation ,'ignore_trash',False ),'auto_sell_enabled':getattr (self .automation ,'auto_sell_enabled',False ),'auto_sell_configuration':getattr (self .automation ,'auto_sell_configuration',''),'fish_count_until_auto_sell':getattr (self .automation ,'fish_count_until_auto_sell',0 ),'use_vip_paths':getattr (self .automation ,'use_vip_paths',False ),'auto_reconnect_enabled':getattr (self .automation ,'auto_reconnect_enabled',False ),'auto_reconnect_time':getattr (self .automation ,'auto_reconnect_time',0 ),'roblox_window_mode':getattr (self .automation ,'roblox_window_mode','windowed'),'roblox_private_server_link':getattr (self .automation ,'roblox_private_server_link',''),'mouse_delay_enabled':getattr (self .automation ,'mouse_delay_enabled',False ),'mouse_delay_ms':getattr (self .automation ,'mouse_delay_ms',0 ),'failsafe_enabled':getattr (self .automation ,'failsafe_enabled',False ),'failsafe_timeout':getattr (self .automation ,'failsafe_timeout',30 ),'failsafe_reconnect_enabled':getattr (self .automation ,'failsafe_reconnect_enabled',False ),'failsafe_reconnect_threshold':getattr (self .automation ,'failsafe_reconnect_threshold',3 ),'backslash_sequence_delay':getattr (self .automation ,'backslash_sequence_delay',100 )}
            with open (file_path ,'w',encoding ='utf-8')as f :
                json .dump (config_to_export ,f ,indent =2 ,ensure_ascii =False )
            QMessageBox .information (self ,'Export Complete',f'Configuration successfully exported to:\n\n{file_path }')
        except Exception as e :
            QMessageBox .critical (self ,'Export Error',f'An error occurred while exporting the configuration:\n\n{str (e )}')

    def closeEvent (self ,event ):
        self .automation .stop_automation ()
        event .accept ()

def main ():
    app =QApplication (sys .argv )
    app .setApplicationName ('FishScope')
    app .setApplicationVersion ('1.0')
    app .setOrganizationName ('cresqnt')
    if os .path .exists ('icon.ico'):
        app .setWindowIcon (QIcon ('icon.ico'))
    automation =MouseAutomation ()
    ui =CalibrationUI (automation )
    keyboard .add_hotkey ('f1',automation .start_automation )
    keyboard .add_hotkey ('f2',automation .stop_automation )
    ui .show ()
    QTimer .singleShot (1000 ,ui .show_first_launch_warning )
    QTimer .singleShot (2000 ,lambda :ui .auto_updater .check_for_updates (silent =True ))
    sys .exit (app .exec ())
if __name__ =='__main__':
    main ()