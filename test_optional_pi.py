#!/usr/bin/env python3
"""
Test script to verify Pi display is optional.

Tests that terminal and none displays start immediately without waiting for Pi.
"""

import sys
import os
import time
import subprocess
import signal
from threading import Timer

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_display_startup(display_type, timeout=10):
    """Test that a display type starts up quickly without waiting for Pi."""
    print(f"Testing --display {display_type} startup speed...")
    
    cmd = [
        sys.executable, "main.py",
        "--display", display_type,
        "--test-mode"  # Exit after setup
    ]
    
    start_time = time.time()
    
    try:
        # Run with timeout to detect hanging
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=os.path.dirname(os.path.abspath(__file__))
        )
        
        end_time = time.time()
        duration = end_time - start_time
        
        if result.returncode == 0:
            print(f"✅ {display_type}: Started successfully in {duration:.1f}s")
            
            # Check that it didn't wait for Pi
            if "Waiting for Pi display" in result.stderr:
                print(f"❌ {display_type}: Still waiting for Pi (should skip)")
                return False
            elif "Skipping Pi discovery" in result.stderr:
                print(f"✅ {display_type}: Correctly skipped Pi discovery")
                return True
            elif display_type == "pi" and "Waiting for Pi display" in result.stderr:
                print(f"✅ {display_type}: Correctly waited for Pi (as expected)")
                return True
            else:
                print(f"⚠️  {display_type}: Unknown Pi behavior")
                return True
                
        else:
            print(f"❌ {display_type}: Failed to start (exit code {result.returncode})")
            if result.stderr:
                print(f"Error: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"❌ {display_type}: Timed out after {timeout}s (likely waiting for Pi)")
        return False
    except Exception as e:
        print(f"❌ {display_type}: Exception occurred: {e}")
        return False

def main():
    """Run Pi display optional tests."""
    print("🔍 Testing Pi Display Optional Behavior")
    print("=" * 40)
    
    # Test cases: display types that should NOT wait for Pi
    fast_displays = ["none", "terminal", "nano", "esp32"]
    results = {}
    
    for display_type in fast_displays:
        if display_type == "esp32":
            # ESP32 requires IP, so test separately
            print(f"\n⚠️  Skipping {display_type} test (requires --display-ip)")
            continue
            
        results[display_type] = test_display_startup(display_type, timeout=15)
        time.sleep(1)  # Brief pause between tests
    
    # Test pi display (should wait for Pi and timeout)
    print(f"\n🔍 Testing --display pi behavior (should wait for Pi)...")
    print("This should timeout as expected (no Pi available)")
    results["pi"] = test_display_startup("pi", timeout=5)  # Short timeout since we expect it to hang
    
    # Summary
    print("\n" + "=" * 40)
    print("Test Results:")
    
    total_tests = 0
    passed_tests = 0
    
    for display_type, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {display_type:8} {status}")
        total_tests += 1
        if passed:
            passed_tests += 1
    
    print(f"\nOverall: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests >= len(fast_displays):
        print("\n🎉 Pi display is now properly optional!")
        print("   Non-Pi displays start immediately without waiting.")
        return 0
    else:
        print("\n💥 Pi display optional feature has issues")
        return 1

if __name__ == "__main__":
    sys.exit(main())