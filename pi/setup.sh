#!/bin/bash
#
# Iris Smart Glasses - Pi Zero W Setup Script
#
# This script configures the Pi Zero W for use as a display server.
# Run this script on the Pi Zero W after flashing Raspberry Pi OS.
#

set -e  # Exit on any error

echo "=== Iris Smart Glasses Pi Zero W Setup ==="
echo

# Check if running on Pi
if ! grep -q "Raspberry Pi" /proc/cpuinfo; then
    echo "Error: This script must be run on a Raspberry Pi"
    exit 1
fi

echo "1. Updating system packages..."
sudo apt update && sudo apt upgrade -y

echo "2. Installing system dependencies..."
sudo apt install -y python3-pip python3-venv i2c-tools git

echo "3. Enabling I2C interface..."
# Enable I2C via raspi-config (non-interactive)
sudo raspi-config nonint do_i2c 0

echo "4. Adding user to i2c group..."
sudo usermod -a -G i2c $USER

echo "5. Creating project directory..."
mkdir -p ~/iris/pi
cd ~/iris

echo "6. Setting up Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

echo "7. Installing Python dependencies..."
pip install --upgrade pip
pip install luma.oled Pillow

echo "8. Testing I2C connection..."
echo "Scanning for I2C devices..."
i2cdetect -y 1

echo
echo "Setup complete! Next steps:"
echo
echo "1. Copy the iris project files to ~/iris/ on the Pi"
echo "2. Reboot the Pi to ensure I2C is fully enabled:"
echo "   sudo reboot"
echo
echo "3. After reboot, test the display server:"
echo "   cd ~/iris"
echo "   source venv/bin/activate" 
echo "   python pi/display_server.py"
echo
echo "4. In another terminal, test sending text:"
echo "   echo 'Hello|World|Test|Display' | ssh pi@raspberrypi.local 'cd iris && source venv/bin/activate && python pi/display_server.py'"
echo
echo "Expected I2C address for SSD1306 OLED: 0x3c"
echo "If your display doesn't appear in the i2cdetect scan above, check your wiring."
echo

# Create a simple test script
cat > ~/test_display.py << 'EOF'
#!/usr/bin/env python3
"""Simple test script for the OLED display."""
import sys
sys.path.append('/home/pi/iris')

from pi.display_server import init_display, display_lines

def main():
    print("Testing OLED display...")
    try:
        device = init_display()
        display_lines(device, ["Test", "Display", "Working!", "Success"])
        print("✓ Display test successful!")
    except Exception as e:
        print(f"✗ Display test failed: {e}")

if __name__ == "__main__":
    main()
EOF

chmod +x ~/test_display.py

echo "Created ~/test_display.py for quick testing"
echo "Run it with: cd ~ && source iris/venv/bin/activate && python test_display.py"