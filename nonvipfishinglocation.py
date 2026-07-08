from path_runner import run_macro

macro_actions = [
    {'type': 'key_press', 'key': 'w'},
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
    {'type': 'key_release', 'key': 'w'},
]

if __name__ == '__main__':
    run_macro(macro_actions)
