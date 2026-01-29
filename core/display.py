#!/usr/bin/env python3
"""
Display manager for Iris Smart Glasses.

Handles OLED display updates via persistent SSH connection to Pi Zero W.
Supports mock mode with terminal ASCII display for testing.
"""

import time
import threading
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

try:
    import paramiko
    SSH_AVAILABLE = True
except ImportError:
    SSH_AVAILABLE = False
    logging.warning("paramiko not available - SSH display will not work")

from .discovery import DeviceRegistry, DiscoveredDevice


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


class Display:
    """
    Display manager with persistent SSH connection to Pi Zero W.
    Maintains single SSH connection for low-latency updates.
    """
    
    def __init__(self, registry: DeviceRegistry, mock: bool = False, config: DisplayConfig = None):
        self.registry = registry
        self.mock = mock
        self.config = config or DisplayConfig()
        
        # SSH connection state
        self.ssh_client: Optional[paramiko.SSHClient] = None
        self.ssh_channel = None
        self.connected = False
        self.connection_lock = threading.Lock()
        
        # Display state
        self.current_lines = ["", "", "", ""]
        self.motion_interrupt_until: Optional[datetime] = None
        
        if not self.mock and not SSH_AVAILABLE:
            logger.error("SSH display requested but paramiko not available")
            raise RuntimeError("paramiko required for SSH display - install with: pip install paramiko")
        
        # Initialize connection if not in mock mode
        if not self.mock:
            self._connect()
    
    def _connect(self) -> bool:
        """
        Establish persistent SSH connection to Pi Zero W.
        
        Returns:
            True if connection successful, False otherwise
        """
        with self.connection_lock:
            if self.connected and self.ssh_channel and not self.ssh_channel.closed:
                return True
            
            # Get Pi device from discovery
            pi = self.registry.get_device("pi")
            if not pi or not pi.online:
                logger.error("Pi not found or offline - cannot connect display")
                return False
            
            try:
                # Create SSH client
                if self.ssh_client:
                    try:
                        self.ssh_client.close()
                    except:
                        pass
                
                self.ssh_client = paramiko.SSHClient()
                self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                
                # Try to connect with SSH key first, then password
                connection_methods = [
                    {'key_filename': '~/.ssh/iris_pi_key'},
                    {'key_filename': '~/.ssh/id_rsa'},  
                    {'password': 'raspberry'},  # Default Pi password
                ]
                
                connected = False
                for method in connection_methods:
                    try:
                        logger.debug(f"Trying SSH connection to {pi.ip} with {method}")
                        self.ssh_client.connect(
                            pi.ip,
                            username='pi',
                            timeout=self.config.ssh_timeout,
                            **method
                        )
                        connected = True
                        break
                    except paramiko.AuthenticationException:
                        continue
                    except Exception as e:
                        logger.debug(f"SSH connection method failed: {e}")
                        continue
                
                if not connected:
                    logger.error(f"Could not authenticate SSH connection to Pi at {pi.ip}")
                    return False
                
                # Open persistent channel and start display server
                self.ssh_channel = self.ssh_client.invoke_shell()
                
                # Start the display server on Pi
                self.ssh_channel.send('cd ~/iris && python3 pi/display_server.py\n')
                
                # Wait a moment for server to start
                time.sleep(1.0)
                
                # Test the connection by sending a test message
                test_lines = ["Iris Glasses", "Display Ready", "", ""]
                self._send_lines(test_lines)
                
                self.connected = True
                logger.info(f"✅ SSH display connected to Pi at {pi.ip}")
                return True
                
            except Exception as e:
                logger.error(f"Failed to connect SSH display: {e}")
                if self.ssh_client:
                    try:
                        self.ssh_client.close()
                    except:
                        pass
                self.ssh_client = None
                self.ssh_channel = None
                return False
    
    def _reconnect(self) -> bool:
        """
        Attempt to reconnect if connection is lost.
        
        Returns:
            True if reconnection successful
        """
        logger.info("Attempting to reconnect SSH display...")
        
        for attempt in range(self.config.reconnect_attempts):
            if attempt > 0:
                time.sleep(self.config.reconnect_delay)
                
            if self._connect():
                logger.info(f"SSH display reconnected successfully (attempt {attempt + 1})")
                return True
        
        logger.error(f"Failed to reconnect SSH display after {self.config.reconnect_attempts} attempts")
        return False
    
    def _send_lines(self, lines: List[str]) -> bool:
        """
        Send lines to Pi display via SSH channel.
        
        Args:
            lines: List of up to 4 lines to display
            
        Returns:
            True if successful, False if failed
        """
        if self.mock:
            self._mock_display(lines)
            return True
        
        if not self.ssh_channel or self.ssh_channel.closed:
            if not self._reconnect():
                return False
        
        try:
            # Ensure we have exactly 4 lines, truncate to character limit
            display_lines = []
            for i in range(4):
                if i < len(lines):
                    line = lines[i][:self.config.chars_per_line]
                else:
                    line = ""
                display_lines.append(line)
            
            # Send as pipe-delimited format
            payload = '|'.join(display_lines) + '\n'
            self.ssh_channel.send(payload.encode())
            
            return True
            
        except Exception as e:
            logger.warning(f"Failed to send display update: {e}")
            self.connected = False
            return False
    
    def _mock_display(self, lines: List[str]) -> None:
        """
        Show ASCII mock display in terminal.
        
        Args:
            lines: List of lines to display
        """
        print("\n┌" + "─" * self.config.chars_per_line + "┐")
        for i in range(self.config.lines):
            line = lines[i] if i < len(lines) else ""
            padded_line = f"{line:<{self.config.chars_per_line}}"
            print(f"│{padded_line}│")
        print("└" + "─" * self.config.chars_per_line + "┘")
    
    def update(self, lines: List[str]) -> bool:
        """
        Update display with new content.
        
        Args:
            lines: List of up to 4 lines to display
            
        Returns:
            True if update successful
        """
        # Check for motion interrupt overlay
        if self._is_motion_interrupt_active():
            return True  # Don't update during motion interrupt
        
        self.current_lines = lines.copy()
        return self._send_lines(lines)
    
    def clear(self) -> bool:
        """Clear the display."""
        return self.update(["", "", "", ""])
    
    def show_idle(self, weather_data: Dict[str, Any]) -> bool:
        """
        Show IDLE screen with weather and time.
        
        Args:
            weather_data: Dict with 'temp', 'condition', 'time' keys
        """
        lines = [
            f"{weather_data.get('temp', '??')}F  {weather_data.get('condition', 'Unknown')}",
            "College Station TX",
            f"     {weather_data.get('time', '??:??')}",
            ""
        ]
        return self.update(lines)
    
    def show_main_menu(self) -> bool:
        """Show main menu screen."""
        lines = [
            "  1. Todo",
            "  2. Translation", 
            "  3. Connect",
            ""
        ]
        return self.update(lines)
    
    def show_todo_list(self, todos: List[Dict[str, Any]], cursor: int = 0) -> bool:
        """
        Show todo list with cursor.
        
        Args:
            todos: List of todo dicts with 'text' and 'done' keys
            cursor: Index of currently selected item
        """
        lines = ["Todo List"]
        
        # Show up to 3 todos starting from appropriate position
        visible_todos = todos[max(0, cursor-2):cursor+1] if todos else []
        
        for i, todo in enumerate(visible_todos[-3:]):  # Last 3 items
            actual_index = len(visible_todos) - 3 + i
            is_current = actual_index == len(visible_todos) - 1  # Last item is current
            
            prefix = "> " if is_current else "  "
            status = "x" if todo.get('done', False) else "o"
            text = todo.get('text', '')[:16]  # Truncate for display
            
            lines.append(f"{prefix}{status} {text}")
        
        # Fill remaining lines
        while len(lines) < 4:
            lines.append("")
        
        return self.update(lines)
    
    def show_todo_add(self, captured_text: str = "") -> bool:
        """
        Show todo add screen.
        
        Args:
            captured_text: Text captured from voice input
        """
        if captured_text:
            # Show captured text and confirmation options
            lines = [
                "Add Todo",
                "",
                f'"{captured_text[:17]}"',  # Truncate to fit
                "confirm / cancel"
            ]
        else:
            # Show listening prompt
            lines = [
                "Add Todo", 
                "",
                "Say your item...",
                ""
            ]
        
        return self.update(lines)
    
    def show_translation(self, original: str = "", translated: str = "") -> bool:
        """
        Show translation screen with original and translated text.
        
        Args:
            original: Original text
            translated: Translated text
        """
        lines = []
        
        # Format original text (up to 2 lines)
        if original:
            orig_words = original.split()
            orig_line1 = ""
            orig_line2 = ""
            
            for word in orig_words:
                if len(orig_line1 + " " + word) <= self.config.chars_per_line:
                    orig_line1 += (" " + word) if orig_line1 else word
                elif len(orig_line2 + " " + word) <= self.config.chars_per_line:
                    orig_line2 += (" " + word) if orig_line2 else word
                else:
                    break
            
            lines.extend([f'"{orig_line1}"', f' {orig_line2}"' if orig_line2 else ""])
        else:
            lines.extend(["", ""])
        
        # Add separator
        if original or translated:
            lines.append("-" * 16)
        else:
            lines.append("")
        
        # Format translated text (1 line)
        if translated:
            trans_text = translated[:self.config.chars_per_line]
            lines.append(f'"{trans_text}"')
        else:
            lines.append("")
        
        # Ensure exactly 4 lines
        lines = (lines + ["", "", "", ""])[:4]
        
        return self.update(lines)
    
    def show_device_list(self, devices: List[Dict[str, str]], cursor: int = 0) -> bool:
        """
        Show device list with cursor.
        
        Args:
            devices: List of device dicts with 'name' and 'status' keys
            cursor: Index of currently selected device
        """
        lines = ["Devices:"]
        
        # Show up to 3 devices starting from cursor position
        visible_devices = devices[cursor:cursor+3] if devices else []
        
        for i, device in enumerate(visible_devices):
            is_current = (i == 0)  # First item is current
            prefix = "> " if is_current else "  "
            name = device.get('name', 'Unknown')[:17]  # Truncate to fit
            
            # Show offline devices dimmed/grayed (just use different formatting)
            if device.get('status') == 'Offline':
                name = f"[{name}]"  # Brackets to indicate offline
            
            lines.append(f"{prefix}{name}")
        
        # Fill remaining lines
        while len(lines) < 4:
            lines.append("")
        
        return self.update(lines)
    
    def show_connected_light(self, status: str = "UNKNOWN") -> bool:
        """Show connected light control screen."""
        lines = [
            "Smart Light",
            f"Status: {status}",
            "",
            "Say: on / off"
        ]
        return self.update(lines)
    
    def show_connected_fan(self, status: str = "UNKNOWN", speed: str = "") -> bool:
        """Show connected fan control screen."""
        status_line = f"Status: {status}"
        if speed and status.upper() == "ON":
            status_line += f" - {speed}"
            
        lines = [
            "Smart Fan",
            status_line,
            "",
            "on/off/low/high"
        ]
        return self.update(lines)
    
    def show_connected_motion(self, alerts_enabled: bool = False) -> bool:
        """Show connected motion sensor screen."""
        status = "ON" if alerts_enabled else "OFF"
        alert_status = "Alerts enabled" if alerts_enabled else "Alerts disabled"
        
        lines = [
            "Motion Sensor",
            f"Status: {status}",
            alert_status,
            "Say: on / off"
        ]
        return self.update(lines)
    
    def show_connected_distance(self, distance_cm: Optional[int] = None) -> bool:
        """Show connected distance sensor screen."""
        if distance_cm is None:
            distance_line = "No reading"
            status_line = ""
        else:
            distance_line = f"   {distance_cm} cm"
            
            # Determine status based on distance
            if distance_cm > 100:
                status_line = "Safe"
            elif distance_cm >= 30:
                status_line = "Getting close"
            else:
                status_line = "STOP"
        
        lines = [
            "Distance",
            "",
            distance_line,
            status_line
        ]
        return self.update(lines)
    
    def show_connected_glasses(self) -> bool:
        """Show connected glasses screen."""
        lines = [
            "Glasses 2",
            "Connected",
            "",
            "Say: send [msg]"
        ]
        return self.update(lines)
    
    def show_motion_interrupt(self, duration: float = 2.0) -> bool:
        """
        Show motion detection overlay for specified duration.
        
        Args:
            duration: How long to show the overlay in seconds
        """
        # Set interrupt end time
        self.motion_interrupt_until = datetime.now() + timedelta(seconds=duration)
        
        # Show motion alert
        lines = [
            "",
            "MOTION DETECTED",
            "",
            ""
        ]
        return self._send_lines(lines)
    
    def _is_motion_interrupt_active(self) -> bool:
        """Check if motion interrupt overlay is currently active."""
        if not self.motion_interrupt_until:
            return False
        
        if datetime.now() >= self.motion_interrupt_until:
            # Interrupt expired, restore previous display
            self.motion_interrupt_until = None
            self._send_lines(self.current_lines)
            return False
        
        return True
    
    def show_connection_error(self, device_name: str = "Device") -> bool:
        """Show connection error overlay."""
        lines = [
            "",
            f"{device_name} offline",
            "Reconnecting...",
            ""
        ]
        return self.update(lines)
    
    def show_text(self, text: str, center: bool = False) -> bool:
        """
        Show arbitrary text on display.
        
        Args:
            text: Text to display
            center: Whether to center the text
        """
        words = text.split()
        lines = [""]
        current_line = 0
        
        for word in words:
            if len(lines[current_line] + " " + word) <= self.config.chars_per_line:
                lines[current_line] += (" " + word) if lines[current_line] else word
            else:
                if current_line < 3:
                    current_line += 1
                    lines.append(word)
                else:
                    break
        
        # Center text if requested
        if center:
            centered_lines = []
            for line in lines:
                padding = (self.config.chars_per_line - len(line)) // 2
                centered_lines.append(" " * padding + line)
            lines = centered_lines
        
        # Ensure exactly 4 lines
        lines = (lines + ["", "", "", ""])[:4]
        
        return self.update(lines)
    
    def disconnect(self) -> None:
        """Clean up SSH connection."""
        with self.connection_lock:
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
        
        logger.info("Display disconnected")
    
    def get_connection_status(self) -> Dict[str, Any]:
        """Get current connection status for debugging."""
        return {
            'connected': self.connected,
            'mock_mode': self.mock,
            'ssh_available': SSH_AVAILABLE,
            'channel_open': self.ssh_channel is not None and not self.ssh_channel.closed if self.ssh_channel else False,
            'pi_online': self.registry.is_device_online("pi")
        }


if __name__ == "__main__":
    # Test display functionality
    import sys
    import time
    from .discovery import create_registry
    
    mock_mode = "--mock" in sys.argv
    
    logging.basicConfig(level=logging.INFO)
    
    # Create registry and display
    registry = create_registry(mock=mock_mode)
    display = Display(registry=registry, mock=mock_mode)
    
    print("Testing display screens...")
    
    # Test various screens
    screens = [
        ("IDLE", lambda: display.show_idle({'temp': 75, 'condition': 'Sunny', 'time': '2:30 PM'})),
        ("Main Menu", display.show_main_menu),
        ("Todo List", lambda: display.show_todo_list([
            {'text': 'Buy groceries', 'done': False},
            {'text': 'Call mom', 'done': True},
            {'text': 'Fix bug', 'done': False}
        ], cursor=0)),
        ("Todo Add", lambda: display.show_todo_add("Buy milk")),
        ("Translation", lambda: display.show_translation("Hello there", "Bonjour là")),
        ("Device List", lambda: display.show_device_list([
            {'name': 'Smart Light', 'status': 'Online'},
            {'name': 'Smart Fan', 'status': 'Offline'},
            {'name': 'Motion Sensor', 'status': 'Online'}
        ], cursor=0)),
        ("Connected Light", lambda: display.show_connected_light("ON")),
        ("Connected Fan", lambda: display.show_connected_fan("ON", "HIGH")),
        ("Distance", lambda: display.show_connected_distance(45)),
    ]
    
    for name, screen_func in screens:
        print(f"\n--- {name} ---")
        screen_func()
        time.sleep(2)
    
    # Test motion interrupt
    print("\n--- Motion Interrupt ---")
    display.show_motion_interrupt(1.0)
    time.sleep(2)
    
    print("\nDisplay test complete")
    display.disconnect()