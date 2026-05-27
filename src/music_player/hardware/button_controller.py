from gpiozero import Button
from music_player.state.config import BUTTON_VOL_UP_PIN, BUTTON_VOL_DOWN_PIN, BUTTON_HOLD_TIME

class ButtonController:
    def __init__(self, toggle_callback, vol_up_callback, vol_down_callback):
        self.vol_up_btn = Button(BUTTON_VOL_UP_PIN, hold_time=BUTTON_HOLD_TIME)
        self.vol_down_btn = Button(BUTTON_VOL_DOWN_PIN, hold_time=BUTTON_HOLD_TIME)
        
        self.toggle_callback = toggle_callback
        self.vol_up_callback = vol_up_callback
        self.vol_down_callback = vol_down_callback
        
        # Set hold/press callbacks
        self.vol_up_btn.when_held = self._check_chord_hold
        self.vol_down_btn.when_held = self._check_chord_hold
        
        self.vol_up_btn.when_pressed = self._vol_up_pressed
        self.vol_down_btn.when_pressed = self._vol_down_pressed

    def _check_chord_hold(self):
        # Both held down
        if self.vol_up_btn.is_held and self.vol_down_btn.is_held:
            self.toggle_callback()

    def _vol_up_pressed(self):
        if self.vol_down_btn.is_pressed:
            return
        self.vol_up_callback()

    def _vol_down_pressed(self):
        if self.vol_up_btn.is_pressed:
            return
        self.vol_down_callback()
