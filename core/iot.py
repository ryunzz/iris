#!/usr/bin/env python3
"""
IoT device client for Iris Smart Glasses.

Handles HTTP communication with ESP32 devices using dynamic discovery.
No hardcoded IP addresses - all devices discovered at runtime.
"""

import logging
import requests
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from .discovery import DeviceRegistry, DiscoveredDevice


logger = logging.getLogger(__name__)


class DeviceOfflineError(Exception):
    """Raised when a device is not available."""
    pass


class IoTClient:
    """
    HTTP client for communicating with Iris IoT devices.
    
    Uses DeviceRegistry for dynamic IP resolution.
    Supports mock mode with fake responses.
    """
    
    def __init__(self, registry: DeviceRegistry, mock: bool = False, timeout: float = 3.0):
        self.registry = registry
        self.mock = mock
        self.timeout = timeout
        
        # Device state cache (to reduce HTTP requests)
        self._device_states: Dict[str, Dict[str, Any]] = {}
        self._state_cache_timeout = timedelta(seconds=5)
        
        logger.info(f"IoT client initialized ({'mock' if mock else 'live'} mode)")
    
    def send_command(self, device_type: str, command: str) -> Dict[str, Any]:
        """
        Send command to a device.
        
        Args:
            device_type: Type of device ("light", "fan", etc.)
            command: Command to send ("on", "off", "low", "high", etc.)
            
        Returns:
            Device response dict
            
        Raises:
            DeviceOfflineError: If device is not available
        """
        if self.mock:
            return self._mock_response(device_type, command)
        
        # Get device from registry
        device = self.registry.get_device(device_type)
        if not device or not device.online:
            raise DeviceOfflineError(f"{device_type} is not available")
        
        try:
            url = f"http://{device.ip}:{device.port}/{command}"
            logger.info(f"Sending command to {device.name}: GET {url}")
            
            response = requests.get(url, timeout=self.timeout)
            response.raise_for_status()
            
            result = response.json()
            
            # Update state cache
            self._update_state_cache(device_type, result)
            
            logger.info(f"Device {device.name} responded: {result}")
            return result
            
        except requests.RequestException as e:
            logger.error(f"Failed to send command to {device_type}: {e}")
            # Mark device as offline in registry
            device.online = False
            raise DeviceOfflineError(f"Communication failed with {device_type}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error communicating with {device_type}: {e}")
            raise DeviceOfflineError(f"Unexpected error with {device_type}: {e}")
    
    def get_device_status(self, device_type: str) -> Dict[str, Any]:
        """
        Get current status of a device.
        
        Args:
            device_type: Type of device
            
        Returns:
            Device status dict
        """
        # Check cache first
        cached_state = self._get_cached_state(device_type)
        if cached_state:
            return cached_state
        
        # Query device for status
        try:
            return self.send_command(device_type, "status")
        except DeviceOfflineError:
            if self.mock:
                return self._mock_response(device_type, "status")
            raise
    
    def get_distance_reading(self, device_type: str = "distance") -> Optional[int]:
        """
        Get distance reading from distance sensor.
        
        Args:
            device_type: Type of distance device
            
        Returns:
            Distance in centimeters, or None if not available
        """
        try:
            response = self.send_command(device_type, "distance")
            return response.get("distance_cm")
        except DeviceOfflineError:
            return None
    
    def send_to_glasses(self, device_type: str, lines: list) -> bool:
        """
        Send display content to another pair of glasses.
        
        Args:
            device_type: Type of glasses device ("glasses")
            lines: List of up to 4 lines to display
            
        Returns:
            True if sent successfully
        """
        if self.mock:
            result = self._mock_response(device_type, "display")
            return result.get("success", True)
        
        device = self.registry.get_device(device_type)
        if not device or not device.online:
            raise DeviceOfflineError(f"{device_type} is not available")
        
        try:
            url = f"http://{device.ip}:{device.port}/display"
            
            # Ensure exactly 4 lines, truncate to reasonable length
            display_lines = []
            for i in range(4):
                if i < len(lines):
                    line = str(lines[i])[:21]  # Match display char limit
                else:
                    line = ""
                display_lines.append(line)
            
            payload = {"lines": display_lines}
            
            logger.info(f"Sending display to {device.name}: {display_lines}")
            
            response = requests.post(
                url, 
                json=payload, 
                timeout=self.timeout,
                headers={'Content-Type': 'application/json'}
            )
            response.raise_for_status()
            
            result = response.json()
            logger.info(f"Display sent to {device.name}: {result}")
            
            return result.get("success", True)
            
        except requests.RequestException as e:
            logger.error(f"Failed to send display to {device_type}: {e}")
            device.online = False
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending display to {device_type}: {e}")
            return False
    
    def _mock_response(self, device_type: str, command: str) -> Dict[str, Any]:
        """Generate mock response for testing."""
        
        if device_type == "light":
            if command == "on":
                return {"status": "on"}
            elif command == "off":
                return {"status": "off"}
            elif command == "status":
                return {"status": "off"}
                
        elif device_type == "fan":
            if command == "on":
                return {"status": "on", "speed": "high"}
            elif command == "off":
                return {"status": "off", "speed": "off"}
            elif command == "low":
                return {"status": "on", "speed": "low"}
            elif command == "high":
                return {"status": "on", "speed": "high"}
            elif command == "status":
                return {"status": "on", "speed": "medium"}
                
        elif device_type == "motion":
            if command == "on":
                return {"alerts": "enabled"}
            elif command == "off":
                return {"alerts": "disabled"}
            elif command == "status":
                return {"alerts": "enabled"}
                
        elif device_type == "distance":
            if command == "distance":
                # Vary mock distance for testing
                import random
                distance = random.randint(20, 150)
                return {"distance_cm": distance}
            elif command == "status":
                return {"device": "iris-distance", "ok": True}
                
        elif device_type == "glasses":
            if command == "display":
                return {"success": True, "message": "Display updated"}
            elif command == "status":
                return {"device": "iris-glasses2", "ok": True}
        
        # Generic response
        return {"device": f"iris-{device_type}", "ok": True}
    
    def _update_state_cache(self, device_type: str, state: Dict[str, Any]) -> None:
        """Update cached state for a device."""
        self._device_states[device_type] = {
            'state': state,
            'timestamp': datetime.now()
        }
    
    def _get_cached_state(self, device_type: str) -> Optional[Dict[str, Any]]:
        """Get cached state if still valid."""
        cached = self._device_states.get(device_type)
        if not cached:
            return None
        
        # Check if cache is still valid
        age = datetime.now() - cached['timestamp']
        if age > self._state_cache_timeout:
            return None
        
        return cached['state']
    
    def clear_cache(self) -> None:
        """Clear device state cache."""
        self._device_states.clear()
        logger.debug("Device state cache cleared")
    
    def get_available_devices(self) -> Dict[str, DiscoveredDevice]:
        """
        Get all available IoT devices from registry.
        
        Returns:
            Dict mapping device types to DiscoveredDevice objects
        """
        devices = {}
        for device in self.registry.get_all_online():
            if device.device_type != "pi":  # Exclude Pi display
                devices[device.device_type] = device
        return devices
    
    def ping_device(self, device_type: str) -> bool:
        """
        Test if a device is responsive.
        
        Args:
            device_type: Type of device to ping
            
        Returns:
            True if device responds to health check
        """
        if self.mock:
            return True  # Mock devices always respond
        
        device = self.registry.get_device(device_type)
        if not device:
            return False
        
        try:
            url = f"http://{device.ip}:{device.port}/health"
            response = requests.get(url, timeout=1.0)  # Quick timeout for ping
            return response.status_code == 200
        except:
            return False
    
    def get_device_info(self, device_type: str) -> Optional[Dict[str, Any]]:
        """
        Get device information and health status.
        
        Args:
            device_type: Type of device
            
        Returns:
            Device info dict or None if not available
        """
        device = self.registry.get_device(device_type)
        if not device:
            return None
        
        info = {
            'name': device.name,
            'type': device.device_type,
            'ip': device.ip,
            'port': device.port,
            'online': device.online,
            'last_seen': device.last_seen.isoformat() if device.last_seen else None,
            'hostname': device.hostname
        }
        
        # Add health check
        if device.online:
            info['responsive'] = self.ping_device(device_type)
        else:
            info['responsive'] = False
        
        return info


if __name__ == "__main__":
    # Test IoT client functionality
    import sys
    import time
    from .discovery import create_registry
    
    logging.basicConfig(level=logging.INFO)
    
    mock_mode = "--mock" in sys.argv
    
    print(f"Testing IoT client ({'mock' if mock_mode else 'live'} mode)...")
    
    # Create registry and IoT client
    registry = create_registry(mock=mock_mode)
    iot = IoTClient(registry=registry, mock=mock_mode)
    
    # Discover devices
    if not mock_mode:
        print("Discovering devices...")
        devices = registry.discover_all(timeout=5.0)
        print(f"Found {len(devices)} devices")
    
    # Test device availability
    print("\n--- Available IoT Devices ---")
    available_devices = iot.get_available_devices()
    
    for device_type, device in available_devices.items():
        status = "✅ Online" if device.online else "❌ Offline"
        print(f"{device.name} ({device_type}): {status}")
        
        # Get device info
        info = iot.get_device_info(device_type)
        if info:
            responsive = "✅ Responsive" if info['responsive'] else "❌ Not responding"
            print(f"  IP: {info['ip']}:{info['port']} - {responsive}")
    
    # Test light commands
    if "light" in available_devices:
        print(f"\n--- Testing Light Commands ---")
        try:
            # Turn on
            result = iot.send_command("light", "on")
            print(f"Light ON: {result}")
            
            time.sleep(1)
            
            # Get status
            status = iot.get_device_status("light")
            print(f"Light status: {status}")
            
            time.sleep(1)
            
            # Turn off
            result = iot.send_command("light", "off")
            print(f"Light OFF: {result}")
            
        except DeviceOfflineError as e:
            print(f"Light test failed: {e}")
    
    # Test fan commands
    if "fan" in available_devices:
        print(f"\n--- Testing Fan Commands ---")
        try:
            result = iot.send_command("fan", "low")
            print(f"Fan LOW: {result}")
            
            time.sleep(1)
            
            result = iot.send_command("fan", "high")
            print(f"Fan HIGH: {result}")
            
        except DeviceOfflineError as e:
            print(f"Fan test failed: {e}")
    
    # Test distance sensor
    if "distance" in available_devices:
        print(f"\n--- Testing Distance Sensor ---")
        for i in range(3):
            try:
                distance = iot.get_distance_reading()
                if distance is not None:
                    print(f"Distance reading {i+1}: {distance} cm")
                else:
                    print(f"Distance reading {i+1}: No data")
                time.sleep(1)
            except DeviceOfflineError as e:
                print(f"Distance sensor test failed: {e}")
                break
    
    # Test glasses communication
    if "glasses" in available_devices:
        print(f"\n--- Testing Glasses Communication ---")
        test_lines = ["Hello from", "Iris Glasses", "Test message", "Line 4"]
        
        try:
            success = iot.send_to_glasses("glasses", test_lines)
            if success:
                print("✅ Message sent to Glasses 2")
            else:
                print("❌ Failed to send message")
        except DeviceOfflineError as e:
            print(f"Glasses test failed: {e}")
    
    print("\nIoT client test complete")