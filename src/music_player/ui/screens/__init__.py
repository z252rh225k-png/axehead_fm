"""UI Screen modules for the music player."""

from music_player.ui.screens.base_screen import BaseScreen
from music_player.ui.screens.music_screen import MusicScreen
from music_player.ui.screens.volume_screen import VolumeScreen
from music_player.ui.screens.power_screen import PowerScreen
from music_player.ui.screens.waiting_screen import WaitingScreen
from music_player.ui.screens.bt_menu_screen import BTMenuScreen

__all__ = [
    "BaseScreen",
    "MusicScreen",
    "VolumeScreen",
    "PowerScreen",
    "WaitingScreen",
    "BTMenuScreen",
]
