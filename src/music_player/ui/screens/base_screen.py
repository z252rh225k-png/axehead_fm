class BaseScreen:
    """Base class for all UI screens."""
    def draw(self, draw, state, bt_manager):
        """Draw the screen content.
        
        Args:
            draw: PIL ImageDraw object
            state: PlayerState instance
            bt_manager: BluetoothManager instance
        """
        pass
