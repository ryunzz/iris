#!/usr/bin/env python3
"""
Display manager for Iris Smart Glasses.

Supports multiple display hardware types:
- None: No display output (testing)
- Terminal: ASCII display to stdout  
- Nano: Arduino Nano over serial USB
- ESP32: ESP32 over HTTP (glasses 2 in Texas)
- Pi: Pi Zero W over SSH (glasses 1 main demo)
"""

import time
import threading
import logging
import json
import sys
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Union
from dataclasses import dataclass

try:
    import paramiko
    SSH_AVAILABLE = True
except ImportError:
    SSH_AVAILABLE = False
    logging.warning("paramiko not available - SSH display will not work")

try:
    import serial
    import serial.tools.list_ports
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False
    logging.warning("pyserial not available - Serial display will not work")

try:
    import requests
    HTTP_AVAILABLE = True
except ImportError:
    HTTP_AVAILABLE = False
    logging.warning("requests not available - HTTP display will not work")

try:
    from .discovery import DeviceRegistry, DiscoveredDevice
    DISCOVERY_AVAILABLE = True
except ImportError:
    DeviceRegistry = None
    DiscoveredDevice = None
    DISCOVERY_AVAILABLE = False
    logging.warning("discovery module not available - Pi display will not work")


logger = logging.getLogger(__name__)


@dataclass
class DisplayConfig:
    """Configuration for display manager."""
    width: int = 128
    height: int = 64
    lines: int = 4
    chars_per_line: int = 21
    reconnect_attempts: int = 3
    reconnect_delay: float = 2.0
    ssh_timeout: float = 10.0
    serial_timeout: float = 5.0
    http_timeout: float = 3.0


class DisplayManager(ABC):
    """Abstract base class for display hardware."""
    
    def __init__(self, config: DisplayConfig = None):
        self.config = config or DisplayConfig()
        self.connected = False
        
    @abstractmethod
    def connect(self) -> bool:
        """Connect to display hardware. Returns True if successful."""
        pass
        
    @abstractmethod
    def disconnect(self) -> None:
        """Disconnect from display hardware."""
        pass
        
    @abstractmethod
    def send_lines(self, lines: List[str]) -> bool:
        """Send 4 lines of text to display. Returns True if successful."""
        pass
        
    @abstractmethod
    def clear(self) -> bool:
        """Clear the display. Returns True if successful."""
        pass
        
    @abstractmethod
    def is_connected(self) -> bool:
        """Check if display is connected and ready."""
        pass

    def _format_lines(self, lines: List[str]) -> List[str]:
        """Format lines to fit display constraints (4 lines, 21 chars each)."""
        formatted = []
        for i in range(4):
            if i < len(lines) and lines[i] is not None:
                line = str(lines[i])[:self.config.chars_per_line]
                formatted.append(line)
            else:
                formatted.append("")
        return formatted


class NoneDisplay(DisplayManager):
    """No display output - for testing without hardware."""
    
    def connect(self) -> bool:
        self.connected = True
        logger.info("Display: None (no output)")
        return True
        
    def disconnect(self) -> None:
        self.connected = False
        
    def send_lines(self, lines: List[str]) -> bool:
        # Silently ignore all display updates
        return True
        
    def clear(self) -> bool:
        return True
        
    def is_connected(self) -> bool:
        return self.connected


class TerminalDisplay(DisplayManager):
    """ASCII display to terminal stdout."""
    
    def __init__(self, config: DisplayConfig = None):
        super().__init__(config)
        self.last_lines = []
        
    def connect(self) -> bool:
        self.connected = True
        logger.info("Display: Terminal ASCII")
        return True
        
    def disconnect(self) -> None:
        self.connected = False
        
    def send_lines(self, lines: List[str]) -> bool:
        if not self.connected:
            return False
            
        formatted = self._format_lines(lines)
        
        # Only update if lines changed (reduce flicker)
        if formatted != self.last_lines:
            self._print_display(formatted)
            self.last_lines = formatted
            
        return True
        
    def clear(self) -> bool:
        if not self.connected:
            return False
            
        self.send_lines(["", "", "", ""])
        return True
        
    def is_connected(self) -> bool:
        return self.connected
        
    def _print_display(self, lines: List[str]):
        """Print ASCII representation of OLED display."""
        print("\n" + "─" * (self.config.chars_per_line + 2))
        for line in lines:
            padded = line.ljust(self.config.chars_per_line)
            print(f"│{padded}│")
        print("─" * (self.config.chars_per_line + 2))


class NanoDisplay(DisplayManager):
    """Arduino Nano display over serial USB."""
    
    def __init__(self, config: DisplayConfig = None, port: str = None):
        super().__init__(config)
        self.port = port
        self.serial_conn = None
        
    def connect(self) -> bool:
        if not SERIAL_AVAILABLE:
            logger.error("pyserial not available for Nano display")
            return False
            
        if self.port is None:
            self.port = self._auto_detect_port()
            
        if self.port is None:
            logger.error("No Arduino Nano found on any serial port")
            return False
            
        try:
            self.serial_conn = serial.Serial(
                self.port, 
                baudrate=9600,
                timeout=self.config.serial_timeout
            )
            time.sleep(2)  # Arduino reset delay
            self.connected = True
            logger.info(f"Display: Arduino Nano on {self.port}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to Nano on {self.port}: {e}")
            return False
            
    def disconnect(self) -> None:
        if self.serial_conn:
            self.serial_conn.close()
            self.serial_conn = None
        self.connected = False
        
    def send_lines(self, lines: List[str]) -> bool:
        if not self.connected or not self.serial_conn:
            return False
            
        try:
            formatted = self._format_lines(lines)
            # Send as pipe-delimited string like Pi
            message = "|".join(formatted) + "\n"
            self.serial_conn.write(message.encode('utf-8'))
            self.serial_conn.flush()
            return True
            
        except Exception as e:
            logger.error(f"Failed to send to Nano: {e}")
            self.connected = False
            return False
            
    def clear(self) -> bool:
        return self.send_lines(["", "", "", ""])
        
    def is_connected(self) -> bool:
        return self.connected and self.serial_conn and self.serial_conn.is_open
        
    def _auto_detect_port(self) -> Optional[str]:
        """Auto-detect Arduino Nano port."""
        ports = serial.tools.list_ports.comports()
        
        # Look for common Arduino identifiers
        arduino_vendors = ['Arduino', 'FTDI', 'Prolific', '1a86', '0403', '10c4']
        
        for port in ports:
            if any(vendor.lower() in str(port).lower() for vendor in arduino_vendors):
                return port.device
                
        # If no Arduino found, try the first available port
        if ports:
            logger.warning(f"No Arduino found, trying first port: {ports[0].device}")
            return ports[0].device
            
        return None


class ESP32Display(DisplayManager):
    """ESP32 display over HTTP (glasses 2 in Texas)."""
    
    def __init__(self, config: DisplayConfig = None, ip: str = None):
        super().__init__(config)
        self.ip = ip
        self.session = None
        
    def connect(self) -> bool:
        if not HTTP_AVAILABLE:
            logger.error("requests not available for ESP32 display")
            return False
            
        if self.ip is None:
            logger.error("ESP32 IP address is required")
            return False
            
        try:
            import requests
            self.session = requests.Session()
            self.session.timeout = self.config.http_timeout
            
            # Test connection
            response = self.session.get(f"http://{self.ip}/status", timeout=self.config.http_timeout)
            if response.status_code == 200:
                self.connected = True
                logger.info(f"Display: ESP32 at {self.ip}")
                return True
            else:
                logger.error(f"ESP32 at {self.ip} responded with status {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to connect to ESP32 at {self.ip}: {e}")
            return False
            
    def disconnect(self) -> None:
        if self.session:
            self.session.close()
            self.session = None
        self.connected = False
        
    def send_lines(self, lines: List[str]) -> bool:
        if not self.connected or not self.session:
            return False
            
        try:
            formatted = self._format_lines(lines)
            payload = {"lines": formatted}
            
            response = self.session.post(
                f"http://{self.ip}/display",
                json=payload,
                timeout=self.config.http_timeout
            )
            
            if response.status_code == 200:
                return True
            else:
                logger.error(f"ESP32 display update failed: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to send to ESP32: {e}")
            self.connected = False
            return False
            
    def clear(self) -> bool:
        return self.send_lines(["", "", "", ""])
        
    def is_connected(self) -> bool:
        return self.connected and self.session is not None


class PiDisplay(DisplayManager):
    """Pi Zero W display over SSH (glasses 1 main demo)."""
    
    def __init__(self, config: DisplayConfig = None, registry = None):
        super().__init__(config)
        self.registry = registry
        self.ssh_client = None
        self.ssh_channel = None
        self.pi_device = None
        
    def connect(self) -> bool:
        if not SSH_AVAILABLE:
            logger.error("paramiko not available for Pi display")
            return False
            
        if not self.registry:
            logger.error("Device registry required for Pi display")
            return False
            
        # Find Pi device
        self.pi_device = self.registry.get_device("pi")
        if not self.pi_device:
            logger.error("Pi device not found in registry")
            return False
            
        # Connect via SSH
        for attempt in range(self.config.reconnect_attempts):
            try:
                self.ssh_client = paramiko.SSHClient()
                self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                
                self.ssh_client.connect(
                    hostname=self.pi_device.ip,
                    port=22,
                    username='pi',
                    timeout=self.config.ssh_timeout,
                    banner_timeout=30
                )
                
                # Create persistent channel
                self.ssh_channel = self.ssh_client.invoke_shell()
                self.ssh_channel.settimeout(self.config.ssh_timeout)
                
                # Start display server
                self.ssh_channel.send("python3 ~/iris/pi/display_server.py\n")
                time.sleep(1)
                
                self.connected = True
                logger.info(f"Display: Pi Zero W at {self.pi_device.ip}")
                return True
                
            except Exception as e:
                logger.warning(f"SSH attempt {attempt + 1} failed: {e}")
                if attempt < self.config.reconnect_attempts - 1:
                    time.sleep(self.config.reconnect_delay)
                    
        logger.error("Failed to connect to Pi via SSH")
        return False
        
    def disconnect(self) -> None:
        if self.ssh_channel:
            try:
                self.ssh_channel.close()
            except:
                pass
            self.ssh_channel = None
            
        if self.ssh_client:
            try:
                self.ssh_client.close()
            except:
                pass
            self.ssh_client = None
            
        self.connected = False
        
    def send_lines(self, lines: List[str]) -> bool:
        if not self.connected or not self.ssh_channel:
            return False
            
        try:
            formatted = self._format_lines(lines)
            # Send as pipe-delimited string to Pi display server
            message = "|".join(formatted) + "\n"
            self.ssh_channel.send(message)
            return True
            
        except Exception as e:
            logger.error(f"Failed to send to Pi: {e}")
            self.connected = False
            return False
            
    def clear(self) -> bool:
        return self.send_lines(["", "", "", ""])
        
    def is_connected(self) -> bool:
        return self.connected and self.ssh_channel is not None


def create_display_manager(display_type: str, config: DisplayConfig = None, 
                          registry = None, **kwargs) -> DisplayManager:
    """Factory function to create display managers."""
    
    if display_type == "none":
        return NoneDisplay(config)
        
    elif display_type == "terminal":
        return TerminalDisplay(config)
        
    elif display_type == "nano":
        return NanoDisplay(config, port=kwargs.get('serial_port'))
        
    elif display_type == "esp32":
        return ESP32Display(config, ip=kwargs.get('display_ip'))
        
    elif display_type == "pi":
        return PiDisplay(config, registry=registry)
        
    else:
        raise ValueError(f"Unknown display type: {display_type}")


class Display:
    """
    High-level display interface that wraps display managers.
    Maintains compatibility with existing code.
    """
    
    def __init__(self, display_type: str = None, registry = None, 
                 mock: bool = False, config: DisplayConfig = None, **kwargs):
        self.config = config or DisplayConfig()
        
        # Determine display type
        if display_type is None:
            display_type = "terminal" if mock else "pi"
            
        # Create display manager
        self.manager = create_display_manager(
            display_type, self.config, registry, **kwargs
        )
        
        # Connect
        self.connected = self.manager.connect()
        if not self.connected:
            logger.warning(f"Failed to connect {display_type} display")
    
    def disconnect(self) -> None:
        """Disconnect from display."""
        if self.manager:
            self.manager.disconnect()
    
    def clear(self) -> None:
        """Clear the display."""
        if self.manager:
            self.manager.clear()
    
    def show_text(self, text: str, center: bool = False) -> None:
        """Show simple text message."""
        lines = text.split('\n')
        if center:
            lines = [line.center(self.config.chars_per_line) for line in lines]
        self.manager.send_lines(lines)
    
    def show_idle(self, weather: Dict[str, Any]) -> None:
        """Show idle screen with weather and time."""
        now = datetime.now()
        temp = weather.get('temperature', 'N/A')
        desc = weather.get('description', '')
        
        lines = [
            now.strftime("%H:%M"),
            f"{temp}°C",
            desc[:21],
            now.strftime("%m/%d")
        ]
        self.manager.send_lines(lines)
    
    def show_main_menu(self) -> None:
        """Show main menu."""
        lines = [
            "MAIN MENU",
            "> 1. Todo List",
            "  2. Translation", 
            "  3. Connect"
        ]
        self.manager.send_lines(lines)
    
    def show_todo_menu(self) -> None:
        """Show todo menu."""
        lines = [
            "TODO MENU",
            "> 1. View List",
            "  2. Add Item",
            "  3. View Instructions"
        ]
        self.manager.send_lines(lines)
    
    def show_todo_instructions(self) -> None:
        """Show todo usage instructions."""
        lines = [
            "TODO INSTRUCTIONS",
            "Say 'up/down' to nav",
            "Say 'cross' to mark",
            "Say 'back' to return"
        ]
        self.manager.send_lines(lines)
    
    def show_todo_list(self, todos: List[Dict], cursor: int = 0) -> None:
        """Show todo list."""
        lines = ["TODO LIST"]
        
        for i, todo in enumerate(todos[:3]):
            marker = "●" if i == cursor else "○"
            status = "✓" if todo.get('done', False) else " "
            text = todo.get('text', '')[:17]
            lines.append(f"{marker}{status} {text}")
            
        # Pad to 4 lines
        while len(lines) < 4:
            lines.append("")
            
        self.manager.send_lines(lines)
    
    def show_todo_add(self, text: str) -> None:
        """Show todo add screen."""
        lines = [
            "ADD TODO",
            "",
            text[:21],
            "Say 'confirm'"
        ]
        self.manager.send_lines(lines)
    
    def show_device_list(self, devices: List[Dict], cursor: int = 0) -> None:
        """Show device list with numbered options."""
        lines = ["DEVICES"]
        
        for i, device in enumerate(devices[:3]):
            marker = "●" if i == cursor else "○"
            number = i + 1  # 1-based numbering
            name = device.get('name', '')[:14]  # Truncate to fit with number
            lines.append(f"{marker} {number}. {name}")
            
        while len(lines) < 4:
            lines.append("")
            
        self.manager.send_lines(lines)
    
    def show_connected_light(self, status: str) -> None:
        """Show connected light screen."""
        lines = [
            "SMART LIGHT",
            "",
            f"Status: {status}",
            "on/off/back"
        ]
        self.manager.send_lines(lines)
    
    def show_connected_fan(self, status: str, speed: str = "") -> None:
        """Show connected fan screen."""
        lines = [
            "SMART FAN", 
            "",
            f"Status: {status}",
            f"Speed: {speed}" if speed else "on/off/low/high"
        ]
        self.manager.send_lines(lines)
    
    def show_connected_motion(self, alerts_enabled: bool) -> None:
        """Show connected motion sensor screen."""
        status = "ENABLED" if alerts_enabled else "DISABLED"
        lines = [
            "MOTION SENSOR",
            "",
            f"Alerts: {status}",
            "on/off/back"
        ]
        self.manager.send_lines(lines)
    
    def show_connected_distance(self, distance_cm: float) -> None:
        """Show connected distance sensor screen."""
        lines = [
            "DISTANCE SENSOR",
            "",
            f"{distance_cm:.1f} cm",
            "back"
        ]
        self.manager.send_lines(lines)
    
    def show_connected_glasses(self) -> None:
        """Show connected glasses screen."""
        lines = [
            "GLASSES 2",
            "",
            "Connected",
            "Say message"
        ]
        self.manager.send_lines(lines)
    
    def show_connection_error(self, device: str) -> None:
        """Show connection error."""
        lines = [
            "ERROR",
            "",
            f"{device} offline",
            "back"
        ]
        self.manager.send_lines(lines)
    
    def show_translation(self, original: str, translated: str) -> None:
        """Show translation screen."""
        lines = [
            "TRANSLATION",
            original[:21],
            "→",
            translated[:21]
        ]
        self.manager.send_lines(lines)
    
    def show_motion_interrupt(self, duration: float = 2.0) -> None:
        """Show motion interrupt notification."""
        lines = [
            "MOTION DETECTED",
            "",
            "●●●●●●●●●●●●●",
            ""
        ]
        self.manager.send_lines(lines)
        
        # Return to previous screen after duration
        def restore():
            time.sleep(duration)
            # Would need access to current state to restore properly
            
        threading.Thread(target=restore, daemon=True).start()