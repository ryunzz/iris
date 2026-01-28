"""
Socket Display Adapter

Drop-in replacement for DisplayManager that uses sockets instead of SSH stdin.
This works better from Windows and doesn't require Terminal 1 (ssh pi).
"""

import socket
import logging
from typing import List

logger = logging.getLogger(__name__)


class SocketDisplayAdapter:
    """
    Adapter that mimics DisplayManager but uses TCP sockets.
    
    Works identically to DisplayManager from the feature's perspective.
    """
    
    def __init__(self, pi_host: str, pi_port: int = 5555):
        """
        Initialize socket display adapter.
        
        Args:
            pi_host: Pi IP address
            pi_port: Port display server is listening on (default 5555)
        """
        self.pi_host = pi_host
        self.pi_port = pi_port
        self.connected = True  # Always "connected" for socket mode
        
        logger.info(f"Initialized socket display adapter for {pi_host}:{pi_port}")
    
    def connect(self) -> bool:
        """
        Test connection to display server.
        
        Returns:
            True if can connect, False otherwise
        """
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            sock.connect((self.pi_host, self.pi_port))
            sock.close()
            logger.info("Display server connection test successful")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to display server: {e}")
            return False
    
    def disconnect(self) -> None:
        """Disconnect (no-op for socket mode)."""
        logger.info("Display adapter disconnected")
    
    def _send_command(self, command: str) -> bool:
        """
        Send command to display server via socket.
        
        Args:
            command: Pipe-delimited string to send
            
        Returns:
            True if sent successfully, False otherwise
        """
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            sock.connect((self.pi_host, self.pi_port))
            sock.send(command.encode('utf-8'))
            sock.close()
            logger.debug(f"Sent command: {command}")
            return True
        except Exception as e:
            logger.error(f"Failed to send command to display: {e}")
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
        
        # Truncate to max 4 lines and 21 chars per line
        processed_lines = []
        for line in lines[:4]:  # Max 4 lines
            if len(line) > 21:
                processed_lines.append(line[:20] + "…")
            else:
                processed_lines.append(line)
        
        # Pad to 4 lines
        while len(processed_lines) < 4:
            processed_lines.append("")
        
        # Join with pipe delimiter
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
        
        # Word wrap to fit 21 chars per line
        words = text.split()
        lines = []
        current_line = ""
        
        for word in words:
            test_line = current_line + (" " if current_line else "") + word
            
            if len(test_line) <= 21:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
                
                if len(lines) >= 4:
                    break
        
        if current_line and len(lines) < 4:
            lines.append(current_line)
        
        return self.show_lines(lines)
    
    def clear(self) -> bool:
        """
        Clear the display.
        
        Returns:
            True if cleared successfully, False otherwise
        """
        return self._send_command("|||")
    
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
    
    # Context manager support (same as DisplayManager)
    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()