"""
Auto Sell Module for FishScope Macro

This module handles the automatic selling functionality for caught fish.
It was extracted from the main macro loop to allow for easier maintenance
and future enhancements.

Author: cresqnt
"""

import time
import autoit


class AutoSellManager:
    """
    Manages the automatic selling of caught fish in the fishing game.
    
    This class encapsulates all the logic needed to automatically sell
    caught fish, including clicking on items, navigating to sell buttons,
    and confirming sales.
    """
    
    def __init__(self, coordinates, apply_mouse_delay_callback=None):
        """
        Initialize the AutoSellManager.
        
        Args:
            coordinates (dict): Dictionary containing all UI coordinate positions
            apply_mouse_delay_callback (callable): Optional callback to apply additional mouse delays
        """
        self.coordinates = coordinates
        self.apply_mouse_delay = apply_mouse_delay_callback if apply_mouse_delay_callback else lambda: None
        
        # Auto sell settings
        self.auto_sell_enabled = True
        self.first_loop = True
        
        # Timing settings (can be adjusted for different game speeds)
        self.click_delay = 0.15  # Base delay between clicks
        self.move_speed = 3      # Mouse movement speed
    
    def set_auto_sell_enabled(self, enabled):
        """
        Enable or disable auto sell functionality.
        
        Args:
            enabled (bool): True to enable auto sell, False to disable
        """
        self.auto_sell_enabled = enabled
    
    def set_first_loop(self, is_first_loop):
        """
        Set whether this is the first loop (auto sell is skipped on first loop).
        
        Args:
            is_first_loop (bool): True if this is the first macro loop
        """
        self.first_loop = is_first_loop
    
    def update_coordinates(self, coordinates):
        """
        Update the coordinate dictionary.
        
        Args:
            coordinates (dict): Updated coordinate dictionary
        """
        self.coordinates = coordinates
    
    def set_timing_settings(self, click_delay=None, move_speed=None):
        """
        Update timing settings for auto sell actions.
        
        Args:
            click_delay (float): Delay between clicks in seconds
            move_speed (int): Mouse movement speed (1-10, higher is faster)
        """
        if click_delay is not None:
            self.click_delay = click_delay
        if move_speed is not None:
            self.move_speed = move_speed
    
    def should_perform_auto_sell(self):
        """
        Check if auto sell should be performed.
        
        Returns:
            bool: True if auto sell should be performed, False otherwise
        """
        return not self.first_loop and self.auto_sell_enabled
    
    def click_first_item(self):
        """
        Click on the first item in the inventory.
        
        Returns:
            bool: True if successful, False if coordinates not available
        """
        if 'first_item' not in self.coordinates:
            print("Warning: first_item coordinates not set")
            return False
        
        try:
            item_x, item_y = self.coordinates['first_item']
            autoit.mouse_move(item_x, item_y, self.move_speed)
            time.sleep(self.click_delay)
            autoit.mouse_click("left")
            self.apply_mouse_delay()
            time.sleep(self.click_delay)
            return True
        except Exception as e:
            print(f"Error clicking first item: {e}")
            return False
    
    def click_sell_button(self):
        """
        Click on the sell button.
        
        Returns:
            bool: True if successful, False if coordinates not available
        """
        if 'sell_button' not in self.coordinates:
            print("Warning: sell_button coordinates not set")
            return False
        
        try:
            sell_x, sell_y = self.coordinates['sell_button']
            autoit.mouse_move(sell_x, sell_y, self.move_speed)
            time.sleep(self.click_delay)
            autoit.mouse_click("left")
            self.apply_mouse_delay()
            time.sleep(self.click_delay)
            return True
        except Exception as e:
            print(f"Error clicking sell button: {e}")
            return False
    
    def click_confirm_button(self):
        """
        Click on the confirm button to finalize the sale.
        
        Returns:
            bool: True if successful, False if coordinates not available
        """
        if 'confirm_button' not in self.coordinates:
            print("Warning: confirm_button coordinates not set")
            return False
        
        try:
            confirm_x, confirm_y = self.coordinates['confirm_button']
            autoit.mouse_move(confirm_x, confirm_y, self.move_speed)
            time.sleep(self.click_delay)
            autoit.mouse_click("left")
            self.apply_mouse_delay()
            time.sleep(self.click_delay)
            return True
        except Exception as e:
            print(f"Error clicking confirm button: {e}")
            return False
    
    def perform_auto_sell_sequence(self):
        """
        Perform the complete auto sell sequence.
        
        This method executes the full auto sell process:
        1. Click first item
        2. Click sell button
        3. Click confirm button
        
        Returns:
            bool: True if the complete sequence was successful, False otherwise
        """
        if not self.should_perform_auto_sell():
            if self.first_loop:
                self.first_loop = False
            return True  # Return True as this is expected behavior
        
        # Step 1: Click first item
        if not self.click_first_item():
            return False
        
        # Step 2: Click sell button
        if not self.click_sell_button():
            return False
        
        # Step 3: Click confirm button
        if not self.click_confirm_button():
            return False
        
        return True
    
    def perform_manual_sell(self):
        """
        Perform a manual sell sequence (ignores first_loop and enabled flags).
        
        This can be used for testing or manual selling operations.
        
        Returns:
            bool: True if successful, False otherwise
        """
        success = (self.click_first_item() and 
                  self.click_sell_button() and 
                  self.click_confirm_button())
        
        return success
    
    def get_status(self):
        """
        Get the current status of the auto sell manager.
        
        Returns:
            dict: Dictionary containing current status information
        """
        return {
            'auto_sell_enabled': self.auto_sell_enabled,
            'first_loop': self.first_loop,
            'click_delay': self.click_delay,
            'move_speed': self.move_speed,
            'coordinates_set': {
                'first_item': 'first_item' in self.coordinates,
                'sell_button': 'sell_button' in self.coordinates,
                'confirm_button': 'confirm_button' in self.coordinates
            }
        }
    
    def validate_coordinates(self):
        """
        Validate that all required coordinates are available.
        
        Returns:
            tuple: (bool, list) - (True if all valid, list of missing coordinates)
        """
        required_coords = ['first_item', 'sell_button', 'confirm_button']
        missing_coords = []
        
        for coord in required_coords:
            if coord not in self.coordinates:
                missing_coords.append(coord)
            elif not isinstance(self.coordinates[coord], (tuple, list)) or len(self.coordinates[coord]) != 2:
                missing_coords.append(f"{coord} (invalid format)")
        
        return len(missing_coords) == 0, missing_coords