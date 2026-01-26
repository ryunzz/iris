"""
Weather Feature for Iris Smart Glasses

Displays current weather conditions on OLED display.
"""

import json
import time
import requests
from typing import Optional, Dict, Any
import logging

from core.feature_base import FeatureBase

logger = logging.getLogger(__name__)


class WeatherFeature(FeatureBase):
    """Weather display feature for Iris Smart Glasses."""
    
    name = "weather"
    
    def __init__(self, display, audio, camera, config):
        """Initialize weather feature."""
        super().__init__(display, audio, camera, config)
        
        self.api_key = config.get('openweather_api_key')
        self.location = config.get('weather_location', 'New York,US')
        self.weather_data = None
        self.last_update = 0
        self.update_interval = 600  # 10 minutes
        self.api_url = "http://api.openweathermap.org/data/2.5/weather"
        
    def activate(self) -> None:
        """Activate weather feature and fetch initial data."""
        self.is_active = True
        logger.info(f"Activating {self.name} feature")
        
        self.speak_feedback("Weather feature activated")
        
        # Show loading message
        self.display.show_lines([
            "Weather",
            "Loading...",
            "",
            "Please wait"
        ])
        
        # Fetch initial weather data
        self.fetch_weather()
        
    def deactivate(self) -> None:
        """Deactivate weather feature."""
        self.is_active = False
        self.weather_data = None
        logger.info(f"Deactivating {self.name} feature")
        
    def process_voice(self, transcript: str) -> None:
        """Handle voice commands for weather feature."""
        command = transcript.lower().strip()
        
        if "update" in command or "refresh" in command:
            self.speak_feedback("Updating weather")
            self.fetch_weather()
            
        elif "location" in command:
            # Simple location change - could be enhanced with better parsing
            if "new york" in command:
                self.location = "New York,US"
            elif "london" in command:
                self.location = "London,UK"
            elif "tokyo" in command:
                self.location = "Tokyo,JP"
            else:
                self.speak_feedback("Location not recognized. Try New York, London, or Tokyo")
                return
                
            self.speak_feedback(f"Location changed to {self.location.split(',')[0]}")
            self.fetch_weather()
            
        elif "help" in command:
            self.speak_feedback("Say update to refresh, or location followed by a city name")
            
        else:
            self.speak_feedback("Say update to refresh weather, or location and city name")
    
    def fetch_weather(self) -> None:
        """Fetch weather data from OpenWeatherMap API."""
        if not self.api_key:
            logger.error("OpenWeatherMap API key not configured")
            self.handle_error(Exception("API key not configured"), "fetch_weather")
            return
            
        try:
            params = {
                'q': self.location,
                'appid': self.api_key,
                'units': 'imperial'  # Fahrenheit
            }
            
            response = requests.get(self.api_url, params=params, timeout=10)
            response.raise_for_status()
            
            self.weather_data = response.json()
            self.last_update = time.time()
            
            logger.info(f"Weather data updated for {self.location}")
            
        except requests.RequestException as e:
            logger.error(f"Failed to fetch weather data: {e}")
            self.handle_error(e, "fetch_weather")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse weather data: {e}")
            self.handle_error(e, "fetch_weather")
    
    def render(self) -> None:
        """Update OLED display with current weather."""
        if not self.weather_data:
            self.display.show_lines([
                "Weather",
                "No data",
                "",
                "Check connection"
            ])
            return
            
        try:
            # Extract weather information
            temp = round(self.weather_data['main']['temp'])
            description = self.weather_data['weather'][0]['description'].title()
            location_name = self.weather_data['name']
            humidity = self.weather_data['main']['humidity']
            
            # Format for 4 lines, ~21 chars each
            line1 = f"{location_name}"[:21]
            line2 = f"{temp}°F {description[:10]}"[:21]
            line3 = f"Humidity: {humidity}%"[:21]
            
            # Time since last update
            minutes_ago = int((time.time() - self.last_update) / 60)
            line4 = f"Updated {minutes_ago}m ago"[:21]
            
            self.display.show_lines([line1, line2, line3, line4])
            
        except KeyError as e:
            logger.error(f"Unexpected weather data format: {e}")
            self.handle_error(e, "render")
    
    def process_frame(self, frame: Optional[bytes]) -> None:
        """Weather feature doesn't need camera input."""
        pass
    
    def get_help_text(self) -> str:
        """Get help text for weather feature."""
        return "Weather commands: 'update', 'location [city]'"
    
    def should_update(self) -> bool:
        """Check if weather data needs updating."""
        return (time.time() - self.last_update) > self.update_interval