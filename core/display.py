"""
Iris Smart Glasses - Display Manager

This module runs on the laptop and sends text to the Pi Zero W over SSH.
The Pi displays the text on the OLED screen.
"""

import subprocess
import logging
from typing import List, Optional
import time

logger = logging.getLogger(__name__)

# Display constants - must match Pi display server
MAX_LINES = 4
CHARS_PER_LINE = 21


class DisplayManager:
    """Manages text display on Pi Zero W via SSH."""
    
    def __init__(self, pi_host: str, pi_user: str = "pi", display_server_path: str = "/home/pi/iris/pi/display_server.py"):
        """
        Initialize display manager.
        
        Args:
            pi_host: Pi hostname or IP address
            pi_user: Pi username (default: "pi")
            display_server_path: Path to display_server.py on Pi
        """
        self.pi_host = pi_host
        self.pi_user = pi_user
        self.display_server_path = display_server_path
        self.ssh_process: Optional[subprocess.Popen] = None
        self.connected = False
        
        logger.info(f"Initialized display manager for {pi_user}@{pi_host}")
    
    def connect(self) -> bool:
        """
        Open SSH connection to Pi and start display server.
        
        Returns:
            True if connected successfully, False otherwise
        """
        if self.connected:
            logger.warning("Already connected to display")
            return True
        
        try:
            # SSH command to run display server on Pi
            ssh_cmd = [
                "ssh",
                f"{self.pi_user}@{self.pi_host}",
                f"cd ~/iris && source venv/bin/activate && python {self.display_server_path}"
            ]
            
            logger.info(f"Connecting to display server at {self.pi_host}...")
            
            # Start SSH process with pipes for communication
            self.ssh_process = subprocess.Popen(
                ssh_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1  # Line buffered
            )
            
            # Give the display server time to initialize
            time.sleep(2)
            
            # Check if process is still running
            if self.ssh_process.poll() is not None:
                # Process has terminated
                stdout, stderr = self.ssh_process.communicate()
                logger.error(f"SSH process terminated: {stderr}")
                return False
            
            self.connected = True
            logger.info("Successfully connected to display server")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to display: {e}")
            self.connected = False
            return False
    
    def disconnect(self) -> None:
        """Close SSH connection to Pi."""
        if not self.connected or not self.ssh_process:
            return
        
        try:
            logger.info("Disconnecting from display server...")
            
            # Send clear command before disconnecting
            self.clear()
            
            # Terminate SSH process
            self.ssh_process.terminate()
            
            # Wait for process to terminate gracefully
            try:
                self.ssh_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger.warning("SSH process didn't terminate gracefully, killing...")
                self.ssh_process.kill()
            
            self.ssh_process = None
            self.connected = False
            logger.info("Disconnected from display server")
            
        except Exception as e:
            logger.error(f"Error disconnecting from display: {e}")
    
    def _send_command(self, command: str) -> bool:
        """
        Send a command to the display server.
        
        Args:
            command: Command string to send
            
        Returns:
            True if sent successfully, False otherwise
        """
        if not self.connected or not self.ssh_process:
            logger.error("Not connected to display server")
            return False
        
        try:
            # Check if process is still alive
            if self.ssh_process.poll() is not None:
                logger.error("Display server process has terminated")
                self.connected = False
                return False
            
            # Send command
            self.ssh_process.stdin.write(command + "\n")
            self.ssh_process.stdin.flush()
            
            logger.debug(f"Sent command: {command}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send command to display: {e}")
            self.connected = False
            return False
    
    def show_lines(self, lines: List[str]) -> bool:
        """
        Display lines of text on the OLED.
        
        Args:
            lines: List of strings to display (max 4 lines, 21 chars each)
            
        Returns:
            True if displayed successfully, False otherwise
        """
        if not lines:
            return self.clear()
        
        # Truncate to max lines and chars per line
        processed_lines = []
        for line in lines[:MAX_LINES]:
            if len(line) > CHARS_PER_LINE:
                processed_lines.append(line[:CHARS_PER_LINE-1] + "…")
            else:
                processed_lines.append(line)
        
        # Join lines with pipe delimiter
        command = "|".join(processed_lines)
        
        return self._send_command(command)
    
    def show_text(self, text: str) -> bool:
        """
        Display text on the OLED, automatically wrapping lines.
        
        Args:
            text: Text to display
            
        Returns:
            True if displayed successfully, False otherwise
        """
        if not text.strip():
            return self.clear()
        
        # Split text into words and wrap to fit display
        words = text.split()
        lines = []
        current_line = ""
        
        for word in words:
            # Check if adding this word would exceed line length
            test_line = current_line + (" " if current_line else "") + word
            
            if len(test_line) <= CHARS_PER_LINE:
                current_line = test_line
            else:
                # Start new line
                if current_line:
                    lines.append(current_line)
                current_line = word
                
                # Stop if we've reached max lines
                if len(lines) >= MAX_LINES:
                    break
        
        # Add final line if there's content and room
        if current_line and len(lines) < MAX_LINES:
            lines.append(current_line)
        
        return self.show_lines(lines)
    
    def clear(self) -> bool:
        """
        Clear the display.
        
        Returns:
            True if cleared successfully, False otherwise
        """
        return self._send_command("")
    
    def show_idle_screen(self) -> bool:
        """
        Show the idle/ready screen.
        
        Returns:
            True if displayed successfully, False otherwise
        """
        return self.show_lines([
            "Iris Smart Glasses",
            "",
            "Ready for commands",
            "Say 'Hey Iris...'"
        ])
    
    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()