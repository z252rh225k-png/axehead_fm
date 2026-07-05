import time
from music_player.ui.screens.base_screen import BaseScreen
from music_player.ui.assets import draw_bluetooth_icon


class BTMenuScreen(BaseScreen):
    """Displays Bluetooth device menu for pairing/connecting."""
    
    def draw(self, draw, state, bt_manager):
        draw.text((4, 2), "BLUETOOTH MENU", fill="white")
        draw.line((0, 13, 128, 13), fill="white")
        
        if bt_manager.connected_device:
            draw_bluetooth_icon(draw, 115, 2)
            
        if state.menu_message and time.time() < state.menu_message_timeout:
            draw.text((20, 32), state.menu_message, fill="white")
            return

        devices = bt_manager.discovered_devices
        idx_disconnect = len(devices)
        idx_back = len(devices) + 1

        start_offset = 0
        if state.menu_index >= 3:
            start_offset = state.menu_index - 2

        for line_idx in range(3):
            item_idx = start_offset + line_idx
            y_pos = 18 + (line_idx * 15)
            cursor = ">" if item_idx == state.menu_index else " "
            
            if item_idx < len(devices):
                dev = devices[item_idx]
                name = dev['name'][:16]
                draw.text((4, y_pos), f"{cursor} {name}", fill="white")
            elif item_idx == idx_disconnect:
                connected = bt_manager.connected_device
                disp_text = f"Disconnect ({connected['name'][:8]})" if connected else "Disconnect"
                draw.text((4, y_pos), f"{cursor} {disp_text}", fill="white")
            elif item_idx == idx_back:
                draw.text((4, y_pos), f"{cursor} [Back to Player]", fill="white")
