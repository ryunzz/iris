#!/usr/bin/env python3
"""
Iris Smart Glasses - Display Server (Pi Zero W)

This is a DUMB terminal that runs on the Pi Zero W.
It receives text over stdin (via SSH) and displays it on the OLED.
NO LOGIC, NO DECISIONS, NO PROCESSING - just text in, display out.

Input format: "Line 1|Line 2|Line 3|Line 4\n"
"""

import sys
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
    
    # Remove empty lines at the end
    while lines and not lines[-1].strip():
        lines.pop()
    
    return lines


def main():
    """Main loop - read from stdin and display on OLED."""
    logger.info("Starting Iris display server...")
    
    try:
        device = init_display()
        
        # Show startup message
        display_lines(device, ["Iris Display", "Server Ready", "", "Waiting..."])
        
        logger.info("Listening for display commands...")
        
        # Main loop - read from stdin
        for line in sys.stdin:
            try:
                # Parse input
                lines = parse_input(line)
                
                # Display the lines
                display_lines(device, lines)
                
            except Exception as e:
                logger.error(f"Error processing input '{line.strip()}': {e}")
                # Show error on display
                display_lines(device, ["Error:", str(e)[:20], "", "Check logs"])
    
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
    finally:
        logger.info("Shutting down display server")


if __name__ == "__main__":
    main()