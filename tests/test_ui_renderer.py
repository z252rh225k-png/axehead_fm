import unittest
from types import SimpleNamespace
from contextlib import contextmanager

from music_player.ui.renderer import UIRenderer


class FakeDraw:
    def __getattr__(self, _name):
        return lambda *args, **kwargs: None


class FakeDisplay:
    def __init__(self):
        self.canvas_calls = 0

    @contextmanager
    def canvas(self):
        self.canvas_calls += 1
        yield FakeDraw()


class UIRendererTests(unittest.TestCase):
    def test_qr_mode_skips_ui_overlay_rendering(self):
        renderer = UIRenderer()
        display = FakeDisplay()
        state = SimpleNamespace(
            is_shutting_down=False,
            current_state=0,
            show_volume_until=0,
            current_uid="abc123",
            current_media_type="qr",
            current_playing=True,
            current_artwork_img=None,
            current_title="",
            current_station_freq="96.7",
        )
        bt_manager = SimpleNamespace(connected_device=None)

        renderer.render(display, state, bt_manager)

        self.assertEqual(display.canvas_calls, 0)


if __name__ == "__main__":
    unittest.main()
