# Made using ReTask by JustSoftware & cresqnt

CPU_INTENSIVE_HIGH_ACCURACY_SLEEP = True
from pynput.keyboard import Key, Controller as KeyboardController
from pynput.mouse import Button, Controller as MouseController
from mousekey import MouseKey
from time import sleep, perf_counter

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

def run_macro(macro, delay=2, emergency_stop_check=None):
    # Break initial delay into smaller chunks for emergency stop checking
    for _ in range(int(delay * 10)):  # Check every 0.1 seconds
        if emergency_stop_check and emergency_stop_check():
            print("Emergency stop detected during non-VIP fishing location macro initial delay")
            return
        sleep(0.1)

    for action in macro:
        # Check for emergency stop before each action
        if emergency_stop_check and emergency_stop_check():
            print("Emergency stop detected during non-VIP fishing location macro")
            return
            
        match action["type"]:
            case "wait":
                # Break wait duration into smaller chunks for emergency stop checking
                wait_duration = action["duration"] / 1000.0
                chunks = int(wait_duration * 10)  # Check every 0.1 seconds
                remainder = wait_duration % 0.1
                
                for _ in range(chunks):
                    if emergency_stop_check and emergency_stop_check():
                        print("Emergency stop detected during non-VIP fishing location macro wait")
                        return
                    sleep(0.1)
                
                if remainder > 0:
                    if emergency_stop_check and emergency_stop_check():
                        print("Emergency stop detected during non-VIP fishing location macro wait")
                        return
                    sleep(remainder)
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


macro_actions = [{'type': 'key_press', 'key': 'w'},
{'type': 'wait', 'duration': 1},
{'type': 'key_press', 'key': 'a'},
{'type': 'wait', 'duration': 6740},
{'type': 'key_release', 'key': 'a'},
{'type': 'wait', 'duration': 163},
{'type': 'key_press', 'key': 'd'},
{'type': 'wait', 'duration': 564},
{'type': 'key_release', 'key': 'd'},
{'type': 'wait', 'duration': 2098},
{'type': 'key_press', 'key': 'a'},
{'type': 'wait', 'duration': 651},
{'type': 'key_release', 'key': 'a'},
{'type': 'wait', 'duration': 58},
{'type': 'key_release', 'key': 'w'},
{'type': 'wait', 'duration': 215},
{'type': 'key_press', 'key': 'd'},
{'type': 'wait', 'duration': 1034},
{'type': 'key_press', 'key': 'w'},
{'type': 'wait', 'duration': 3273},
{'type': 'key_release', 'key': 'd'},
{'type': 'wait', 'duration': 1427},
{'type': 'key_release', 'key': 'w'}]

if __name__ == "__main__":
    run_macro(macro_actions)