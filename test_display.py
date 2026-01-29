#!/usr/bin/env python3
"""
Quick test script for the new display system.

Tests all display types to ensure they work correctly.
"""

import time
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.display import Display, DisplayConfig


def test_display_type(display_type: str, **kwargs):
    """Test a specific display type."""
    print(f"\n=== Testing {display_type} display ===")
    
    try:
        display = Display(
            display_type=display_type,
            config=DisplayConfig(),
            **kwargs
        )
        
        if not display.connected:
            print(f"❌ Failed to connect to {display_type} display")
            return False
        
        print(f"✅ Connected to {display_type} display")
        
        # Test basic text
        display.show_text("Display Test\nLine 2\nLine 3\nLine 4")
        time.sleep(2)
        
        # Test idle screen
        weather = {
            "temperature": 22.5,
            "description": "Sunny",
            "location": "Test City"
        }
        display.show_idle(weather)
        time.sleep(2)
        
        # Test main menu
        display.show_main_menu()
        time.sleep(2)
        
        # Clear and disconnect
        display.clear()
        display.disconnect()
        
        print(f"✅ {display_type} display test passed")
        return True
        
    except Exception as e:
        print(f"❌ {display_type} display test failed: {e}")
        return False


def main():
    """Run display tests."""
    print("🖥️  Display System Test")
    print("=" * 30)
    
    results = {}
    
    # Test none display
    results['none'] = test_display_type('none')
    
    # Test terminal display
    results['terminal'] = test_display_type('terminal')
    
    # Test nano display (may fail if not connected)
    print("\n⚠️  Nano test may fail if Arduino not connected")
    results['nano'] = test_display_type('nano')
    
    # Test ESP32 display (will fail without valid IP)
    print("\n⚠️  ESP32 test will fail without valid IP")
    results['esp32'] = test_display_type('esp32', display_ip='192.168.1.100')
    
    # Print summary
    print("\n" + "=" * 30)
    print("Test Results:")
    for display_type, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {display_type:8} {status}")
    
    passed_count = sum(results.values())
    total_count = len(results)
    
    print(f"\nOverall: {passed_count}/{total_count} tests passed")
    
    if passed_count >= 2:  # none and terminal should always work
        print("🎉 Display system is working correctly!")
        return 0
    else:
        print("💥 Display system has issues")
        return 1


if __name__ == "__main__":
    sys.exit(main())