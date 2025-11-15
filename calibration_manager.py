import json 
import os 
import requests 
import time 
from datetime import datetime ,timezone 
from pathlib import Path 
import shutil 

class CalibrationManager :

    def __init__ (self ,verbose =False ):
        self .calibration_url ='https://cresqnt.com/api/fishscopecalibs'
        self .appdata_path =os .path .join (os .getenv ('APPDATA',''),'FishScope')
        self .calibration_file =os .path .join (self .appdata_path ,'remote_calibrations.json')
        self .backup_file =os .path .join (self .appdata_path ,'remote_calibrations_backup.json')
        self .verbose =verbose 
        os .makedirs (self .appdata_path ,exist_ok =True )
        self ._cached_calibrations =None 
        self ._cache_timestamp =None 
        self .default_calibrations ={'version':'1.0','last_updated':'2025-09-20T12:00:00Z','calibrations':[{'name':'1920x1080 | Windowed | 100% Scale','resolution':'1920x1080','window_mode':'windowed','scale':'100%','coordinates':{'fish_button':[851 ,802 ],'white_diamond':[1176 ,805 ],'reel_bar':[757 ,728 ,1163 ,750 ],'completed_border':[1133 ,744 ],'close_button':[1108 ,337 ],'fish_caught_desc':[700 ,540 ,1035 ,685 ],'first_item':[830 ,409 ],'sell_button':[588 ,775 ],'confirm_button':[797 ,613 ],'mouse_idle_position':[999 ,190 ],'shaded_area':[951 ,731 ],'sell_fish_shop':[900 ,600 ],'collection_button':[950 ,650 ],'exit_collections':[1000 ,700 ],'exit_fish_shop':[1050 ,750 ]}},{'name':'2560x1440 | Windowed | 100% Scale','resolution':'2560x1440','window_mode':'windowed','scale':'100%','coordinates':{'fish_button':[1149 ,1089 ],'white_diamond':[1536 ,1093 ],'reel_bar':[1042 ,1000 ,1515 ,1026 ],'completed_border':[1479 ,959 ],'close_button':[1455 ,491 ],'fish_caught_desc':[933 ,720 ,1378 ,913 ],'first_item':[1101 ,546 ],'sell_button':[779 ,1054 ],'confirm_button':[1054 ,827 ],'mouse_idle_position':[1281 ,1264 ],'shaded_area':[1271 ,1008 ],'sell_fish_shop':[1200 ,800 ],'collection_button':[1250 ,850 ],'exit_collections':[1300 ,900 ],'exit_fish_shop':[1350 ,950 ]}},{'name':'3840x2160 | Windowed | 100% Scale','resolution':'3840x2160','window_mode':'windowed','scale':'100%','coordinates':{'fish_button':[1751 ,1648 ],'white_diamond':[2253 ,1652 ],'reel_bar':[1607 ,1535 ,2233 ,1568 ],'completed_border':[2174 ,1384 ],'close_button':[2136 ,789 ],'fish_caught_desc':[1400 ,1080 ,2070 ,1370 ],'first_item':[1650 ,819 ],'sell_button':[1168 ,1588 ],'confirm_button':[1595 ,1238 ],'mouse_idle_position':[1952 ,452 ],'shaded_area':[1904 ,1540 ],'sell_fish_shop':[1800 ,1200 ],'collection_button':[1850 ,1250 ],'exit_collections':[1900 ,1300 ],'exit_fish_shop':[1950 ,1350 ]}}]}

    def _print (self ,message ):
        if self .verbose :
            print (message )

    def download_calibrations (self ,timeout =10 ):
        try :
            print (f'Downloading calibrations from: {self .calibration_url }')
            headers ={'User-Agent':'FishScope-Macro/1.0','Accept':'application/json','Content-Type':'application/json'}
            response =requests .get (self .calibration_url ,timeout =timeout ,headers =headers )
            response .raise_for_status ()
            calibration_data =response .json ()
            if not self .validate_calibration_data (calibration_data ):
                raise ValueError ('Invalid calibration data format received from server')
            print (f"Successfully downloaded {len (calibration_data .get ('calibrations',[]))} calibrations")
            return (True ,'Calibrations downloaded successfully',calibration_data )
        except requests .exceptions .Timeout :
            error_msg =f'Request timed out after {timeout } seconds'
            print (f'Error downloading calibrations: {error_msg }')
            return (False ,error_msg ,None )
        except requests .exceptions .ConnectionError :
            error_msg ='Could not connect to calibration server'
            print (f'Error downloading calibrations: {error_msg }')
            return (False ,error_msg ,None )
        except requests .exceptions .HTTPError as e :
            error_msg =f'HTTP error {e .response .status_code }: {e .response .reason }'
            print (f'Error downloading calibrations: {error_msg }')
            return (False ,error_msg ,None )
        except json .JSONDecodeError :
            error_msg ='Invalid JSON response from server'
            print (f'Error downloading calibrations: {error_msg }')
            return (False ,error_msg ,None )
        except ValueError as e :
            error_msg =str (e )
            print (f'Error downloading calibrations: {error_msg }')
            return (False ,error_msg ,None )
        except Exception as e :
            error_msg =f'Unexpected error: {str (e )}'
            print (f'Error downloading calibrations: {error_msg }')
            return (False ,error_msg ,None )

    def validate_calibration_data (self ,data ):
        try :
            if not isinstance (data ,dict ):
                return False 
            if 'calibrations'not in data :
                return False 
            if not isinstance (data ['calibrations'],list ):
                return False 
            for calibration in data ['calibrations']:
                if not isinstance (calibration ,dict ):
                    return False 
                required_fields =['name','coordinates']
                for field in required_fields :
                    if field not in calibration :
                        return False 
                coordinates =calibration ['coordinates']
                if not isinstance (coordinates ,dict ):
                    return False 
                essential_coords =['fish_button','white_diamond','reel_bar','close_button']
                for coord in essential_coords :
                    if coord not in coordinates :
                        return False 
                    coord_data =coordinates [coord ]
                    if not isinstance (coord_data ,list ):
                        return False 
                    if coord in ['reel_bar','fish_caught_desc']:
                        if len (coord_data )!=4 :
                            return False 
                    elif len (coord_data )!=2 :
                        return False 
                    for coord_val in coord_data :
                        if not isinstance (coord_val ,(int ,float )):
                            return False 
            return True 
        except Exception as e :
            print (f'Error validating calibration data: {e }')
            return False 

    def save_calibrations (self ,data ):
        try :
            if os .path .exists (self .calibration_file ):
                try :
                    shutil .copy2 (self .calibration_file ,self .backup_file )
                    print ('Created backup of existing calibrations')
                except Exception as e :
                    print (f'Warning: Could not create backup: {e }')
            with open (self .calibration_file ,'w',encoding ='utf-8')as f :
                json .dump (data ,f ,indent =2 )
            print (f'Calibrations saved to: {self .calibration_file }')
            self ._cached_calibrations =data 
            self ._cache_timestamp =time .time ()
            return True 
        except Exception as e :
            print (f'Error saving calibrations: {e }')
            return False 

    def load_calibrations (self ,force_reload =False ):
        try :
            if not force_reload and self ._cached_calibrations is not None :
                if self ._cache_timestamp and time .time ()-self ._cache_timestamp <300 :
                    return self ._cached_calibrations 
            self ._cache_timestamp =time .time ()
            if os .path .exists (self .calibration_file ):
                with open (self .calibration_file ,'r',encoding ='utf-8')as f :
                    data =json .load (f )
                if self .validate_calibration_data (data ):
                    if (self ._cached_calibrations is None or force_reload )and self .verbose :
                        print (f"Loaded {len (data .get ('calibrations',[]))} calibrations from local file")
                    self ._cached_calibrations =data 
                    return data 
                else :
                    print ('Local calibration file is corrupted, trying backup...')
                    if os .path .exists (self .backup_file ):
                        try :
                            with open (self .backup_file ,'r',encoding ='utf-8')as f :
                                backup_data =json .load (f )
                            if self .validate_calibration_data (backup_data ):
                                print ('Loaded calibrations from backup file')
                                shutil .copy2 (self .backup_file ,self .calibration_file )
                                self ._cached_calibrations =backup_data 
                                return backup_data 
                        except Exception as e :
                            print (f'Backup file also corrupted: {e }')
            if self ._cached_calibrations is None and self .verbose :
                print ('No valid local calibrations found, using defaults')
            self ._cached_calibrations =self .default_calibrations 
            return self .default_calibrations 
        except Exception as e :
            print (f'Error loading calibrations: {e }')
            print ('Using default calibrations')
            self ._cached_calibrations =self .default_calibrations 
            return self .default_calibrations 

    def update_calibrations (self ,force_update =False ):
        try :
            current_calibrations =self .load_calibrations (force_reload =True )
            should_update =force_update 
            if not should_update :
                if os .path .exists (self .calibration_file ):
                    file_age =time .time ()-os .path .getmtime (self .calibration_file )
                    if file_age >86400 :
                        should_update =True 
                        print ('Local calibrations are older than 24 hours, updating...')
                else :
                    should_update =True 
                    print ('No local calibrations found, downloading...')
            if should_update :
                success ,message ,new_data =self .download_calibrations ()
                if success and new_data :
                    if self .save_calibrations (new_data ):
                        return (True ,'Calibrations updated successfully',new_data )
                    else :
                        return (False ,'Failed to save downloaded calibrations',current_calibrations )
                else :
                    print (f'Failed to update calibrations: {message }')
                    print ('Using existing calibrations')
                    return (False ,f'Update failed: {message }',current_calibrations )
            else :
                self ._print ('Using existing calibrations (no update needed)')
                return (True ,'Using existing calibrations',current_calibrations )
        except Exception as e :
            error_msg =f'Error during calibration update: {str (e )}'
            print (error_msg )
            return (False ,error_msg ,self .default_calibrations )

    def get_calibration_by_name (self ,name ):
        calibrations =self .load_calibrations ()
        for calibration in calibrations .get ('calibrations',[]):
            if calibration .get ('name')==name :
                return calibration .get ('coordinates',{})
        return None 

    def get_available_calibrations (self ):
        calibrations =self .load_calibrations ()
        names =[]
        for calibration in calibrations .get ('calibrations',[]):
            if 'name'in calibration :
                names .append (calibration ['name'])
        return names 

    def get_calibration_info (self ,name ):
        calibrations =self .load_calibrations ()
        for calibration in calibrations .get ('calibrations',[]):
            if calibration .get ('name')==name :
                return {'name':calibration .get ('name','Unknown'),'resolution':calibration .get ('resolution','Unknown'),'window_mode':calibration .get ('window_mode','Unknown'),'scale':calibration .get ('scale','Unknown'),'coordinate_count':len (calibration .get ('coordinates',{}))}
        return None 