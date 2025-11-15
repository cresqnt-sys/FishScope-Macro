import time 
import autoit 

class AutoSellManager :

    def __init__ (self ,coordinates ,apply_mouse_delay_callback =None ):
        self .coordinates =coordinates 
        self .apply_mouse_delay =apply_mouse_delay_callback if apply_mouse_delay_callback else lambda :None 
        self .auto_sell_enabled =True 
        self .first_loop =True 
        self .click_delay =0.15 
        self .move_speed =3 

    def set_auto_sell_enabled (self ,enabled ):
        self .auto_sell_enabled =enabled 

    def set_first_loop (self ,is_first_loop ):
        self .first_loop =is_first_loop 

    def update_coordinates (self ,coordinates ):
        self .coordinates =coordinates 

    def set_timing_settings (self ,click_delay =None ,move_speed =None ):
        if click_delay is not None :
            self .click_delay =click_delay 
        if move_speed is not None :
            self .move_speed =move_speed 

    def should_perform_auto_sell (self ):
        return not self .first_loop and self .auto_sell_enabled 

    def click_first_item (self ):
        if 'first_item'not in self .coordinates :
            print ('Warning: first_item coordinates not set')
            return False 
        try :
            item_x ,item_y =self .coordinates ['first_item']
            autoit .mouse_move (item_x ,item_y ,self .move_speed )
            time .sleep (self .click_delay )
            autoit .mouse_click ('left')
            self .apply_mouse_delay ()
            time .sleep (self .click_delay )
            return True 
        except Exception as e :
            print (f'Error clicking first item: {e }')
            return False 

    def click_sell_button (self ):
        if 'sell_button'not in self .coordinates :
            print ('Warning: sell_button coordinates not set')
            return False 
        try :
            sell_x ,sell_y =self .coordinates ['sell_button']
            autoit .mouse_move (sell_x ,sell_y ,self .move_speed )
            time .sleep (self .click_delay )
            autoit .mouse_click ('left')
            self .apply_mouse_delay ()
            time .sleep (self .click_delay )
            return True 
        except Exception as e :
            print (f'Error clicking sell button: {e }')
            return False 

    def click_confirm_button (self ):
        if 'confirm_button'not in self .coordinates :
            print ('Warning: confirm_button coordinates not set')
            return False 
        try :
            confirm_x ,confirm_y =self .coordinates ['confirm_button']
            autoit .mouse_move (confirm_x ,confirm_y ,self .move_speed )
            time .sleep (self .click_delay )
            autoit .mouse_click ('left')
            self .apply_mouse_delay ()
            time .sleep (self .click_delay )
            return True 
        except Exception as e :
            print (f'Error clicking confirm button: {e }')
            return False 

    def perform_auto_sell_sequence (self ):
        if not self .should_perform_auto_sell ():
            if self .first_loop :
                self .first_loop =False 
            return True 
        if not self .click_first_item ():
            return False 
        if not self .click_sell_button ():
            return False 
        if not self .click_confirm_button ():
            return False 
        return True 

    def perform_manual_sell (self ):
        success =self .click_first_item ()and self .click_sell_button ()and self .click_confirm_button ()
        return success 

    def get_status (self ):
        return {'auto_sell_enabled':self .auto_sell_enabled ,'first_loop':self .first_loop ,'click_delay':self .click_delay ,'move_speed':self .move_speed ,'coordinates_set':{'first_item':'first_item'in self .coordinates ,'sell_button':'sell_button'in self .coordinates ,'confirm_button':'confirm_button'in self .coordinates }}

    def validate_coordinates (self ):
        required_coords =['first_item','sell_button','confirm_button']
        missing_coords =[]
        for coord in required_coords :
            if coord not in self .coordinates :
                missing_coords .append (coord )
            elif not isinstance (self .coordinates [coord ],(tuple ,list ))or len (self .coordinates [coord ])!=2 :
                missing_coords .append (f'{coord } (invalid format)')
        return (len (missing_coords )==0 ,missing_coords )