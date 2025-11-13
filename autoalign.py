import autoit
import time
from screeninfo import get_monitors

def auto_align_camera(delay=2, emergency_stop_check=None):
    for _ in range(int(delay * 10)):
        if emergency_stop_check and emergency_stop_check():
            return
        time.sleep(0.1)
    if emergency_stop_check and emergency_stop_check():
        return
    if autoit.win_exists('Roblox'):
        autoit.win_activate('Roblox')
        time.sleep(0.3)
    else:
        return
    if emergency_stop_check and emergency_stop_check():
        return
    autoit.send('{ESC}')
    time.sleep(0.15)
    if emergency_stop_check and emergency_stop_check():
        return
    autoit.send('r')
    time.sleep(0.15)
    if emergency_stop_check and emergency_stop_check():
        return
    autoit.send('{ENTER}')
    time.sleep(0.5)
    if emergency_stop_check and emergency_stop_check():
        return
    try:
        monitor = get_monitors()[0]
        screen_width = monitor.width
        screen_height = monitor.height
    except IndexError:
        screen_width, screen_height = (1920, 1080)
    center_x = screen_width // 2
    start_y = int(screen_height * 0.2)
    end_y = int(screen_height * 0.8)
    autoit.mouse_move(x=center_x, y=start_y, speed=0)
    time.sleep(0.1)
    if emergency_stop_check and emergency_stop_check():
        return
    autoit.mouse_down('right')
    time.sleep(0.1)
    if emergency_stop_check and emergency_stop_check():
        autoit.mouse_up('right')
        return
    autoit.mouse_move(x=center_x, y=end_y, speed=10)
    time.sleep(0.1)
    autoit.mouse_up('right')
    if emergency_stop_check and emergency_stop_check():
        return
    time.sleep(0.15)
    if emergency_stop_check and emergency_stop_check():
        return
    autoit.mouse_wheel('up', 10)
    time.sleep(0.15)
    if emergency_stop_check and emergency_stop_check():
        return
    autoit.mouse_wheel('down', 10)
if __name__ == '__main__':
    auto_align_camera()