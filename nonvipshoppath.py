from path_runner import run_macro, drag_camera_up
from time import sleep

macro_actions = [
    {'type': 'key_press', 'key': 'w'},
    {'type': 'key_press', 'key': 'a'},
    {'type': 'wait', 'duration': 6668},
    {'type': 'key_release', 'key': 'a'},
    {'type': 'wait', 'duration': 32},
    {'type': 'key_press', 'key': 'd'},
    {'type': 'wait', 'duration': 557},
    {'type': 'key_release', 'key': 'd'},
    {'type': 'wait', 'duration': 1492},
    {'type': 'key_press', 'key': 'a'},
    {'type': 'wait', 'duration': 1051},
    {'type': 'key_release', 'key': 'a'},
    {'type': 'wait', 'duration': 360},
    {'type': 'key_release', 'key': 'w'},
    {'type': 'wait', 'duration': 336},
    {'type': 'key_press', 'key': 's'},
    {'type': 'wait', 'duration': 258},
    {'type': 'key_release', 'key': 's'},
    {'type': 'wait', 'duration': 157},
    {'type': 'key_press', 'key': 'Key.space'},
    {'type': 'wait', 'duration': 121},
    {'type': 'key_press', 'key': 'a'},
    {'type': 'wait', 'duration': 99},
    {'type': 'key_release', 'key': 'Key.space'},
    {'type': 'wait', 'duration': 515},
    {'type': 'key_press', 'key': 'Key.space'},
    {'type': 'wait', 'duration': 203},
    {'type': 'key_release', 'key': 'Key.space'},
    {'type': 'wait', 'duration': 735},
    {'type': 'key_release', 'key': 'a'},
    {'type': 'wait', 'duration': 99},
    {'type': 'key_press', 'key': 'w'},
    {'type': 'wait', 'duration': 2866},
    {'type': 'key_release', 'key': 'w'},
    {'type': 'wait', 'duration': 47},
    {'type': 'key_press', 'key': 'd'},
    {'type': 'wait', 'duration': 100},
    {'type': 'key_press', 'key': 'Key.space'},
    {'type': 'wait', 'duration': 198},
    {'type': 'key_release', 'key': 'Key.space'},
    {'type': 'wait', 'duration': 973},
    {'type': 'key_release', 'key': 'd'},
    {'type': 'wait', 'duration': 191},
    {'type': 'key_press', 'key': 's'},
    {'type': 'wait', 'duration': 862},
    {'type': 'key_release', 'key': 's'},
    {'type': 'wait', 'duration': 766},
    {'type': 'key_press', 'key': 'e'},
    {'type': 'wait', 'duration': 121},
    {'type': 'key_release', 'key': 'e'},
]

if __name__ == '__main__':
    run_macro(macro_actions)
    print('Navigation complete. Waiting 1 second before camera adjustment...')
    sleep(1)
    print('Adjusting camera angle...')
    drag_camera_up()
    print('Camera adjusted. Waiting 4 seconds before continuing...')
    sleep(4)
    print('Navigation and camera adjustment complete. Ready for next phase.')
