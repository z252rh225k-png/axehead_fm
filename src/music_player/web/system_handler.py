import subprocess
from typing import Dict, List, Optional

class SystemHandler:
    def __init__(self):
        self.services = [
            "music-player",
            "music-web",
            "music-splash"
        ]

    def get_service_status(self, service_name: str) -> Dict:
        """Get the status of a specific systemd service."""
        if service_name not in self.services:
            return {"error": "Unknown service"}

        try:
            # Get active state with a short timeout
            status_cmd = ["systemctl", "is-active", f"{service_name}.service"]
            result = subprocess.run(status_cmd, capture_output=True, text=True, timeout=5)
            active_state = result.stdout.strip()

            # Get detailed status
            show_cmd = [
                "systemctl", "show", f"{service_name}.service", 
                "--property=ActiveState,SubState,MainPID,Status,LoadState,ActiveEnterTimestamp"
            ]
            result = subprocess.run(show_cmd, capture_output=True, text=True, timeout=5)
            details = {}
            for line in result.stdout.splitlines():
                if "=" in line:
                    parts = line.split("=", 1)
                    if len(parts) == 2:
                        details[parts[0]] = parts[1]

            return {
                "name": service_name,
                "active": active_state == "active",
                "status": active_state,
                "details": details
            }
        except subprocess.TimeoutExpired:
            return {"name": service_name, "error": "Timeout", "status": "unknown"}
        except Exception as e:
            return {"name": service_name, "error": str(e), "status": "error"}

    def get_all_statuses(self) -> List[Dict]:
        return [self.get_service_status(s) for s in self.services]

    def get_system_info(self) -> Dict:
        """Collect general system health information."""
        info = {}
        try:
            # CPU Temp (Pi specific)
            temp_cmd = ["vcgencmd", "measure_temp"]
            result = subprocess.run(temp_cmd, capture_output=True, text=True, timeout=2)
            info["temperature"] = result.stdout.strip().replace("temp=", "")
        except:
            info["temperature"] = "unknown"

        try:
            # Memory usage
            mem_cmd = ["free", "-m"]
            result = subprocess.run(mem_cmd, capture_output=True, text=True, timeout=2)
            info["memory"] = result.stdout
        except:
            pass

        try:
            # Disk space
            disk_cmd = ["df", "-h", "/"]
            result = subprocess.run(disk_cmd, capture_output=True, text=True, timeout=2)
            info["disk"] = result.stdout
        except:
            pass

        try:
            # Uptime
            uptime_cmd = ["uptime", "-p"]
            result = subprocess.run(uptime_cmd, capture_output=True, text=True, timeout=2)
            info["uptime"] = result.stdout.strip()
        except:
            pass

        return info

    def control_service(self, service_name: str, action: str) -> Dict:
        """Start, stop, or restart a service."""
        if service_name not in self.services:
            return {"ok": False, "error": "Unknown service"}
        
        if action not in ["start", "stop", "restart"]:
            return {"ok": False, "error": "Invalid action"}

        try:
            # We assume sudo is configured as per deploy.sh
            cmd = ["sudo", "systemctl", action, f"{service_name}.service"]
            subprocess.run(cmd, check=True, capture_output=True, timeout=10)
            return {"ok": True, "message": f"Service {service_name} {action}ed successfully"}
        except subprocess.CalledProcessError as e:
            return {"ok": False, "error": e.stderr if hasattr(e, 'stderr') else str(e)}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def get_logs(self, service_name: str, lines: int = 50, log_file: Optional[str] = None) -> Dict:
        """Get the latest journal entries or a specific log file for a service."""
        if service_name not in self.services:
            return {"error": "Unknown service"}

        try:
            if log_file:
                # Read from custom log file if provided
                cmd = ["sudo", "tail", "-n", str(lines), log_file]
            else:
                # Default to journalctl
                cmd = ["sudo", "journalctl", "-u", f"{service_name}.service", "-n", str(lines), "--no-pager"]
                
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            return {
                "name": service_name,
                "logs": result.stdout,
                "source": "file" if log_file else "journal"
            }
        except subprocess.TimeoutExpired:
            return {"error": "Log retrieval timed out"}
        except Exception as e:
            return {"error": str(e)}
