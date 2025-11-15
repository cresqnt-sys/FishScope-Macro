import time 
import os 
import sys 
import subprocess 
import webbrowser 
import autoit 
import ctypes 
from ctypes import wintypes 
try :
    import win32gui 
    import win32con 
    WIN32_AVAILABLE =True 
except ImportError :
    WIN32_AVAILABLE =False 
    win32gui =None 
    win32con =None 
try :
    import keyboard 
    KEYBOARD_AVAILABLE =True 
except ImportError :
    KEYBOARD_AVAILABLE =False 
PROCESS_TERMINATE =1 
PROCESS_QUERY_INFORMATION =1024 
try :
    kernel32 =ctypes .windll .kernel32 
    shell32 =ctypes .windll .shell32 
    user32 =ctypes .windll .user32 
    shell32 .ShellExecuteW .argtypes =[wintypes .HWND ,wintypes .LPCWSTR ,wintypes .LPCWSTR ,wintypes .LPCWSTR ,wintypes .LPCWSTR ,ctypes .c_int ]
    shell32 .ShellExecuteW .restype =wintypes .HINSTANCE 
    kernel32 .CreateToolhelp32Snapshot .argtypes =[wintypes .DWORD ,wintypes .DWORD ]
    kernel32 .CreateToolhelp32Snapshot .restype =wintypes .HANDLE 

    class PROCESSENTRY32 (ctypes .Structure ):
        _fields_ =[('dwSize',wintypes .DWORD ),('cntUsage',wintypes .DWORD ),('th32ProcessID',wintypes .DWORD ),('th32DefaultHeapID',ctypes .POINTER (wintypes .ULONG )),('th32ModuleID',wintypes .DWORD ),('cntThreads',wintypes .DWORD ),('th32ParentProcessID',wintypes .DWORD ),('pcPriClassBase',wintypes .LONG ),('dwFlags',wintypes .DWORD ),('szExeFile',wintypes .CHAR *260 )]
    kernel32 .Process32First .argtypes =[wintypes .HANDLE ,ctypes .POINTER (PROCESSENTRY32 )]
    kernel32 .Process32First .restype =wintypes .BOOL 
    kernel32 .Process32Next .argtypes =[wintypes .HANDLE ,ctypes .POINTER (PROCESSENTRY32 )]
    kernel32 .Process32Next .restype =wintypes .BOOL 
    kernel32 .OpenProcess .argtypes =[wintypes .DWORD ,wintypes .BOOL ,wintypes .DWORD ]
    kernel32 .OpenProcess .restype =wintypes .HANDLE 
    kernel32 .TerminateProcess .argtypes =[wintypes .HANDLE ,wintypes .UINT ]
    kernel32 .TerminateProcess .restype =wintypes .BOOL 
    kernel32 .CloseHandle .argtypes =[wintypes .HANDLE ]
    kernel32 .CloseHandle .restype =wintypes .BOOL 
    WINAPI_AVAILABLE =True 
except Exception as e :
    WINAPI_AVAILABLE =False 
    print (f'Warning: Windows API functions not available: {e }')

class AutoReconnectManager :

    def __init__ (self ,automation =None ):
        self .automation =automation 
        self .auto_reconnect_enabled =False 
        self .auto_reconnect_time =3600 
        self .auto_reconnect_timer_start =None 
        self .auto_reconnect_in_progress =False 
        self .roblox_private_server_link =''
        self .roblox_window_mode ='windowed'
        self .backslash_sequence_delay =60.0 
        self .is_pyinstaller =getattr (sys ,'frozen',False )and hasattr (sys ,'_MEIPASS')
        if self .is_pyinstaller :
            print ('Running in PyInstaller executable - using Windows API for process management')

    def _get_exe_directory (self ):
        if self .is_pyinstaller :
            return os .path .dirname (sys .executable )
        else :
            return os .path .dirname (os .path .abspath (__file__ ))

    def set_automation_reference (self ,automation ):
        self .automation =automation 

    def should_auto_reconnect (self ):
        if not self .auto_reconnect_enabled or not self .auto_reconnect_timer_start :
            return False 
        if self .automation :
            if hasattr (self .automation ,'automation_phase')and self .automation .automation_phase in ['pre_sell','selling']:
                print ('Auto reconnect blocked: currently in auto sell phase')
                return False 
            if hasattr (self .automation ,'external_script_running')and self .automation .external_script_running :
                print ('Auto reconnect blocked: external script (navigation) is running')
                return False 
            if hasattr (self .automation ,'in_sell_cycle')and self .automation .in_sell_cycle :
                print ('Auto reconnect blocked: in sell cycle')
                return False 
        elapsed_time =time .time ()-self .auto_reconnect_timer_start 
        return elapsed_time >=self .auto_reconnect_time 

    def get_auto_reconnect_time_remaining (self ):
        if not self .auto_reconnect_enabled or not self .auto_reconnect_timer_start :
            return None 
        elapsed_time =time .time ()-self .auto_reconnect_timer_start 
        total_time =self .auto_reconnect_time 
        remaining =total_time -elapsed_time 
        return max (0 ,remaining )

    def start_timer (self ):
        self .auto_reconnect_timer_start =time .time ()

    def reset_timer (self ):
        self .auto_reconnect_timer_start =time .time ()

    def stop_timer (self ):
        self .auto_reconnect_timer_start =None 

    def interruptible_sleep (self ,duration ,toggle_callback =None ):
        steps =int (duration *10 )
        for i in range (steps ):
            if toggle_callback and (not toggle_callback ()):
                return False 
            if self .should_auto_reconnect ():
                return 'auto_reconnect'
            time .sleep (0.1 )
        return True 

    def perform_auto_reconnect (self ,toggle_callback =None ):
        try :
            self .auto_reconnect_in_progress =True 
            if self .is_pyinstaller :
                print ('Auto-reconnect starting in compiled executable mode')
            if self .automation and hasattr (self .automation ,'send_webhook_notification'):
                self .automation .send_webhook_notification ('roblox_reconnected','ðŸ”„ Auto Reconnect Triggered',f'Reconnecting after {self .auto_reconnect_time } seconds...',color =1548984 )
            print ('Closing Roblox instances...')
            self .close_roblox_instances ()
            time .sleep (5 )
            launch_success =False 
            if self .roblox_private_server_link .strip ():
                print ('Attempting to launch private server...')
                launch_success =self .launch_private_server ()
                if launch_success :
                    print ('Private server launch successful')
                    if not self ._execute_reconnect_sequence (toggle_callback ):
                        print ('Reconnect sequence failed after private server launch')
                        self .auto_reconnect_in_progress =False 
                        return False 
                else :
                    print ('Private server launch failed, continuing with reconnect sequence...')
                    if not self ._execute_reconnect_sequence (toggle_callback ):
                        print ('Reconnect sequence failed without private server')
                        self .auto_reconnect_in_progress =False 
                        return False 
            else :
                print ('No private server link provided, proceeding with standard reconnect...')
                if not self ._execute_reconnect_sequence (toggle_callback ):
                    print ('Standard reconnect sequence failed')
                    self .auto_reconnect_in_progress =False 
                    return False 
            self .reset_timer ()
            self .auto_reconnect_in_progress =False 
            if self .automation and hasattr (self .automation ,'send_roblox_reconnected_notification'):
                self .automation .send_roblox_reconnected_notification ()
            print ('Auto-reconnect completed successfully')
            return True 
        except Exception as e :
            error_msg =f'Auto Reconnect Error: {str (e )}'
            print (error_msg )
            if self .automation and hasattr (self .automation ,'send_error_notification'):
                self .automation .send_error_notification ('Auto Reconnect Error',str (e ))
            self .auto_reconnect_in_progress =False 
            self .reset_timer ()
            return False 

    def _wait_with_checks (self ,seconds ,toggle_callback =None ):
        for i in range (seconds *10 ):
            if toggle_callback and (not toggle_callback ()):
                return False 
            time .sleep (0.1 )
        return True 

    def _execute_reconnect_sequence (self ,toggle_callback ):
        if self .wait_for_roblox_and_set_window_mode (toggle_callback ):
            if self .automation and hasattr (self .automation ,'send_roblox_detected_notification'):
                self .automation .send_roblox_detected_notification ()
        if not self ._wait_with_checks (60 ,toggle_callback ):
            return False 
        self .press_backslash_sequence ()
        time .sleep (2 )
        return True 

    def close_roblox_instances (self ):
        try :
            roblox_processes =['RobloxPlayerBeta.exe','RobloxStudioBeta.exe','Roblox.exe']
            processes_found =False 
            if WINAPI_AVAILABLE :
                try :
                    TH32CS_SNAPPROCESS =2 
                    snapshot =kernel32 .CreateToolhelp32Snapshot (TH32CS_SNAPPROCESS ,0 )
                    if snapshot ==-1 :
                        print ('Failed to create process snapshot')
                    else :
                        try :
                            process_entry =PROCESSENTRY32 ()
                            process_entry .dwSize =ctypes .sizeof (PROCESSENTRY32 )
                            if kernel32 .Process32First (snapshot ,ctypes .byref (process_entry )):
                                while True :
                                    exe_name =process_entry .szExeFile .decode ('utf-8',errors ='ignore')
                                    if exe_name in roblox_processes :
                                        processes_found =True 
                                        print (f'Found Roblox process: {exe_name } (PID: {process_entry .th32ProcessID })')
                                        process_handle =kernel32 .OpenProcess (PROCESS_TERMINATE ,False ,process_entry .th32ProcessID )
                                        if process_handle :
                                            if kernel32 .TerminateProcess (process_handle ,0 ):
                                                print (f'Successfully terminated {exe_name }')
                                            else :
                                                print (f'Failed to terminate {exe_name }')
                                            kernel32 .CloseHandle (process_handle )
                                    if not kernel32 .Process32Next (snapshot ,ctypes .byref (process_entry )):
                                        break 
                        finally :
                            kernel32 .CloseHandle (snapshot )
                except Exception as e :
                    print (f'Windows API process enumeration failed: {e }')
            if not WINAPI_AVAILABLE or not processes_found :
                try :
                    for process_name in roblox_processes :
                        try :
                            result =subprocess .run (['taskkill','/f','/im',process_name ],capture_output =True ,text =True ,check =False )
                            if result .returncode ==0 :
                                print (f'Taskkill successfully terminated {process_name }')
                        except Exception as e :
                            pass 
                except Exception as e :
                    print (f'Taskkill fallback failed: {e }')
            if WIN32_AVAILABLE :
                try :

                    def enum_windows_callback (hwnd ,windows ):
                        if win32gui .IsWindowVisible (hwnd ):
                            window_text =win32gui .GetWindowText (hwnd )
                            if 'Roblox'in window_text or 'roblox'in window_text .lower ():
                                windows .append ((hwnd ,window_text ))
                        return True 
                    windows =[]
                    win32gui .EnumWindows (enum_windows_callback ,windows )
                    for hwnd ,window_text in windows :
                        try :
                            win32gui .PostMessage (hwnd ,win32con .WM_CLOSE ,0 ,0 )
                            print (f'Sent close message to Roblox window: {window_text }')
                        except Exception as e :
                            pass 
                    if windows :
                        processes_found =True 
                except Exception as e :
                    pass 
            if processes_found :
                print ('Roblox close sequence completed')
            else :
                print ('No Roblox processes found to close')
        except Exception as e :
            print (f'Error closing Roblox instances: {e }')

    def launch_private_server (self ):
        try :
            if not self .roblox_private_server_link .strip ():
                print ('No private server link provided')
                return False 
            link =self .roblox_private_server_link .strip ()
            if link .startswith ('roblox://'):
                roblox_url =link 
            elif 'roblox.com/games/'in link :
                try :
                    game_part =link .split ('games/')[1 ]
                    game_id =game_part .split ('/')[0 ].split ('?')[0 ]
                    if 'privateServerLinkCode='in link :
                        private_code =link .split ('privateServerLinkCode=')[1 ].split ('&')[0 ]
                        roblox_url =f'roblox://placeId={game_id }&linkCode={private_code }'
                    else :
                        roblox_url =f'roblox://placeId={game_id }'
                except Exception as e :
                    return False 
            else :
                return False 
            if WINAPI_AVAILABLE :
                try :
                    result =shell32 .ShellExecuteW (None ,'open',roblox_url ,None ,None ,1 )
                    if result >32 :
                        print (f'Successfully launched Roblox using Windows API: {roblox_url }')
                        return True 
                except Exception as e :
                    print (f'Windows API ShellExecute failed: {e }')
            try :
                if WINAPI_AVAILABLE :
                    powershell_cmd =f'powershell.exe -Command "Start-Process \\"{roblox_url }\\""'
                    startup_info =ctypes .Structure ()
                    startup_info .cb =ctypes .sizeof (startup_info )
                    process_info =ctypes .Structure ()
                    import tempfile 
                    with tempfile .NamedTemporaryFile (mode ='w',suffix ='.cmd',delete =False )as temp_file :
                        temp_file .write (f'start "" "{roblox_url }"\n')
                        temp_file .flush ()
                        result =shell32 .ShellExecuteW (None ,'open',temp_file .name ,None ,None ,0 )
                        import threading 

                        def cleanup ():
                            time .sleep (2 )
                            try :
                                os .unlink (temp_file .name )
                            except :
                                pass 
                        threading .Thread (target =cleanup ,daemon =True ).start ()
                        if result >32 :
                            print (f'Successfully launched Roblox using batch file method: {roblox_url }')
                            return True 
            except Exception as e :
                print (f'Batch file method failed: {e }')
            try :
                if WINAPI_AVAILABLE :
                    result =shell32 .ShellExecuteW (None ,None ,roblox_url ,None ,None ,1 )
                    if result >32 :
                        print (f'Successfully launched Roblox using URL association: {roblox_url }')
                        return True 
            except Exception as e :
                print (f'URL association method failed: {e }')
            try :
                webbrowser .open (roblox_url )
                print (f'Launched Roblox using webbrowser module: {roblox_url }')
                return True 
            except Exception as e :
                print (f'Webbrowser module failed: {e }')
            try :
                escaped_url =f'"{roblox_url }"'
                command =f'start "" {escaped_url }'
                result =os .system (command )
                if result ==0 :
                    print (f'Successfully launched Roblox using os.system: {roblox_url }')
                    return True 
            except Exception as e :
                print (f'os.system method failed: {e }')
            print ('All launch methods failed')
            return False 
        except Exception as e :
            print (f'Error launching private server: {e }')
            return False 

    def press_backslash_sequence (self ):
        total_delay =max (60.0 ,self .backslash_sequence_delay )
        try :
            self .focus_roblox_window ()
            time .sleep (0.5 )
            self ._prepare_and_wait (total_delay )
            print ('Wait complete, now executing key sequence...')
            print ('Now actions are â†’ \\ â†’ Enter â†’ \\ then continue')
            self ._send_backslash_sequence (autoit .send )
            print (f'Backslash sequence completed after {total_delay } second delay + key execution')
        except Exception as e :
            try :
                self .focus_roblox_window ()
                time .sleep (0.5 )
                self ._prepare_and_wait (total_delay )
                print ('Wait complete, now executing key sequence (fallback)...')
                print ('Now actions are â†’ \\ â†’ Enter â†’ \\ then continue')
                if KEYBOARD_AVAILABLE :
                    self ._send_backslash_sequence (lambda key :keyboard .send ('enter'if key =='{ENTER}'else key ))
                    print (f'Backslash sequence completed (fallback) after {total_delay } second delay + key execution')
                else :
                    print ('Keyboard module not available for fallback input')
            except Exception as e2 :
                print (f'Both autoit and keyboard methods failed: {e }, {e2 }')
                print (f'Warning: If you have a slow PC, you may need to increase the key sequence delay beyond {total_delay } seconds')

    def _prepare_and_wait (self ,total_delay ):
        if self .automation and hasattr (self .automation ,'send_webhook_notification'):
            self .automation .send_webhook_notification ('roblox_detected','ðŸŽ® RobloxPlayerBeta.exe Detected',f'Now waiting {total_delay } seconds before executing key sequence...',color =2664261 )
        time .sleep (total_delay )

    def _send_backslash_sequence (self ,send_func ):
        send_func ('\\')
        time .sleep (0.5 )
        send_func ('{ENTER}')
        time .sleep (0.5 )
        send_func ('\\')

    def focus_roblox_window (self ):
        try :
            if WIN32_AVAILABLE :

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
                    return True 
                else :
                    return False 
            else :
                return False 
        except Exception as e :
            return False 

    def is_roblox_running (self ):
        try :
            if WINAPI_AVAILABLE :
                try :
                    TH32CS_SNAPPROCESS =2 
                    snapshot =kernel32 .CreateToolhelp32Snapshot (TH32CS_SNAPPROCESS ,0 )
                    if snapshot ==-1 :
                        print ('Failed to create process snapshot for Roblox check')
                        return False 
                    try :
                        process_entry =PROCESSENTRY32 ()
                        process_entry .dwSize =ctypes .sizeof (PROCESSENTRY32 )
                        if kernel32 .Process32First (snapshot ,ctypes .byref (process_entry )):
                            while True :
                                exe_name =process_entry .szExeFile .decode ('utf-8',errors ='ignore')
                                if exe_name .lower ()=='robloxplayerbeta.exe':
                                    return True 
                                if not kernel32 .Process32Next (snapshot ,ctypes .byref (process_entry )):
                                    break 
                        return False 
                    finally :
                        kernel32 .CloseHandle (snapshot )
                except Exception as e :
                    print (f'Windows API process check failed: {e }')
            try :
                result =subprocess .run (['tasklist','/FI','IMAGENAME eq RobloxPlayerBeta.exe'],capture_output =True ,text =True ,check =False )
                return 'RobloxPlayerBeta.exe'in result .stdout 
            except Exception as e :
                print (f'Tasklist fallback failed: {e }')
                return False 
        except Exception as e :
            print (f'Error checking for Roblox process: {e }')
            return False 

    def wait_for_roblox_and_set_window_mode (self ,toggle_callback =None ):
        for i in range (120 ):
            if toggle_callback and (not toggle_callback ()):
                return False 
            if self .is_roblox_running ():
                time .sleep (3 )
                if self .roblox_window_mode =='windowed':
                    self .set_roblox_windowed ()
                else :
                    self .set_roblox_fullscreen ()
                return True 
            time .sleep (0.5 )
        print ('âš  Timeout waiting for RobloxPlayerBeta.exe to start')
        return False 

    def set_roblox_windowed (self ):
        try :
            if WIN32_AVAILABLE :

                def enum_windows_callback (hwnd ,windows ):
                    if win32gui .IsWindowVisible (hwnd ):
                        window_text =win32gui .GetWindowText (hwnd )
                        if 'Roblox'in window_text :
                            windows .append (hwnd )
                    return True 
                windows =[]
                win32gui .EnumWindows (enum_windows_callback ,windows )
                for hwnd in windows :
                    try :
                        win32gui .SetForegroundWindow (hwnd )
                        time .sleep (0.5 )
                        win32gui .ShowWindow (hwnd ,win32con .SW_RESTORE )
                        time .sleep (0.5 )
                        win32gui .ShowWindow (hwnd ,win32con .SW_MAXIMIZE )
                        time .sleep (0.5 )
                        print ('Set Roblox to windowed mode (maximized)')
                        return 
                    except Exception as window_error :
                        continue 
                print ('Warning: No Roblox windows found for windowed mode setting')
            else :
                print ('Win32 not available, using keyboard shortcut fallback for windowed mode...')
                try :
                    time .sleep (1 )
                    autoit .win_activate ('Roblox')
                    time .sleep (0.5 )
                    autoit .send ('{F11}')
                    time .sleep (0.5 )
                    autoit .send ('{F11}')
                    time .sleep (0.5 )
                    autoit .send ('!{SPACE}')
                    time .sleep (0.3 )
                    autoit .send ('x')
                    time .sleep (0.5 )
                    print ('Applied windowed mode using keyboard shortcuts')
                except Exception as fallback_error :
                    print (f'Fallback windowed mode failed: {fallback_error }')
                    print ('Roblox may not be in the desired window mode. Please adjust manually if needed.')
        except Exception as e :
            print (f'Error setting Roblox to windowed mode: {e }')

    def set_roblox_fullscreen (self ):
        try :
            if WIN32_AVAILABLE :

                def enum_windows_callback (hwnd ,windows ):
                    if win32gui .IsWindowVisible (hwnd ):
                        window_text =win32gui .GetWindowText (hwnd )
                        if 'Roblox'in window_text :
                            windows .append (hwnd )
                    return True 
                windows =[]
                win32gui .EnumWindows (enum_windows_callback ,windows )
                for hwnd in windows :
                    try :
                        win32gui .SetForegroundWindow (hwnd )
                        time .sleep (0.5 )
                        print ('Attempting to set Roblox to fullscreen using F11 key...')
                        autoit .send ('{F11}')
                        time .sleep (1.5 )
                        placement =win32gui .GetWindowPlacement (hwnd )
                        if placement [1 ]==win32con .SW_MAXIMIZE or placement [1 ]==win32con .SW_SHOWMAXIMIZED :
                            print ('Set Roblox to fullscreen mode')
                            return 
                        else :
                            screen_width =win32gui .GetSystemMetrics (win32con .SM_CXSCREEN )
                            screen_height =win32gui .GetSystemMetrics (win32con .SM_CYSCREEN )
                            style =win32gui .GetWindowLong (hwnd ,win32con .GWL_STYLE )
                            style =style &~(win32con .WS_CAPTION |win32con .WS_THICKFRAME |win32con .WS_MINIMIZE |win32con .WS_MAXIMIZE |win32con .WS_SYSMENU )
                            win32gui .SetWindowLong (hwnd ,win32con .GWL_STYLE ,style )
                            win32gui .SetWindowPos (hwnd ,win32con .HWND_TOP ,0 ,0 ,screen_width ,screen_height ,win32con .SWP_SHOWWINDOW |win32con .SWP_FRAMECHANGED )
                            print ('Set Roblox to fullscreen mode (borderless)')
                            return 
                    except Exception as window_error :
                        continue 
                print ('Warning: No Roblox windows found for fullscreen setting')
            else :
                print ('Win32 not available, using F11 key fallback for fullscreen...')
                try :
                    time .sleep (1 )
                    autoit .win_activate ('Roblox')
                    time .sleep (0.5 )
                    autoit .send ('{F11}')
                    time .sleep (1.5 )
                    print ('Applied fullscreen mode using F11 key')
                except Exception as fallback_error :
                    print (f'Fallback fullscreen mode failed: {fallback_error }')
                    print ('You may need to manually press F11 to enter fullscreen mode')
        except Exception as e :
            print (f'Error setting Roblox to fullscreen mode: {e }')
            print ('You may need to manually press F11 to enter fullscreen mode')

    def test_auto_reconnect (self ):
        print ('Test auto reconnect triggered')
        original_enabled =self .auto_reconnect_enabled 
        original_timer =self .auto_reconnect_timer_start 
        try :
            self .auto_reconnect_enabled =True 
            self .auto_reconnect_timer_start =time .time ()-(self .auto_reconnect_time +1 )
            success =self .perform_auto_reconnect (lambda :True if self .automation else True )
            return success 
        except Exception as e :
            print (f'Error during test auto reconnect: {e }')
            return False 
        finally :
            self .auto_reconnect_enabled =original_enabled 
            self .auto_reconnect_timer_start =original_timer 

    def get_config_dict (self ):
        return {'auto_reconnect_enabled':self .auto_reconnect_enabled ,'auto_reconnect_time':self .auto_reconnect_time //60 ,'roblox_private_server_link':self .roblox_private_server_link ,'roblox_window_mode':self .roblox_window_mode ,'backslash_sequence_delay':self .backslash_sequence_delay }

    def load_config (self ,config_data ):
        if 'auto_reconnect_enabled'in config_data :
            self .auto_reconnect_enabled =bool (config_data ['auto_reconnect_enabled'])
        if 'auto_reconnect_time'in config_data :
            value =int (config_data ['auto_reconnect_time'])
            if value >1440 :
                self .auto_reconnect_time =max (60 ,min (86400 ,value ))
            else :
                self .auto_reconnect_time =max (60 ,min (86400 ,value *60 ))
        else :
            self .auto_reconnect_time =3600 
        if 'roblox_private_server_link'in config_data :
            self .roblox_private_server_link =str (config_data ['roblox_private_server_link'])
        if 'roblox_window_mode'in config_data :
            self .roblox_window_mode =str (config_data ['roblox_window_mode'])
        if 'backslash_sequence_delay'in config_data :
            self .backslash_sequence_delay =max (60.0 ,float (config_data ['backslash_sequence_delay']))

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