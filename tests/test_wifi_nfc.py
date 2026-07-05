import unittest
from unittest.mock import patch

from music_player.catalog.resolver import resolve_playback_assets
from music_player.hardware.nfc_reader import is_wifi_tag, parse_wifi_ndef


class WifiNfcTests(unittest.TestCase):
    def test_wifi_tag_detection_with_provisioning_marker(self):
        self.assertTrue(is_wifi_tag("nfc_wifi_provision", "ssid=MyNetwork|pass=Secret123|auth=WPA2"))

    def test_parse_wifi_payload_supports_key_value_format(self):
        payload = "ssid=MyNetwork|pass=Secret123|auth=WPA2"
        parsed = parse_wifi_ndef(payload)
        self.assertEqual(parsed, {
            "ssid": "MyNetwork",
            "password": "Secret123",
            "security": "WPA2",
        })

    @patch("music_player.catalog.resolver.socket.gethostname", return_value="raspberrypi")
    @patch("music_player.catalog.resolver.load_catalog")
    def test_resolve_qr_entry_with_template_placeholders(self, mock_load_catalog, _mock_gethostname):
        mock_load_catalog.return_value = {
            "qr_01": {
                "type": "qr",
                "title": "Web UI",
                "text": "http://${hostname}:${port}/api/dashboard",
            }
        }

        entry = resolve_playback_assets("qr_01")

        self.assertEqual(entry["type"], "qr")
        self.assertEqual(entry["text"], "http://raspberrypi:5000/api/dashboard")
        self.assertEqual(entry["title"], "Web UI")


if __name__ == "__main__":
    unittest.main()
