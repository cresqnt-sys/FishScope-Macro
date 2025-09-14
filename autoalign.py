import autoit
import time
from screeninfo import get_monitors # <-- IMPORT THIS

def auto_align_camera(delay=2):
    """
    Executes a simplified alignment sequence using the 'autoit' backend.
    """
    print(f"Starting simplified auto-align in {delay} seconds... Please focus the Roblox window.")
    time.sleep(delay)

    # --- Optional but Recommended: Activate the Roblox Window ---
    if autoit.win_exists("Roblox"):
        print("Roblox window found. Activating...")
        autoit.win_activate("Roblox")
        time.sleep(0.3)  # Give the window a moment to become active
    else:
        print("Error: Roblox window not found. Please make sure the game is running.")
        return # Exit the function if the window isn't found

    # --- Part 1: Reset Character ---
    print("Step 1: Resetting character...")
    autoit.send("{ESC}")
    time.sleep(0.15)
    autoit.send("r")
    time.sleep(0.15)
    autoit.send("{ENTER}")
    # Increased sleep after reset to allow the character to respawn
    time.sleep(0.5)

    # --- Part 2: Align Camera via Mouse Drag (Centered) ---
    print("Step 2: Aligning camera with mouse...")

    # --- THIS IS THE CORRECTED PART ---
    # Use screeninfo to get the primary monitor's dimensions
    try:
        monitor = get_monitors()[0]
        screen_width = monitor.width
        screen_height = monitor.height
    except IndexError:
        print("Error: Could not detect a monitor. Using default 1920x1080.")
        screen_width, screen_height = 1920, 1080
    # ------------------------------------

    center_x = screen_width // 2
    start_y = int(screen_height * 0.2)  # Start 20% down from the top
    end_y = int(screen_height * 0.8)    # End 80% down from the top

    # Move to the start position instantly (speed=0)
    autoit.mouse_move(x=center_x, y=start_y, speed=0)
    time.sleep(0.1)

    # Press and hold the right mouse button
    autoit.mouse_down("right")
    time.sleep(0.1)

    # Drag the mouse down to the end position with a smooth speed
    autoit.mouse_move(x=center_x, y=end_y, speed=10)
    time.sleep(0.1)

    # Release the right mouse button
    autoit.mouse_up("right")

    # --- Part 3: Zoom Camera In and Out ---
    print("Step 3: Resetting camera zoom...")
    time.sleep(0.15)
    # The second parameter is the number of "clicks" to scroll
    autoit.mouse_wheel("up", 10)   # Zoom In
    time.sleep(0.15)
    autoit.mouse_wheel("down", 10) # Zoom Out

    print("\nSimplified auto-align sequence complete.")

if __name__ == "__main__":
    # To run this script, execute it from your terminal.
    # You will have 2 seconds to click on the Roblox window.
    auto_align_camera()