import socket
import subprocess
import time
from typing import Optional, Tuple, List, Dict


class NetworkManager:
    """Small wrapper around nmcli for simple Wi-Fi provisioning."""

    def __init__(self):
        self.connected = False
        self.current_ssid: Optional[str] = None
        self.current_ip: Optional[str] = None
        self.hotspot_active = False

    def connect_wifi(self, ssid: str, password: str, security: str = "WPA2") -> Tuple[bool, str]:
        """Attempt to connect to a Wi-Fi network using nmcli."""
        try:
            subprocess.run(["nmcli", "radio", "wifi", "on"], check=False, capture_output=True, text=True)
            result = subprocess.run(
                ["nmcli", "device", "wifi", "connect", ssid, "password", password],
                capture_output=True,
                text=True,
                timeout=25,
            )
            if result.returncode != 0:
                message = (result.stderr or result.stdout or "Connection failed").strip()
                return False, message

            time.sleep(3)
            if self._verify_connection(ssid, timeout=12):
                self.connected = True
                self.current_ssid = ssid
                self.current_ip = self._get_local_ip()
                return True, f"Connected to {ssid}"
            return False, f"Connected but could not verify {ssid}"
        except FileNotFoundError:
            return False, "nmcli is not available"
        except subprocess.TimeoutExpired:
            return False, "Connection timeout"
        except Exception as exc:  # pragma: no cover - defensive branch
            return False, f"Network error: {exc}"

    def list_saved_connections(self) -> Tuple[bool, List[Dict[str, str]]]:
        """Return saved NetworkManager connections for display in the web UI."""
        try:
            result = subprocess.run(
                ["nmcli", "-t", "-f", "NAME,ACTIVE,DEVICE", "connection", "show"],
                capture_output=True,
                text=True,
                timeout=15,
            )
            if result.returncode != 0:
                return False, []

            connections: List[Dict[str, str]] = []
            for line in result.stdout.splitlines():
                if not line.strip():
                    continue
                parts = [part.strip() for part in line.split(":")]
                if len(parts) < 3:
                    continue
                name, active, device = parts[0], parts[1], parts[2]
                connections.append({
                    "name": name,
                    "active": active.lower() in {"yes", "true", "1"},
                    "device": device or "—",
                    "ssid": name,
                })
            return True, connections
        except FileNotFoundError:
            return False, []
        except Exception:  # pragma: no cover - defensive branch
            return False, []

    def connect_saved_connection(self, connection_name: str) -> Tuple[bool, str]:
        """Activate a previously saved connection profile."""
        try:
            subprocess.run(["nmcli", "radio", "wifi", "on"], check=False, capture_output=True, text=True)
            result = subprocess.run(
                ["nmcli", "connection", "up", "id", connection_name],
                capture_output=True,
                text=True,
                timeout=25,
            )
            if result.returncode != 0:
                message = (result.stderr or result.stdout or "Could not activate connection").strip()
                return False, message

            time.sleep(2)
            self.connected = True
            self.current_ssid = connection_name
            self.current_ip = self._get_local_ip()
            return True, f"Activated {connection_name}"
        except FileNotFoundError:
            return False, "nmcli is not available"
        except subprocess.TimeoutExpired:
            return False, "Connection timeout"
        except Exception as exc:  # pragma: no cover - defensive branch
            return False, f"Network error: {exc}"

    def forget_connection(self, connection_name: str) -> Tuple[bool, str]:
        """Delete a saved NetworkManager connection profile."""
        try:
            result = subprocess.run(
                ["nmcli", "connection", "delete", connection_name],
                capture_output=True,
                text=True,
                timeout=15,
            )
            if result.returncode != 0:
                message = (result.stderr or result.stdout or "Could not delete connection").strip()
                return False, message
            return True, f"Deleted {connection_name}"
        except FileNotFoundError:
            return False, "nmcli is not available"
        except Exception as exc:  # pragma: no cover - defensive branch
            return False, f"Network error: {exc}"

    def disconnect(self) -> bool:
        try:
            subprocess.run(["nmcli", "radio", "wifi", "off"], check=True, capture_output=True, text=True)
            self.connected = False
            self.current_ssid = None
            self.current_ip = None
            return True
        except Exception:  # pragma: no cover - defensive branch
            return False

    def start_hotspot(self, ssid: str = "AxeheadFM", password: str = "pi1234567") -> Tuple[bool, str]:
        try:
            result = subprocess.run(
                ["nmcli", "device", "wifi", "hotspot", "ifname", "wlan0", "ssid", ssid, "password", password],
                capture_output=True,
                text=True,
                timeout=15,
            )
            if result.returncode != 0:
                return False, (result.stderr or result.stdout).strip()
            time.sleep(2)
            self.hotspot_active = True
            return True, f"Hotspot '{ssid}' started"
        except Exception as exc:  # pragma: no cover - defensive branch
            return False, f"Hotspot error: {exc}"

    def is_connected(self) -> bool:
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=2)
            return True
        except (socket.timeout, OSError):
            return False

    def get_status(self) -> dict:
        return {
            "connected": self.is_connected(),
            "ssid": self.current_ssid,
            "ip": self.current_ip,
            "hotspot": self.hotspot_active,
        }

    def _verify_connection(self, ssid: str, timeout: int = 12) -> bool:
        start = time.time()
        while time.time() - start < timeout:
            try:
                result = subprocess.run(
                    ["nmcli", "-t", "-f", "ACTIVE,SSID", "device", "wifi", "list"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode == 0 and ssid in result.stdout and "yes" in result.stdout:
                    return True
            except Exception:  # pragma: no cover - defensive branch
                pass
            time.sleep(1)
        return False

    @staticmethod
    def _get_local_ip() -> Optional[str]:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.connect(("8.8.8.8", 80))
            ip = sock.getsockname()[0]
            sock.close()
            return ip
        except Exception:  # pragma: no cover - defensive branch
            return None


_network_manager: Optional[NetworkManager] = None


def get_network_manager() -> NetworkManager:
    global _network_manager
    if _network_manager is None:
        _network_manager = NetworkManager()
    return _network_manager
