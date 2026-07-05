import subprocess
import time
import threading
import json

class AudioDeviceManager:
    """
    Monitors ALSA/PipeWire audio devices and automatically routes audio output.
    
    Priority:
    1. Headphones (3.5mm jack) if plugged in
    2. USB Audio if available
    3. HDMI as fallback
    """
    
    # Device card/names to match
    DEVICE_PRIORITY = [
        {"name": "Headphones", "patterns": ["bcm2835 Headphones", "Headphones"], "sink_name": "alsa_output.bcm2835-headphones"},
        {"name": "USB", "patterns": ["USB Audio", "UACDemo"], "sink_name": "alsa_output.usb"},
        {"name": "HDMI", "patterns": ["vc4-hdmi", "HDMI"], "sink_name": "alsa_output.hdmi"}
    ]
    
    def __init__(self):
        self.current_device = None
        self.available_devices = {}
        self.monitor_thread = None
        self.is_running = False
        self._update_lock = threading.Lock()
    
    def start_monitor(self):
        """Start background thread monitoring audio devices."""
        if self.is_running:
            return
        
        self.is_running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        print("[AudioDeviceManager] Started monitoring audio devices")
    
    def stop_monitor(self):
        """Stop the monitoring thread."""
        self.is_running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2)
        print("[AudioDeviceManager] Stopped monitoring")
    
    def _monitor_loop(self):
        """Background loop that detects available devices and switches output."""
        check_interval = 2  # Check every 2 seconds
        last_device = None
        
        while self.is_running:
            try:
                available = self._detect_available_devices()
                best_device = self._select_best_device(available)
                
                if best_device != last_device:
                    self._switch_to_device(best_device)
                    last_device = best_device
                    
            except Exception as e:
                print(f"[AudioDeviceManager] Error in monitor loop: {e}")
            
            time.sleep(check_interval)
    
    def _detect_available_devices(self):
        """
        Detect available audio devices using pactl/PipeWire.
        Returns dict with device names and their properties.
        """
        available = {}
        
        try:
            # Use pactl to list sinks
            result = subprocess.run(
                ["pactl", "list", "sinks"],
                capture_output=True,
                text=True,
                timeout=2
            )
            
            current_sink = None
            for line in result.stdout.splitlines():
                if line.startswith("Sink"):
                    # Extract sink name
                    parts = line.split("#")
                    if len(parts) > 1:
                        current_sink = parts[1].strip()
                
                if "Name:" in line and current_sink:
                    sink_name = line.split("Name:")[-1].strip()
                    
                    # Check if this sink is available/plugged in
                    for device_config in self.DEVICE_PRIORITY:
                        for pattern in device_config["patterns"]:
                            if pattern.lower() in line.lower() or pattern.lower() in sink_name.lower():
                                available[device_config["name"]] = {
                                    "sink_name": sink_name,
                                    "priority": self.DEVICE_PRIORITY.index(device_config)
                                }
                                break
        
        except Exception as e:
            print(f"[AudioDeviceManager] Error detecting devices: {e}")
        
        with self._update_lock:
            self.available_devices = available
        
        return available
    
    def _select_best_device(self, available_devices):
        """
        Select the best device based on priority.
        Returns device name string.
        """
        if not available_devices:
            return None
        
        # Sort by priority (lower index = higher priority)
        sorted_devices = sorted(
            available_devices.items(),
            key=lambda x: x[1]["priority"]
        )
        
        best = sorted_devices[0][0]
        
        with self._update_lock:
            if best != self.current_device:
                print(f"[AudioDeviceManager] Best device available: {best}")
        
        return best
    
    def _switch_to_device(self, device_name):
        """
        Switch PipeWire/PulseAudio default output to the specified device.
        """
        if not device_name:
            return
        
        try:
            # Find the sink for this device
            result = subprocess.run(
                ["pactl", "list", "sinks", "short"],
                capture_output=True,
                text=True,
                timeout=2
            )
            
            target_sink = None
            for line in result.stdout.splitlines():
                for config in self.DEVICE_PRIORITY:
                    if config["name"] == device_name:
                        for pattern in config["patterns"]:
                            if pattern.lower() in line.lower():
                                parts = line.split()
                                if parts:
                                    target_sink = parts[0]  # Sink index or name
                                break
            
            if target_sink:
                # Set as default sink
                subprocess.run(
                    ["pactl", "set-default-sink", target_sink],
                    capture_output=True,
                    timeout=2
                )
                
                with self._update_lock:
                    self.current_device = device_name
                
                print(f"[AudioDeviceManager] ✓ Switched audio to: {device_name}")
                return True
        
        except Exception as e:
            print(f"[AudioDeviceManager] Error switching device: {e}")
        
        return False
    
    def get_current_device(self):
        """Get the currently active device name."""
        with self._update_lock:
            return self.current_device
    
    def get_available_devices(self):
        """Get list of currently available devices."""
        with self._update_lock:
            return list(self.available_devices.keys())
