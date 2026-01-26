#!/usr/bin/env python3
"""
Simple test script to verify weather feature OLED display works.
This bypasses API calls and just shows static text on the display.
"""

import sys
import logging
from unittest.mock import Mock

# Add project root to path
sys.path.append('.')

from core.display import DisplayManager
from features.weather.feature import WeatherFeature

def setup_logging():
    """Set up basic logging."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

def create_mock_managers():
    """Create mock managers for testing."""
    # Mock display manager
    display = Mock(spec=DisplayManager)
    
    # Mock audio manager
    audio = Mock()
    
    # Mock camera manager
    camera = Mock()
    
    return display, audio, camera

def test_weather_display():
    """Test weather feature display without API calls."""
    setup_logging()
    
    print("Testing Weather Feature Display...")
    
    # Create mock managers
    display, audio, camera = create_mock_managers()
    
    # Mock config
    config = {
        'openweather_api_key': None,  # No API key for testing
        'weather_location': 'Test City'
    }
    
    # Create weather feature
    weather = WeatherFeature(display, audio, camera, config)
    
    # Test 1: Display without weather data
    print("\n1. Testing display without weather data...")
    weather.render()
    
    # Check what would be displayed
    assert display.show_lines.called
    lines = display.show_lines.call_args[0][0]
    print(f"Display lines: {lines}")
    
    # Test 2: Mock weather data and test display
    print("\n2. Testing display with mock weather data...")
    weather.weather_data = {
        'name': 'Test City',
        'main': {'temp': 72, 'humidity': 50},
        'weather': [{'description': 'sunny'}]
    }
    weather.last_update = 1000000000  # Mock timestamp
    
    display.reset_mock()  # Reset mock call history
    weather.render()
    
    # Check what would be displayed
    lines = display.show_lines.call_args[0][0]
    print(f"Display lines: {lines}")
    
    # Test 3: Test activation
    print("\n3. Testing activation...")
    weather.activate()
    
    print(f"Feature active: {weather.is_active}")
    print("Activation calls:")
    for call in audio.speak.call_args_list:
        print(f"  - speak: {call}")
    for call in display.show_lines.call_args_list:
        print(f"  - display: {call}")
    
    print("\nTest completed! Check the output above to see what would be displayed.")

if __name__ == "__main__":
    test_weather_display()