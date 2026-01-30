#!/usr/bin/env python3
"""
Test script for Arduino Nano OLED display.

Tests the NanoDisplay class to ensure it can communicate with 
the Arduino sketch and display text properly.

Usage:
    python3 test_nano_display.py [--port /dev/ttyUSB0]
"""

import time
import sys
import argparse
from core.display import NanoDisplay, DisplayConfig

def test_nano_display(port=None):
    """Test the Arduino Nano OLED display."""
    print("🔧 Testing Arduino Nano OLED Display")
    print("=" * 50)
    
    # Create display with optional port
    config = DisplayConfig()
    display = NanoDisplay(config, port=port)
    
    print("📡 Connecting to Arduino Nano...")
    if not display.connect():
        print("❌ Failed to connect to Arduino Nano")
        print("💡 Troubleshooting:")
        print("   1. Check USB cable connection")
        print("   2. Verify Arduino sketch is uploaded")
        print("   3. Try different port: --port /dev/ttyUSB0")
        print("   4. Check permissions: sudo usermod -a -G dialout $USER")
        return False
    
    print(f"✅ Connected to Arduino Nano")
    print(f"   Port: {display.port}")
    
    # Test sequence
    test_displays = [
        # Startup message
        ["🤖 IRIS GLASSES", "Nano Display Test", "Connection OK", "Starting tests..."],
        
        # Main menu simulation
        ["MAIN MENU", "> 1. Todo List", "  2. Translation", "  3. Connect"],
        
        # Todo list simulation  
        ["TODO LIST", "○  Buy groceries", "○  Walk dog", "○  Study for exam"],
        
        # Time/weather simulation
        ["12:34", "22°C", "Sunny", "01/29"],
        
        # Translation simulation
        ["TRANSLATION", "Hello world", "→", "Bonjour le monde"],
        
        # Device list simulation
        ["DEVICES", "● 1. Smart Light", "○ 2. Smart Fan", "○ 3. Motion Sensor"],
        
        # Long text test
        ["LONG TEXT TEST", "This is a very long line that should be truncated properly", "Short", "🎉 Done!"]
    ]
    
    print("\n🧪 Running display tests...")
    
    for i, lines in enumerate(test_displays):
        print(f"   Test {i+1}/{len(test_displays)}: {lines[0]}")
        
        success = display.send_lines(lines)
        if not success:
            print(f"❌ Test {i+1} failed!")
            return False
        
        time.sleep(2)  # Pause to see each test
    
    print("\n🎉 All tests completed!")
    
    # Clear display
    print("🧹 Clearing display...")
    display.clear()
    
    # Disconnect
    print("🔌 Disconnecting...")
    display.disconnect()
    
    print("\n✅ Arduino Nano OLED display test successful!")
    print("\n🚀 Ready to use with main application:")
    print("   python3 main.py --display nano --audio-source laptop")
    
    return True

def main():
    parser = argparse.ArgumentParser(description="Test Arduino Nano OLED display")
    parser.add_argument("--port", help="Serial port (e.g., /dev/ttyUSB0)")
    args = parser.parse_args()
    
    try:
        success = test_nano_display(args.port)
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        print("\n\n⏹️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        print("\n💡 Make sure:")
        print("   1. Arduino Nano is connected via USB")
        print("   2. Arduino sketch (arduino_nano_oled_display.ino) is uploaded")
        print("   3. OLED display is wired correctly (SDA→A4, SCL→A5)")
        print("   4. Required libraries are installed (Adafruit SSD1306, GFX)")
        sys.exit(1)

if __name__ == "__main__":
    main()