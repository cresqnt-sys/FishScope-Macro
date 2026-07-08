from path_runner import run_macro

macro_actions = [
    {'type': 'key_press', 'key': 'w'},
    {'type': 'wait', 'duration': 1},
    {'type': 'key_press', 'key': 'a'},
    {'type': 'wait', 'duration': 4882},
    {'type': 'key_press', 'key': 'd'},
    {'type': 'wait', 'duration': 10},
    {'type': 'key_release', 'key': 'a'},
    {'type': 'wait', 'duration': 583},
    {'type': 'key_release', 'key': 'd'},
    {'type': 'wait', 'duration': 1466},
    {'type': 'key_press', 'key': 'a'},
    {'type': 'wait', 'duration': 857},
    {'type': 'key_release', 'key': 'a'},
    {'type': 'wait', 'duration': 262},
    {'type': 'key_release', 'key': 'w'},
    {'type': 'wait', 'duration': 187},
    {'type': 'key_press', 'key': 's'},
    {'type': 'wait', 'duration': 326},
    {'type': 'key_release', 'key': 's'},
    {'type': 'wait', 'duration': 149},
    {'type': 'key_press', 'key': 'd'},
    {'type': 'wait', 'duration': 1056},
    {'type': 'key_press', 'key': 'w'},
    {'type': 'wait', 'duration': 1673},
    {'type': 'key_release', 'key': 'd'},
    {'type': 'wait', 'duration': 2385},
    {'type': 'key_release', 'key': 'w'},
]

if __name__ == '__main__':
    run_macro(macro_actions)
