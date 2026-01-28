#!/usr/bin/env python3
#NOTE: for displays to work, run iris/pi/display_server.py on the pi0W SSH first!
"""
Iris Smart Glasses - Display Server (Socket Version)

This is a DUMB terminal that runs on the Pi Zero W.
It listens on TCP port 5555 and displays text on the OLED.
NO LOGIC, NO DECISIONS, NO PROCESSING - just text in, display out.

Input format: "Line 1|Line 2|Line 3|Line 4"
"""

import socket
import logging
from typing import List
from luma.core.interface.serial import i2c
from luma.core.render import canvas
from luma.oled.device import ssd1306
from PIL import ImageFont

# Display constants
DISPLAY_WIDTH = 128
DISPLAY_HEIGHT = 64
MAX_LINES = 4
CHARS_PER_LINE = 21

# Network constants
HOST = '0.0.0.0'  # Listen on all interfaces
PORT = 5555       # Port to listen on

# Initialize logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def init_display() -> ssd1306:
    """Initialize SSD1306 OLED display via I2C."""
    try:
        # I2C port 1, address 0x3C
        serial = i2c(port=1, address=0x3C)
        device = ssd1306(serial, width=DISPLAY_WIDTH, height=DISPLAY_HEIGHT)
        logger.info("Display initialized successfully")
        return device
    except Exception as e:
        logger.error(f"Failed to initialize display: {e}")
        raise


def display_lines(device: ssd1306, lines: List[str]) -> None:
    """
    Draw up to 4 lines of text on the OLED display.
    
    Args:
        device: SSD1306 display device
        lines: List of strings to display (max 4)
    """
    try:
        with canvas(device) as draw:
            # Use default font
            font = ImageFont.load_default()
            
            # Display up to 4 lines
            for i, line in enumerate(lines[:MAX_LINES]):
                # Truncate line if too long
                if len(line) > CHARS_PER_LINE:
                    line = line[:CHARS_PER_LINE-1] + "…"
                
                # Calculate y position (16 pixels per line)
                y = i * 16
                
                # Draw the text
                draw.text((0, y), line, font=font, fill=255)
                
        logger.debug(f"Displayed {len(lines)} lines: {lines}")
    except Exception as e:
        logger.error(f"Failed to display lines: {e}")


def parse_input(input_line: str) -> List[str]:
    """
    Parse pipe-delimited input into lines.
    
    Args:
        input_line: Input string in format "Line1|Line2|Line3|Line4"
        
    Returns:
        List of lines to display
    """
    if not input_line.strip():
        return []
    
    # Split on pipe delimiter
    lines = input_line.strip().split('|')
    
    # Pad with empty strings to ensure 4 lines
    while len(lines) < MAX_LINES:
        lines.append('')
    
    return lines[:MAX_LINES]


def main():
    """Main loop - listen on socket and display on OLED."""
    logger.info("Starting Iris display server (socket version)...")
    
    try:
        # Initialize display
        device = init_display()
        
        # Show startup message
        display_lines(device, ["Iris Display", "Server Ready", "", "Waiting..."])
        
        # Create TCP socket
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((HOST, PORT))
        server_socket.listen(1)
        
        logger.info(f"Display server listening on {HOST}:{PORT}...")
        
        # Main loop - accept connections and display
        while True:
            try:
                # Accept connection
                conn, addr = server_socket.accept()
                logger.debug(f"Connection from {addr}")
                
                # Receive data
                data = conn.recv(1024).decode('utf-8').strip()
                
                if data:
                    logger.debug(f"Received: {data}")
                    
                    # Parse and display
                    lines = parse_input(data)
                    display_lines(device, lines)
                
                # Close connection
                conn.close()
                
            except socket.error as e:
                logger.error(f"Socket error: {e}")
                continue
            except Exception as e:
                logger.error(f"Error processing connection: {e}")
                # Show error on display
                display_lines(device, ["Connection Error", str(e)[:20], "", ""])
                continue
    
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        return 1
    finally:
        logger.info("Shutting down display server")
        if 'server_socket' in locals():
            server_socket.close()
    
    return 0


if __name__ == "__main__":
    exit(main())