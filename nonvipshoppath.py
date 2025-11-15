CPU_INTENSIVE_HIGH_ACCURACY_SLEEP =True 
from pynput .keyboard import Key ,Controller as KeyboardController 
from pynput .mouse import Button ,Controller as MouseController 
from mousekey import MouseKey 
from time import sleep ,perf_counter 
from screeninfo import get_monitors 
kc =KeyboardController ()
mc =MouseController ()
mkey =MouseKey ()
pynput_special_keys ={'Key.alt':Key .alt ,'Key.alt_l':Key .alt_l ,'Key.alt_r':Key .alt_r ,'Key.backspace':Key .backspace ,'Key.caps_lock':Key .caps_lock ,'Key.cmd':Key .cmd ,'Key.cmd_l':Key .cmd_l ,'Key.cmd_r':Key .cmd_r ,'Key.ctrl':Key .ctrl ,'Key.ctrl_l':Key .ctrl_l ,'Key.ctrl_r':Key .ctrl_r ,'Key.delete':Key .delete ,'Key.down':Key .down ,'Key.end':Key .end ,'Key.enter':Key .enter ,'Key.esc':Key .esc ,'Key.f1':Key .f1 ,'Key.f2':Key .f2 ,'Key.f3':Key .f3 ,'Key.f4':Key .f4 ,'Key.f5':Key .f5 ,'Key.f6':Key .f6 ,'Key.f7':Key .f7 ,'Key.f8':Key .f8 ,'Key.f9':Key .f9 ,'Key.f10':Key .f10 ,'Key.f11':Key .f11 ,'Key.f12':Key .f12 ,'Key.home':Key .home ,'Key.insert':Key .insert ,'Key.left':Key .left ,'Key.menu':Key .menu ,'Key.num_lock':Key .num_lock ,'Key.page_down':Key .page_down ,'Key.page_up':Key .page_up ,'Key.pause':Key .pause ,'Key.print_screen':Key .print_screen ,'Key.right':Key .right ,'Key.scroll_lock':Key .scroll_lock ,'Key.shift':Key .shift ,'Key.shift_l':Key .shift_l ,'Key.shift_r':Key .shift_r ,'Key.space':Key .space ,'Key.tab':Key .tab ,'Key.up':Key .up }
pynput_special_buttons ={'Button.left':Button .left ,'Button.right':Button .right ,'Button.middle':Button .middle }

def run_macro (macro ,delay =2 ,emergency_stop_check =None ):
    for _ in range (int (delay *10 )):
        if emergency_stop_check and emergency_stop_check ():
            print ('Emergency stop detected during non-VIP shop path macro initial delay')
            return 
        sleep (0.1 )
    for action in macro :
        if emergency_stop_check and emergency_stop_check ():
            print ('Emergency stop detected during non-VIP shop path macro')
            return 
        match action ['type']:
            case 'wait':
                wait_duration =action ['duration']/1000.0 
                chunks =int (wait_duration *10 )
                remainder =wait_duration %0.1 
                for _ in range (chunks ):
                    if emergency_stop_check and emergency_stop_check ():
                        print ('Emergency stop detected during non-VIP shop path macro wait')
                        return 
                    sleep (0.1 )
                if remainder >0 :
                    if emergency_stop_check and emergency_stop_check ():
                        print ('Emergency stop detected during non-VIP shop path macro wait remainder')
                        return 
                    sleep (remainder )
            case 'key_press':
                key =action ['key']
                kc .press (pynput_special_keys .get (key ,key ))
            case 'key_release':
                key =action ['key']
                kc .release (pynput_special_keys .get (key ,key ))
            case 'mouse_movement':
                mkey .move_to (int (action ['x']),int (action ['y']))
            case 'mouse_press':
                mc .press (pynput_special_buttons [action ['button']])
            case 'mouse_release':
                mc .release (pynput_special_buttons [action ['button']])
            case 'mouse_scroll':
                if 'x'in action :
                    mkey .move_to (int (action ['x']),int (action ['y']))
                mc .scroll (action ['dx'],action ['dy'])

def drag_camera_up ():
    try :
        monitor =get_monitors ()[0 ]
        screen_width =monitor .width 
        screen_height =monitor .height 
    except IndexError :
        print ('Error: Could not detect a monitor. Using default 1920x1080.')
        screen_width ,screen_height =(1920 ,1080 )
    center_x =screen_width //2 
    start_y =int (screen_height *0.8 )
    end_y =int (screen_height *0.2 )
    mkey .move_to (center_x ,start_y )
    sleep (0.1 )
    mc .press (Button .right )
    sleep (0.1 )
    mkey .move_to (center_x ,end_y )
    sleep (0.1 )
    mc .release (Button .right )
macro_actions =[{'type':'key_press','key':'w'},{'type':'key_press','key':'a'},{'type':'wait','duration':6668 },{'type':'key_release','key':'a'},{'type':'wait','duration':32 },{'type':'key_press','key':'d'},{'type':'wait','duration':557 },{'type':'key_release','key':'d'},{'type':'wait','duration':1492 },{'type':'key_press','key':'a'},{'type':'wait','duration':1051 },{'type':'key_release','key':'a'},{'type':'wait','duration':360 },{'type':'key_release','key':'w'},{'type':'wait','duration':336 },{'type':'key_press','key':'s'},{'type':'wait','duration':258 },{'type':'key_release','key':'s'},{'type':'wait','duration':157 },{'type':'key_press','key':'Key.space'},{'type':'wait','duration':121 },{'type':'key_press','key':'a'},{'type':'wait','duration':99 },{'type':'key_release','key':'Key.space'},{'type':'wait','duration':515 },{'type':'key_press','key':'Key.space'},{'type':'wait','duration':203 },{'type':'key_release','key':'Key.space'},{'type':'wait','duration':735 },{'type':'key_release','key':'a'},{'type':'wait','duration':99 },{'type':'key_press','key':'w'},{'type':'wait','duration':2866 },{'type':'key_release','key':'w'},{'type':'wait','duration':47 },{'type':'key_press','key':'d'},{'type':'wait','duration':100 },{'type':'key_press','key':'Key.space'},{'type':'wait','duration':198 },{'type':'key_release','key':'Key.space'},{'type':'wait','duration':973 },{'type':'key_release','key':'d'},{'type':'wait','duration':191 },{'type':'key_press','key':'s'},{'type':'wait','duration':862 },{'type':'key_release','key':'s'},{'type':'wait','duration':766 },{'type':'key_press','key':'e'},{'type':'wait','duration':121 },{'type':'key_release','key':'e'}]
if __name__ =='__main__':
    run_macro (macro_actions )
    print ('Navigation complete. Waiting 1 second before camera adjustment...')
    sleep (1 )
    print ('Adjusting camera angle...')
    drag_camera_up ()
    print ('Camera adjusted. Waiting 4 seconds before continuing...')
    sleep (4 )
    print ('Navigation and camera adjustment complete. Ready for next phase.')