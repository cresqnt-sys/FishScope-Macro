# Made using ReTask by JustSoftware & cresqnt

CPU_INTENSIVE_HIGH_ACCURACY_SLEEP = True
from pynput.keyboard import Key, Controller as KeyboardController
from pynput.mouse import Button, Controller as MouseController
from mousekey import MouseKey
from time import sleep, perf_counter
from screeninfo import get_monitors

kc = KeyboardController()
mc = MouseController()
mkey = MouseKey()

pynput_special_keys = {
    "Key.alt": Key.alt,
    "Key.alt_l": Key.alt_l,
    "Key.alt_r": Key.alt_r,
    "Key.backspace": Key.backspace,
    "Key.caps_lock": Key.caps_lock,
    "Key.cmd": Key.cmd,
    "Key.cmd_l": Key.cmd_l,
    "Key.cmd_r": Key.cmd_r,
    "Key.ctrl": Key.ctrl,
    "Key.ctrl_l": Key.ctrl_l,
    "Key.ctrl_r": Key.ctrl_r,
    "Key.delete": Key.delete,
    "Key.down": Key.down,
    "Key.end": Key.end,
    "Key.enter": Key.enter,
    "Key.esc": Key.esc,
    "Key.f1": Key.f1,
    "Key.f2": Key.f2,
    "Key.f3": Key.f3,
    "Key.f4": Key.f4,
    "Key.f5": Key.f5,
    "Key.f6": Key.f6,
    "Key.f7": Key.f7,
    "Key.f8": Key.f8,
    "Key.f9": Key.f9,
    "Key.f10": Key.f10,
    "Key.f11": Key.f11,
    "Key.f12": Key.f12,
    "Key.home": Key.home,
    "Key.insert": Key.insert,
    "Key.left": Key.left,
    "Key.menu": Key.menu,
    "Key.num_lock": Key.num_lock,
    "Key.page_down": Key.page_down,
    "Key.page_up": Key.page_up,
    "Key.pause": Key.pause,
    "Key.print_screen": Key.print_screen,
    "Key.right": Key.right,
    "Key.scroll_lock": Key.scroll_lock,
    "Key.shift": Key.shift,
    "Key.shift_l": Key.shift_l,
    "Key.shift_r": Key.shift_r,
    "Key.space": Key.space,
    "Key.tab": Key.tab,
    "Key.up": Key.up
}

pynput_special_buttons = {
    "Button.left": Button.left,
    "Button.right": Button.right,
    "Button.middle": Button.middle
}

def run_macro(macro, delay=2):
    sleep(delay)

    for action in macro:
        match action["type"]:
            case "wait":
                sleep(action["duration"] / 1000.0)
            case "key_press":
                key = action["key"]
                kc.press(pynput_special_keys.get(key, key))
            case "key_release":
                key = action["key"]
                kc.release(pynput_special_keys.get(key, key))
            case "mouse_movement":
                mkey.move_to(int(action["x"]), int(action["y"]))
            case "mouse_press":
                mc.press(pynput_special_buttons[action["button"]])
            case "mouse_release":
                mc.release(pynput_special_buttons[action["button"]])
            case "mouse_scroll":
                if "x" in action:
                    mkey.move_to(int(action["x"]), int(action["y"]))
                mc.scroll(action["dx"], action["dy"])

def drag_camera_up():
    """Perform an upward camera drag using mouse movement"""
    try:
        monitor = get_monitors()[0]
        screen_width = monitor.width
        screen_height = monitor.height
    except IndexError:
        print("Error: Could not detect a monitor. Using default 1920x1080.")
        screen_width, screen_height = 1920, 1080
    
    center_x = screen_width // 2
    start_y = int(screen_height * 0.8)  # Start from bottom (80% down)
    end_y = int(screen_height * 0.2)    # End at top (20% down)
    
    # Move to start position and perform upward drag
    mkey.move_to(center_x, start_y)
    sleep(0.1)
    mc.press(Button.right)
    sleep(0.1)
    mkey.move_to(center_x, end_y)
    sleep(0.1)
    mc.release(Button.right)


macro_actions = [{'type': 'key_press', 'key': 'w'},
{'type': 'wait', 'duration': 1},
{'type': 'key_press', 'key': 'a'},
{'type': 'wait', 'duration': 4984},
{'type': 'key_release', 'key': 'a'},
{'type': 'wait', 'duration': 294},
{'type': 'key_release', 'key': 'w'},
{'type': 'wait', 'duration': 178},
{'type': 'key_press', 'key': 'd'},
{'type': 'wait', 'duration': 35},
{'type': 'key_press', 'key': 's'},
{'type': 'wait', 'duration': 21},
{'type': 'key_release', 'key': 's'},
{'type': 'wait', 'duration': 252},
{'type': 'key_press', 'key': 'w'},
{'type': 'wait', 'duration': 95},
{'type': 'key_release', 'key': 'd'},
{'type': 'wait', 'duration': 1111},
{'type': 'key_press', 'key': 'a'},
{'type': 'wait', 'duration': 963},
{'type': 'key_release', 'key': 'a'},
{'type': 'wait', 'duration': 195},
{'type': 'key_release', 'key': 'w'},
{'type': 'wait', 'duration': 263},
{'type': 'key_press', 'key': 's'},
{'type': 'wait', 'duration': 193},
{'type': 'key_release', 'key': 's'},
{'type': 'wait', 'duration': 169},
{'type': 'key_press', 'key': 'd'},
{'type': 'wait', 'duration': 191},
{'type': 'key_release', 'key': 'd'},
{'type': 'wait', 'duration': 166},
{'type': 'key_press', 'key': 'Key.space'},
{'type': 'wait', 'duration': 40},
{'type': 'key_press', 'key': 'w'},
{'type': 'wait', 'duration': 239},
{'type': 'key_release', 'key': 'Key.space'},
{'type': 'wait', 'duration': 107},
{'type': 'key_release', 'key': 'w'},
{'type': 'wait', 'duration': 168},
{'type': 'key_press', 'key': 'a'},
{'type': 'wait', 'duration': 578},
{'type': 'key_press', 'key': 'Key.space'},
{'type': 'wait', 'duration': 216},
{'type': 'key_release', 'key': 'Key.space'},
{'type': 'wait', 'duration': 346},
{'type': 'key_release', 'key': 'a'},
{'type': 'wait', 'duration': 324},
{'type': 'key_press', 'key': 'w'},
{'type': 'wait', 'duration': 450},
{'type': 'key_press', 'key': 'Key.space'},
{'type': 'wait', 'duration': 239},
{'type': 'key_release', 'key': 'Key.space'},
{'type': 'wait', 'duration': 745},
{'type': 'key_release', 'key': 'w'},
{'type': 'wait', 'duration': 185},
{'type': 'key_press', 'key': 'Key.space'},
{'type': 'wait', 'duration': 126},
{'type': 'key_press', 'key': 'd'},
{'type': 'wait', 'duration': 46},
{'type': 'key_release', 'key': 'Key.space'},
{'type': 'wait', 'duration': 176},
{'type': 'key_release', 'key': 'd'},
{'type': 'wait', 'duration': 307},
{'type': 'key_press', 'key': 'Key.space'},
{'type': 'wait', 'duration': 100},
{'type': 'key_press', 'key': 'd'},
{'type': 'wait', 'duration': 78},
{'type': 'key_release', 'key': 'Key.space'},
{'type': 'wait', 'duration': 499},
{'type': 'key_release', 'key': 'd'},
{'type': 'wait', 'duration': 277},
{'type': 'key_press', 'key': 's'},
{'type': 'wait', 'duration': 165},
{'type': 'key_release', 'key': 's'},
{'type': 'wait', 'duration': 1199},
{'type': 'key_press', 'key': 'e'},
{'type': 'wait', 'duration': 141},
{'type': 'key_release', 'key': 'e'}]

if __name__ == "__main__":
    # Execute the navigation macro
    run_macro([{'type': 'key_press', 'key': 'w'},
{'type': 'wait', 'duration': 1},
{'type': 'key_press', 'key': 'a'},
{'type': 'wait', 'duration': 4984},
{'type': 'key_release', 'key': 'a'},
{'type': 'wait', 'duration': 294},
{'type': 'key_release', 'key': 'w'},
{'type': 'wait', 'duration': 178},
{'type': 'key_press', 'key': 'd'},
{'type': 'wait', 'duration': 35},
{'type': 'key_press', 'key': 's'},
{'type': 'wait', 'duration': 21},
{'type': 'key_release', 'key': 's'},
{'type': 'wait', 'duration': 252},
{'type': 'key_press', 'key': 'w'},
{'type': 'wait', 'duration': 95},
{'type': 'key_release', 'key': 'd'},
{'type': 'wait', 'duration': 1111},
{'type': 'key_press', 'key': 'a'},
{'type': 'wait', 'duration': 963},
{'type': 'key_release', 'key': 'a'},
{'type': 'wait', 'duration': 195},
{'type': 'key_release', 'key': 'w'},
{'type': 'wait', 'duration': 263},
{'type': 'key_press', 'key': 's'},
{'type': 'wait', 'duration': 193},
{'type': 'key_release', 'key': 's'},
{'type': 'wait', 'duration': 169},
{'type': 'key_press', 'key': 'd'},
{'type': 'wait', 'duration': 191},
{'type': 'key_release', 'key': 'd'},
{'type': 'wait', 'duration': 166},
{'type': 'key_press', 'key': 'Key.space'},
{'type': 'wait', 'duration': 40},
{'type': 'key_press', 'key': 'w'},
{'type': 'wait', 'duration': 239},
{'type': 'key_release', 'key': 'Key.space'},
{'type': 'wait', 'duration': 107},
{'type': 'key_release', 'key': 'w'},
{'type': 'wait', 'duration': 168},
{'type': 'key_press', 'key': 'a'},
{'type': 'wait', 'duration': 578},
{'type': 'key_press', 'key': 'Key.space'},
{'type': 'wait', 'duration': 216},
{'type': 'key_release', 'key': 'Key.space'},
{'type': 'wait', 'duration': 346},
{'type': 'key_release', 'key': 'a'},
{'type': 'wait', 'duration': 324},
{'type': 'key_press', 'key': 'w'},
{'type': 'wait', 'duration': 450},
{'type': 'key_press', 'key': 'Key.space'},
{'type': 'wait', 'duration': 239},
{'type': 'key_release', 'key': 'Key.space'},
{'type': 'wait', 'duration': 745},
{'type': 'key_release', 'key': 'w'},
{'type': 'wait', 'duration': 185},
{'type': 'key_press', 'key': 'Key.space'},
{'type': 'wait', 'duration': 126},
{'type': 'key_press', 'key': 'd'},
{'type': 'wait', 'duration': 46},
{'type': 'key_release', 'key': 'Key.space'},
{'type': 'wait', 'duration': 176},
{'type': 'key_release', 'key': 'd'},
{'type': 'wait', 'duration': 307},
{'type': 'key_press', 'key': 'Key.space'},
{'type': 'wait', 'duration': 100},
{'type': 'key_press', 'key': 'd'},
{'type': 'wait', 'duration': 78},
{'type': 'key_release', 'key': 'Key.space'},
{'type': 'wait', 'duration': 499},
{'type': 'key_release', 'key': 'd'},
{'type': 'wait', 'duration': 277},
{'type': 'key_press', 'key': 's'},
{'type': 'wait', 'duration': 165},
{'type': 'key_release', 'key': 's'},
{'type': 'wait', 'duration': 1199},
{'type': 'key_press', 'key': 'e'},
{'type': 'wait', 'duration': 141},
{'type': 'key_release', 'key': 'e'}])
    
    # Wait 1 second after macro completion
    print("Navigation complete. Waiting 1 second before camera adjustment...")
    sleep(1)
    
    # Perform upward camera drag
    print("Adjusting camera angle...")
    drag_camera_up()
    
    # Wait 4 seconds before clicking SELL
    print("Camera adjusted. Waiting 4 seconds before SELL action...")
    sleep(4)
    
    # Click SELL (you can modify this part if needed)
    print("Ready to SELL!")