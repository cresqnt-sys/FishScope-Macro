"""
Auto-Reconnect module for FishScope Macro

This module handles all auto-reconnect functionality including:
- Timing and scheduling of reconnects
- Roblox process management (closing/launching)
- Window mode management
- Private server launching
- Keyboard input sequences for game setup
"""

import time
import os
import sys
import subprocess
import webbrowser
import autoit
import ctypes
from ctypes import wintypes

try:
    import win32gui
    import win32con
    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False
    win32gui = None
    win32con = None

try:
    import keyboard
    KEYBOARD_AVAILABLE = True
except ImportError:
    KEYBOARD_AVAILABLE = False

# Windows API constants and function definitions for compiled executable compatibility
PROCESS_TERMINATE = 0x0001
PROCESS_QUERY_INFORMATION = 0x0400

# Define Windows API functions using ctypes for better PyInstaller compatibility
try:
    kernel32 = ctypes.windll.kernel32
    shell32 = ctypes.windll.shell32
    user32 = ctypes.windll.user32
    
    # Define ShellExecute for launching URLs
    shell32.ShellExecuteW.argtypes = [
        wintypes.HWND,    # hwnd
        wintypes.LPCWSTR, # lpOperation
        wintypes.LPCWSTR, # lpFile
        wintypes.LPCWSTR, # lpParameters
        wintypes.LPCWSTR, # lpDirectory
        ctypes.c_int      # nShowCmd
    ]
    shell32.ShellExecuteW.restype = wintypes.HINSTANCE
    
    # Define CreateToolhelp32Snapshot and related functions for process enumeration
    kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    
    # Define PROCESSENTRY32 structure
    class PROCESSENTRY32(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.POINTER(wintypes.ULONG)),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", wintypes.LONG),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", wintypes.CHAR * 260)
        ]
    
    kernel32.Process32First.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32)]
    kernel32.Process32First.restype = wintypes.BOOL
    
    kernel32.Process32Next.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32)]
    kernel32.Process32Next.restype = wintypes.BOOL
    
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    
    kernel32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel32.TerminateProcess.restype = wintypes.BOOL
    
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    
    WINAPI_AVAILABLE = True
except Exception as e:
    WINAPI_AVAILABLE = False
    print(f"Warning: Windows API functions not available: {e}")


class AutoReconnectManager:
    """Manages all auto-reconnect functionality for the FishScope macro"""
    
    def __init__(self, automation=None):
        """Initialize the auto-reconnect manager
        
        Args:
            automation: Reference to the main automation object for callbacks
        """
        self.automation = automation
        
        # Auto reconnect settings
        self.auto_reconnect_enabled = False
        self.auto_reconnect_time = 3600  # Default 60 minutes (3600 seconds)
        self.auto_reconnect_timer_start = None
        self.auto_reconnect_in_progress = False
        self.roblox_private_server_link = ""
        self.roblox_window_mode = "windowed"  # "windowed" or "fullscreen"
        self.backslash_sequence_delay = 60.0  # Default 60 seconds delay between key presses (minimum enforced)
        
        # Check if we're running in a PyInstaller executable
        self.is_pyinstaller = getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')
        if self.is_pyinstaller:
            print("Running in PyInstaller executable - using Windows API for process management")
    
    def _get_exe_directory(self):
        """Get the directory where the executable is located (for PyInstaller compatibility)"""
        if self.is_pyinstaller:
            # When running as compiled executable
            return os.path.dirname(sys.executable)
        else:
            # When running as script
            return os.path.dirname(os.path.abspath(__file__))
        
    def set_automation_reference(self, automation):
        """Set reference to the main automation object"""
        self.automation = automation
        
    def should_auto_reconnect(self):
        """Check if auto reconnect should be triggered"""
        if not self.auto_reconnect_enabled or not self.auto_reconnect_timer_start:
            return False
        
        # Check if auto sell is active or we're in selling phases
        if self.automation:
            # Block reconnect during auto sell or shop navigation
            if (hasattr(self.automation, 'automation_phase') and 
                self.automation.automation_phase in ['pre_sell', 'selling']):
                print("Auto reconnect blocked: currently in auto sell phase")
                return False
            
            # Block reconnect if external script is running (shop path navigation)
            if (hasattr(self.automation, 'external_script_running') and 
                self.automation.external_script_running):
                print("Auto reconnect blocked: external script (navigation) is running")
                return False
            
            # Block reconnect if in sell cycle
            if (hasattr(self.automation, 'in_sell_cycle') and 
                self.automation.in_sell_cycle):
                print("Auto reconnect blocked: in sell cycle")
                return False
        
        elapsed_time = time.time() - self.auto_reconnect_timer_start
        return elapsed_time >= self.auto_reconnect_time  # Compare seconds to seconds

    def get_auto_reconnect_time_remaining(self):
        """Get remaining time until auto reconnect in seconds"""
        if not self.auto_reconnect_enabled or not self.auto_reconnect_timer_start:
            return None
        
        elapsed_time = time.time() - self.auto_reconnect_timer_start
        total_time = self.auto_reconnect_time  # Already in seconds
        remaining = total_time - elapsed_time
        return max(0, remaining)

    def start_timer(self):
        """Start the auto reconnect timer"""
        self.auto_reconnect_timer_start = time.time()
        
    def reset_timer(self):
        """Reset the auto reconnect timer"""
        self.auto_reconnect_timer_start = time.time()
        
    def stop_timer(self):
        """Stop the auto reconnect timer"""
        self.auto_reconnect_timer_start = None

    def interruptible_sleep(self, duration, toggle_callback=None):
        """Sleep for the specified duration while checking for auto reconnect every 0.1 seconds
        
        Args:
            duration: Sleep duration in seconds
            toggle_callback: Function to check if macro should continue running
            
        Returns:
            True if sleep completed normally
            False if macro was stopped
            "auto_reconnect" if auto reconnect should be triggered
        """
        steps = int(duration * 10)  # Check every 0.1 seconds
        for i in range(steps):
            # Check if macro is stopped (if callback provided)
            if toggle_callback and not toggle_callback():
                return False
            if self.should_auto_reconnect():
                return "auto_reconnect"
            time.sleep(0.1)
        return True

    def perform_auto_reconnect(self, toggle_callback=None):
        """Perform the auto reconnect sequence with enhanced error handling for PyInstaller
        
        Args:
            toggle_callback: Function to check if macro should continue running
            
        Returns:
            True if reconnect was successful
            False if reconnect failed
        """
        try:
            # Set flag to disable other macro functions
            self.auto_reconnect_in_progress = True
            
            if self.is_pyinstaller:
                print("Auto-reconnect starting in compiled executable mode")

            if self.automation and hasattr(self.automation, 'send_webhook_notification'):
                self.automation.send_webhook_notification(
                    'roblox_reconnected',
                    "🔄 Auto Reconnect Triggered",
                    f"Reconnecting after {self.auto_reconnect_time} seconds...",
                    color=0x17a2b8
                )

            print("Closing Roblox instances...")
            self.close_roblox_instances()
            time.sleep(5)

            launch_success = False
            if self.roblox_private_server_link.strip():
                print("Attempting to launch private server...")
                launch_success = self.launch_private_server()
                if launch_success:
                    print("Private server launch successful")
                    if not self._execute_reconnect_sequence(toggle_callback):
                        print("Reconnect sequence failed after private server launch")
                        self.auto_reconnect_in_progress = False
                        return False
                else:
                    print("Private server launch failed, continuing with reconnect sequence...")
                    if not self._execute_reconnect_sequence(toggle_callback):
                        print("Reconnect sequence failed without private server")
                        self.auto_reconnect_in_progress = False
                        return False
            else:
                print("No private server link provided, proceeding with standard reconnect...")
                if not self._execute_reconnect_sequence(toggle_callback):
                    print("Standard reconnect sequence failed")
                    self.auto_reconnect_in_progress = False
                    return False

            self.reset_timer()
            self.auto_reconnect_in_progress = False

            if self.automation and hasattr(self.automation, 'send_roblox_reconnected_notification'):
                self.automation.send_roblox_reconnected_notification()

            print("Auto-reconnect completed successfully")
            return True

        except Exception as e:
            error_msg = f"Auto Reconnect Error: {str(e)}"
            print(error_msg)
            if self.automation and hasattr(self.automation, 'send_error_notification'):
                self.automation.send_error_notification("Auto Reconnect Error", str(e))
            self.auto_reconnect_in_progress = False
            self.reset_timer()
            return False

    def _wait_with_checks(self, seconds, toggle_callback=None):
        """Wait for specified seconds while checking for macro stop
        
        Args:
            seconds: Number of seconds to wait
            toggle_callback: Function to check if macro should continue running
            
        Returns:
            True if wait completed normally
            False if macro was stopped
        """
        for i in range(seconds * 10):  # Check every 0.1 seconds
            if toggle_callback and not toggle_callback():
                return False
            time.sleep(0.1)
        return True

    def _execute_reconnect_sequence(self, toggle_callback):
        """Execute the common reconnect sequence pattern
        
        Args:
            toggle_callback: Function to check if macro should continue running
            
        Returns:
            True if sequence completed successfully
            False if sequence failed
        """
        if self.wait_for_roblox_and_set_window_mode(toggle_callback):
            if self.automation and hasattr(self.automation, 'send_roblox_detected_notification'):
                self.automation.send_roblox_detected_notification()
        
        if not self._wait_with_checks(60, toggle_callback):
            return False
        
        self.press_backslash_sequence()
        time.sleep(2)
        return True

    def close_roblox_instances(self):
        """Close all Roblox instances using Windows API for better PyInstaller compatibility"""
        try:
            roblox_processes = ["RobloxPlayerBeta.exe", "RobloxStudioBeta.exe", "Roblox.exe"]
            processes_found = False
            
            # Method 1: Use Windows API to enumerate and terminate processes (PyInstaller-compatible)
            if WINAPI_AVAILABLE:
                try:
                    # Create snapshot of all processes
                    TH32CS_SNAPPROCESS = 0x00000002
                    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
                    
                    if snapshot == -1:  # INVALID_HANDLE_VALUE
                        print("Failed to create process snapshot")
                    else:
                        try:
                            # Initialize process entry structure
                            process_entry = PROCESSENTRY32()
                            process_entry.dwSize = ctypes.sizeof(PROCESSENTRY32)
                            
                            # Get first process
                            if kernel32.Process32First(snapshot, ctypes.byref(process_entry)):
                                while True:
                                    # Check if this is a Roblox process
                                    exe_name = process_entry.szExeFile.decode('utf-8', errors='ignore')
                                    
                                    if exe_name in roblox_processes:
                                        processes_found = True
                                        print(f"Found Roblox process: {exe_name} (PID: {process_entry.th32ProcessID})")
                                        
                                        # Open process with terminate access
                                        process_handle = kernel32.OpenProcess(
                                            PROCESS_TERMINATE, 
                                            False, 
                                            process_entry.th32ProcessID
                                        )
                                        
                                        if process_handle:
                                            # Terminate the process
                                            if kernel32.TerminateProcess(process_handle, 0):
                                                print(f"Successfully terminated {exe_name}")
                                            else:
                                                print(f"Failed to terminate {exe_name}")
                                            
                                            # Close process handle
                                            kernel32.CloseHandle(process_handle)
                                    
                                    # Get next process
                                    if not kernel32.Process32Next(snapshot, ctypes.byref(process_entry)):
                                        break
                            
                        finally:
                            # Close snapshot handle
                            kernel32.CloseHandle(snapshot)
                            
                except Exception as e:
                    print(f"Windows API process enumeration failed: {e}")
            
            # Method 2: Fallback to taskkill if Windows API is not available or failed
            if not WINAPI_AVAILABLE or not processes_found:
                try:
                    for process_name in roblox_processes:
                        try:
                            # Try using taskkill via subprocess (less reliable in PyInstaller but backup)
                            result = subprocess.run(['taskkill', '/f', '/im', process_name], 
                                                   capture_output=True, text=True, check=False)
                            if result.returncode == 0:
                                print(f"Taskkill successfully terminated {process_name}")
                            # Don't print errors for processes that don't exist
                        except Exception as e:
                            # Silently continue if subprocess fails
                            pass
                    
                except Exception as e:
                    print(f"Taskkill fallback failed: {e}")
            
            # Method 3: Use win32gui if available for window-based termination
            if WIN32_AVAILABLE:
                try:
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
                            print(f"Sent close message to Roblox window: {window_text}")
                        except Exception as e:
                            pass
                    
                    if windows:
                        processes_found = True
                        
                except Exception as e:
                    pass
            
            if processes_found:
                print("Roblox close sequence completed")
            else:
                print("No Roblox processes found to close")
                    
        except Exception as e:
            print(f"Error closing Roblox instances: {e}")

    def launch_private_server(self):
        """Launch Roblox private server using Windows API calls for better PyInstaller compatibility"""
        try:
            if not self.roblox_private_server_link.strip():
                print("No private server link provided")
                return False
            
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
            
            # Method 1: Windows API ShellExecute (most reliable for compiled executables)
            if WINAPI_AVAILABLE:
                try:
                    # Use ShellExecuteW to open the roblox:// URL
                    result = shell32.ShellExecuteW(
                        None,           # hwnd
                        "open",         # operation
                        roblox_url,     # file
                        None,           # parameters
                        None,           # directory
                        1               # nShowCmd (SW_NORMAL)
                    )
                    # ShellExecute returns a value > 32 on success
                    if result > 32:
                        print(f"Successfully launched Roblox using Windows API: {roblox_url}")
                        return True
                except Exception as e:
                    print(f"Windows API ShellExecute failed: {e}")
            
            # Method 2: PowerShell Start-Process (fallback for compiled executables)
            try:
                if WINAPI_AVAILABLE:
                    # Use Windows API to create a PowerShell process
                    powershell_cmd = f'powershell.exe -Command "Start-Process \\"{roblox_url}\\""'
                    
                    # Create process using Windows API
                    startup_info = ctypes.Structure()
                    startup_info.cb = ctypes.sizeof(startup_info)
                    process_info = ctypes.Structure()
                    
                    # This is more complex but more reliable than subprocess in PyInstaller
                    import tempfile
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.cmd', delete=False) as temp_file:
                        temp_file.write(f'start "" "{roblox_url}"\n')
                        temp_file.flush()
                        
                        # Execute the batch file
                        result = shell32.ShellExecuteW(
                            None,           # hwnd
                            "open",         # operation
                            temp_file.name, # file
                            None,           # parameters
                            None,           # directory
                            0               # nShowCmd (SW_HIDE)
                        )
                        
                        # Clean up temp file after a delay
                        import threading
                        def cleanup():
                            time.sleep(2)
                            try:
                                os.unlink(temp_file.name)
                            except:
                                pass
                        threading.Thread(target=cleanup, daemon=True).start()
                        
                        if result > 32:
                            print(f"Successfully launched Roblox using batch file method: {roblox_url}")
                            return True
                
            except Exception as e:
                print(f"Batch file method failed: {e}")
            
            # Method 3: Direct URL association (backup method)
            try:
                if WINAPI_AVAILABLE:
                    # Try to open URL using file association
                    result = shell32.ShellExecuteW(
                        None,           # hwnd
                        None,           # operation (default)
                        roblox_url,     # file
                        None,           # parameters
                        None,           # directory
                        1               # nShowCmd (SW_NORMAL)
                    )
                    if result > 32:
                        print(f"Successfully launched Roblox using URL association: {roblox_url}")
                        return True
            except Exception as e:
                print(f"URL association method failed: {e}")
            
            # Method 4: Fallback to webbrowser module (least reliable but better than nothing)
            try:
                webbrowser.open(roblox_url)
                print(f"Launched Roblox using webbrowser module: {roblox_url}")
                return True
            except Exception as e:
                print(f"Webbrowser module failed: {e}")
            
            # Method 5: Last resort - try os.system if all else fails (for development environment)
            try:
                escaped_url = f'"{roblox_url}"'
                command = f'start "" {escaped_url}'
                result = os.system(command)
                if result == 0:
                    print(f"Successfully launched Roblox using os.system: {roblox_url}")
                    return True
            except Exception as e:
                print(f"os.system method failed: {e}")
            
            print("All launch methods failed")
            return False
            
        except Exception as e:
            print(f"Error launching private server: {e}")
            return False

    def press_backslash_sequence(self):
        """Press backslash, enter, backslash sequence with total time delay"""
        # Compute total_delay before any try/except to ensure it's defined for exception handlers
        total_delay = max(60.0, self.backslash_sequence_delay)
        
        try:
            # Focus RobloxPlayerBeta.exe before sending the sequence
            self.focus_roblox_window()
            time.sleep(0.5)  # Small delay to ensure window is focused
            
            # Prepare and wait before executing sequence
            self._prepare_and_wait(total_delay)
            
            print("Wait complete, now executing key sequence...")
            print("Now actions are → \\ → Enter → \\ then continue")
            
            # Execute key sequence with autoit
            self._send_backslash_sequence(autoit.send)
            
            print(f"Backslash sequence completed after {total_delay} second delay + key execution")
            
        except Exception as e:
            # Try alternative method if autoit fails
            try:
                # Also try to focus with alternative method
                self.focus_roblox_window()
                time.sleep(0.5)
                
                # Prepare and wait before executing sequence
                self._prepare_and_wait(total_delay)
                
                print("Wait complete, now executing key sequence (fallback)...")
                print("Now actions are → \\ → Enter → \\ then continue")
                
                if KEYBOARD_AVAILABLE:
                    # Execute key sequence with keyboard module
                    self._send_backslash_sequence(lambda key: keyboard.send("enter" if key == "{ENTER}" else key))
                    
                    print(f"Backslash sequence completed (fallback) after {total_delay} second delay + key execution")
                else:
                    print("Keyboard module not available for fallback input")
            except Exception as e2:
                print(f"Both autoit and keyboard methods failed: {e}, {e2}")
                print(f"Warning: If you have a slow PC, you may need to increase the key sequence delay beyond {total_delay} seconds")

    def _prepare_and_wait(self, total_delay):
        """Send notification and wait for the specified delay"""
        # Send notification that RobloxPlayerBeta.exe was detected
        if self.automation and hasattr(self.automation, 'send_webhook_notification'):
            self.automation.send_webhook_notification(
                'roblox_detected',
                "🎮 RobloxPlayerBeta.exe Detected",
                f"Now waiting {total_delay} seconds before executing key sequence...",
                color=0x28a745
            )
        
        # Wait the full delay time BEFORE executing the key sequence
        time.sleep(total_delay)

    def _send_backslash_sequence(self, send_func):
        """Send the backslash sequence using the provided send function"""
        # Send first backslash
        send_func("\\")
        
        time.sleep(0.5)  # Brief delay between keys
        
        # Send enter
        send_func("{ENTER}")
        
        time.sleep(0.5)  # Brief delay between keys
        
        # Send final backslash
        send_func("\\")

    def focus_roblox_window(self):
        """Focus RobloxPlayerBeta.exe window"""
        try:
            if WIN32_AVAILABLE:
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
                    return True
                else:
                    return False
            else:
                return False
        except Exception as e:
            return False

    def is_roblox_running(self):
        """Check if RobloxPlayerBeta.exe is running using Windows API for PyInstaller compatibility"""
        try:
            # Method 1: Use Windows API to enumerate processes (PyInstaller-compatible)
            if WINAPI_AVAILABLE:
                try:
                    # Create snapshot of all processes
                    TH32CS_SNAPPROCESS = 0x00000002
                    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
                    
                    if snapshot == -1:  # INVALID_HANDLE_VALUE
                        print("Failed to create process snapshot for Roblox check")
                        return False
                    
                    try:
                        # Initialize process entry structure
                        process_entry = PROCESSENTRY32()
                        process_entry.dwSize = ctypes.sizeof(PROCESSENTRY32)
                        
                        # Get first process
                        if kernel32.Process32First(snapshot, ctypes.byref(process_entry)):
                            while True:
                                # Check if this is RobloxPlayerBeta.exe
                                exe_name = process_entry.szExeFile.decode('utf-8', errors='ignore')
                                
                                if exe_name.lower() == 'robloxplayerbeta.exe':
                                    return True
                                
                                # Get next process
                                if not kernel32.Process32Next(snapshot, ctypes.byref(process_entry)):
                                    break
                        
                        return False
                        
                    finally:
                        # Close snapshot handle
                        kernel32.CloseHandle(snapshot)
                        
                except Exception as e:
                    print(f"Windows API process check failed: {e}")
            
            # Method 2: Fallback to tasklist if Windows API is not available
            try:
                result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq RobloxPlayerBeta.exe'], 
                                      capture_output=True, text=True, check=False)
                return 'RobloxPlayerBeta.exe' in result.stdout
            except Exception as e:
                print(f"Tasklist fallback failed: {e}")
                return False
                
        except Exception as e:
            print(f"Error checking for Roblox process: {e}")
            return False

    def wait_for_roblox_and_set_window_mode(self, toggle_callback=None):
        """Wait for RobloxPlayerBeta.exe to start and set the appropriate window mode"""
        
        # Wait for Roblox to start (check every 0.5 seconds for up to 60 seconds)
        for i in range(120):  # 60 seconds total
            if toggle_callback and not toggle_callback():
                return False
                
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
                def enum_windows_callback(hwnd, windows):
                    if win32gui.IsWindowVisible(hwnd):
                        window_text = win32gui.GetWindowText(hwnd)
                        if "Roblox" in window_text:
                            windows.append(hwnd)
                    return True

                windows = []
                win32gui.EnumWindows(enum_windows_callback, windows)
                
                for hwnd in windows:
                    try:
                        # First, make sure the window is active and focused
                        win32gui.SetForegroundWindow(hwnd)
                        time.sleep(0.5)
                        
                        # Restore window if minimized (this will also exit fullscreen)
                        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                        time.sleep(0.5)
                        
                        # Maximize the window
                        win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
                        time.sleep(0.5)
                        
                        return
                    except Exception as window_error:
                        continue
                        
                print("Warning: No Roblox windows found for windowed mode setting")
            else:
                print("Win32 not available for windowed mode setting")
        except Exception as e:
            print(f"Error setting Roblox to windowed mode: {e}")

    def set_roblox_fullscreen(self):
        """Set Roblox to fullscreen mode"""
        try:
            if WIN32_AVAILABLE:
                def enum_windows_callback(hwnd, windows):
                    if win32gui.IsWindowVisible(hwnd):
                        window_text = win32gui.GetWindowText(hwnd)
                        if "Roblox" in window_text:
                            windows.append(hwnd)
                    return True

                windows = []
                win32gui.EnumWindows(enum_windows_callback, windows)
                
                for hwnd in windows:
                    try:
                        # First, make sure the window is active and focused
                        win32gui.SetForegroundWindow(hwnd)
                        time.sleep(0.5)
                        
                        # Method 1: Try using F11 key to enter true fullscreen mode (most reliable)
                        print("Attempting to set Roblox to fullscreen using F11 key...")
                        autoit.send("{F11}")
                        time.sleep(1.5)  # Give time for fullscreen transition
                        
                        # Verify if fullscreen worked by checking window state
                        placement = win32gui.GetWindowPlacement(hwnd)
                        if placement[1] == win32con.SW_MAXIMIZE or placement[1] == win32con.SW_SHOWMAXIMIZED:
                            return
                        else:
                            # Method 2: Fallback to window manipulation if F11 didn't work
                            # Get screen dimensions
                            screen_width = win32gui.GetSystemMetrics(win32con.SM_CXSCREEN)
                            screen_height = win32gui.GetSystemMetrics(win32con.SM_CYSCREEN)
                            
                            # Remove window borders and title bar for true fullscreen effect
                            style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
                            style = style & ~(win32con.WS_CAPTION | win32con.WS_THICKFRAME | win32con.WS_MINIMIZE | win32con.WS_MAXIMIZE | win32con.WS_SYSMENU)
                            win32gui.SetWindowLong(hwnd, win32con.GWL_STYLE, style)
                            
                            # Set window to cover entire screen
                            win32gui.SetWindowPos(hwnd, win32con.HWND_TOP, 0, 0, 
                                                screen_width, screen_height, 
                                                win32con.SWP_SHOWWINDOW | win32con.SWP_FRAMECHANGED)
                            return
                    except Exception as window_error:
                        continue
                        
                print("Warning: No Roblox windows found for fullscreen setting")
            else:
                # Fallback method using autoit key press (F11 for fullscreen) when win32 not available
                print("Win32 not available, using F11 key fallback for fullscreen...")
                time.sleep(1)
                autoit.send("{F11}")
                time.sleep(1.5)
                print("Sent F11 key for fullscreen mode")
        except Exception as e:
            print(f"Error setting Roblox to fullscreen mode: {e}")
            print("You may need to manually press F11 to enter fullscreen mode")

    def test_auto_reconnect(self):
        """Trigger an immediate auto reconnect for testing purposes
        
        Returns:
            bool: True if reconnect was successful, False otherwise
        """
        print("Test auto reconnect triggered")
        
        # Store current settings
        original_enabled = self.auto_reconnect_enabled
        original_timer = self.auto_reconnect_timer_start
        
        try:
            # Temporarily enable auto reconnect and force timer expiration
            self.auto_reconnect_enabled = True
            self.auto_reconnect_timer_start = time.time() - (self.auto_reconnect_time + 1)
            
            # Perform the reconnect sequence
            success = self.perform_auto_reconnect(lambda: True if self.automation else True)
            
            return success
            
        except Exception as e:
            print(f"Error during test auto reconnect: {e}")
            return False
        finally:
            # Restore original settings
            self.auto_reconnect_enabled = original_enabled
            self.auto_reconnect_timer_start = original_timer

    def get_config_dict(self):
        """Get configuration dictionary for saving settings"""
        return {
            'auto_reconnect_enabled': self.auto_reconnect_enabled,
            'auto_reconnect_time': self.auto_reconnect_time // 60,  # Save as minutes
            'roblox_private_server_link': self.roblox_private_server_link,
            'roblox_window_mode': self.roblox_window_mode,
            'backslash_sequence_delay': self.backslash_sequence_delay
        }
        
    def load_config(self, config_data):
        """Load configuration from saved data"""
        if 'auto_reconnect_enabled' in config_data:
            self.auto_reconnect_enabled = bool(config_data['auto_reconnect_enabled'])
        if 'auto_reconnect_time' in config_data:
            value = int(config_data['auto_reconnect_time'])
            # Check if this is already in seconds (large value) or in minutes (small value)
            if value > 1440:  # If value is more than 1440, it's likely already in seconds
                # Keep the value as seconds, enforce reasonable limits (1 minute to 24 hours)
                self.auto_reconnect_time = max(60, min(86400, value))
            else:
                # Value is in minutes, convert to seconds, enforce limits (1 minute to 24 hours)
                self.auto_reconnect_time = max(60, min(86400, value * 60))
        else:
            # If no config exists, use default of 60 minutes (3600 seconds)
            self.auto_reconnect_time = 3600
        if 'roblox_private_server_link' in config_data:
            self.roblox_private_server_link = str(config_data['roblox_private_server_link'])
        if 'roblox_window_mode' in config_data:
            self.roblox_window_mode = str(config_data['roblox_window_mode'])
        if 'backslash_sequence_delay' in config_data:
            # Ensure minimum of 60 seconds
            self.backslash_sequence_delay = max(60.0, float(config_data['backslash_sequence_delay']))

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