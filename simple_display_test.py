#!/usr/bin/env python3
"""
Simplest possible test - just show static text on OLED.
"""

import sys
sys.path.append('.')

from unittest.mock import Mock
from features.weather.feature import WeatherFeature

# Create minimal mocks
display = Mock()
audio = Mock() 
camera = Mock()
config = {}

# Create weather feature
weather = WeatherFeature(display, audio, camera, config)

# Set fake weather data
weather.weather_data = {
    'name': 'Boston',
    'main': {'temp': 45, 'humidity': 65},
    'weather': [{'description': 'cloudy'}]
}
weather.last_update = 0

# Test display
print("Calling weather.render()...")
weather.render()

# Show what would be displayed
lines = display.show_lines.call_args[0][0]
print("\nOLED would display these 4 lines:")
for i, line in enumerate(lines, 1):
    print(f"Line {i}: '{line}'")