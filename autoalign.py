import autoit
import time
from screeninfo import get_monitors # <-- IMPORT THIS

def auto_align_camera(delay=2, emergency_stop_check=None):
    """
    Executes a simplified alignment sequence using the 'autoit' backend.
    
    Args:
        delay: Initial delay before starting
        emergency_stop_check: Optional function that returns True if should stop immediately
    """    
    # Break delay into smaller chunks to check for emergency stop
    for _ in range(int(delay * 10)):  # Check every 0.1 seconds
        if emergency_stop_check and emergency_stop_check():
            return
        time.sleep(0.1)

    # --- Optional but Recommended: Activate the Roblox Window ---
    if emergency_stop_check and emergency_stop_check():
        return
        
    if autoit.win_exists("Roblox"):
        autoit.win_activate("Roblox")
        time.sleep(0.3)  # Give the window a moment to become active
    else:
        return # Exit the function if the window isn't found

    # --- Part 1: Reset Character ---
    if emergency_stop_check and emergency_stop_check():
        return
        
    autoit.send("{ESC}")
    time.sleep(0.15)
    
    if emergency_stop_check and emergency_stop_check():
        return
        
    autoit.send("r")
    time.sleep(0.15)
    
    if emergency_stop_check and emergency_stop_check():
        return
        
    autoit.send("{ENTER}")
    # Increased sleep after reset to allow the character to respawn
    time.sleep(0.5)

    # --- Part 2: Align Camera via Mouse Drag (Centered) ---
    if emergency_stop_check and emergency_stop_check():
        return

    # --- THIS IS THE CORRECTED PART ---
    # Use screeninfo to get the primary monitor's dimensions
    try:
        monitor = get_monitors()[0]
        screen_width = monitor.width
        screen_height = monitor.height
    except IndexError:
        screen_width, screen_height = 1920, 1080
    # ------------------------------------

    center_x = screen_width // 2
    start_y = int(screen_height * 0.2)  # Start 20% down from the top
    end_y = int(screen_height * 0.8)    # End 80% down from the top

    # Move to the start position instantly (speed=0)
    autoit.mouse_move(x=center_x, y=start_y, speed=0)
    time.sleep(0.1)

    if emergency_stop_check and emergency_stop_check():
        return

    # Press and hold the right mouse button
    autoit.mouse_down("right")
    time.sleep(0.1)

    if emergency_stop_check and emergency_stop_check():
        autoit.mouse_up("right")  # Release mouse button before exiting
        return

    # Drag the mouse down to the end position with a smooth speed
    autoit.mouse_move(x=center_x, y=end_y, speed=10)
    time.sleep(0.1)

    # Release the right mouse button
    autoit.mouse_up("right")

    # --- Part 3: Zoom Camera In and Out ---
    if emergency_stop_check and emergency_stop_check():
        return
        
    time.sleep(0.15)
    
    if emergency_stop_check and emergency_stop_check():
        return
        
    # The second parameter is the number of "clicks" to scroll
    autoit.mouse_wheel("up", 10)   # Zoom In
    time.sleep(0.15)
    
    if emergency_stop_check and emergency_stop_check():
        return
        
    autoit.mouse_wheel("down", 10) # Zoom Out

if __name__ == "__main__":
    # To run this script, execute it from your terminal.
    # You will have 2 seconds to click on the Roblox window.
    auto_align_camera()