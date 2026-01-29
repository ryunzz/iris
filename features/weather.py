#!/usr/bin/env python3
"""
Weather feature for Iris Smart Glasses.

Provides weather information for College Station, TX using OpenWeatherMap API.
Supports mock mode with static test data.
"""

import logging
import requests
from typing import Dict, Any
from datetime import datetime
import os


logger = logging.getLogger(__name__)


class Weather:
    """
    Weather information provider for College Station, TX.
    """
    
    # College Station, TX coordinates
    LATITUDE = 30.6280
    LONGITUDE = -96.3344
    CITY_NAME = "College Station, TX"
    
    def __init__(self, mock: bool = False, api_key: str = None):
        self.mock = mock
        self.api_key = api_key or os.getenv('OPENWEATHER_API_KEY')
        
        if not self.mock and not self.api_key:
            logger.warning("No OpenWeatherMap API key provided - using mock data")
            self.mock = True
        
        logger.info(f"Weather initialized ({'mock' if self.mock else 'live'} mode)")
    
    def get_current(self) -> Dict[str, Any]:
        """
        Get current weather data.
        
        Returns:
            Dict with 'temp', 'condition', 'time' keys
        """
        if self.mock:
            return self._get_mock_weather()
        
        try:
            return self._get_live_weather()
        except Exception as e:
            logger.error(f"Failed to get live weather: {e}")
            logger.info("Falling back to mock data")
            return self._get_mock_weather()
    
    def _get_live_weather(self) -> Dict[str, Any]:
        """Get live weather from OpenWeatherMap API."""
        
        # OpenWeatherMap Current Weather API
        url = "http://api.openweathermap.org/data/2.5/weather"
        params = {
            'lat': self.LATITUDE,
            'lon': self.LONGITUDE,
            'appid': self.api_key,
            'units': 'imperial',  # Fahrenheit
            'exclude': 'minutely,hourly,daily,alerts'
        }
        
        logger.debug(f"Fetching weather from OpenWeatherMap...")
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        # Extract relevant information
        temp = round(data['main']['temp'])
        condition = data['weather'][0]['main']  # e.g., "Clear", "Clouds", "Rain"
        description = data['weather'][0]['description']  # More detailed
        
        # Map OpenWeatherMap conditions to simpler display names
        condition_mapping = {
            'Clear': 'Sunny',
            'Clouds': 'Cloudy',
            'Rain': 'Rainy',
            'Drizzle': 'Drizzle',
            'Thunderstorm': 'Stormy',
            'Snow': 'Snowy',
            'Mist': 'Misty',
            'Fog': 'Foggy',
            'Haze': 'Hazy'
        }
        
        display_condition = condition_mapping.get(condition, condition)
        
        # Get current time
        current_time = datetime.now().strftime("%-I:%M %p")  # e.g., "3:42 PM"
        
        result = {
            'temp': temp,
            'condition': display_condition,
            'time': current_time,
            'description': description,
            'city': self.CITY_NAME
        }
        
        logger.info(f"Weather: {temp}°F {display_condition} in {self.CITY_NAME}")
        return result
    
    def _get_mock_weather(self) -> Dict[str, Any]:
        """Get mock weather data for testing."""
        
        current_time = datetime.now().strftime("%-I:%M %p")
        
        # Vary mock data slightly based on time to make it interesting
        hour = datetime.now().hour
        
        if 6 <= hour < 12:
            # Morning
            temp = 72
            condition = "Sunny"
        elif 12 <= hour < 17:
            # Afternoon  
            temp = 78
            condition = "Sunny"
        elif 17 <= hour < 20:
            # Evening
            temp = 75
            condition = "Cloudy"
        else:
            # Night
            temp = 68
            condition = "Clear"
        
        result = {
            'temp': temp,
            'condition': condition,
            'time': current_time,
            'description': f"{condition.lower()} skies",
            'city': self.CITY_NAME
        }
        
        logger.debug(f"Mock weather: {temp}°F {condition}")
        return result
    
    def get_forecast(self, days: int = 3) -> List[Dict[str, Any]]:
        """
        Get weather forecast for next few days.
        
        Args:
            days: Number of days to forecast
            
        Returns:
            List of weather dicts with day name, high/low temps, condition
        """
        if self.mock:
            return self._get_mock_forecast(days)
        
        try:
            return self._get_live_forecast(days)
        except Exception as e:
            logger.error(f"Failed to get live forecast: {e}")
            return self._get_mock_forecast(days)
    
    def _get_live_forecast(self, days: int) -> List[Dict[str, Any]]:
        """Get live forecast from OpenWeatherMap API."""
        
        # OpenWeatherMap 5-day forecast API
        url = "http://api.openweathermap.org/data/2.5/forecast"
        params = {
            'lat': self.LATITUDE,
            'lon': self.LONGITUDE,
            'appid': self.api_key,
            'units': 'imperial',
            'cnt': days * 8  # 8 forecasts per day (every 3 hours)
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        # Process forecast data (simplified - just take first forecast per day)
        forecast = []
        processed_days = set()
        
        for item in data['list'][:days * 8]:
            dt = datetime.fromtimestamp(item['dt'])
            day_key = dt.strftime('%Y-%m-%d')
            
            if day_key not in processed_days:
                day_name = dt.strftime('%A')
                temp_max = round(item['main']['temp_max'])
                temp_min = round(item['main']['temp_min'])
                condition = item['weather'][0]['main']
                
                forecast.append({
                    'day': day_name,
                    'high': temp_max,
                    'low': temp_min,
                    'condition': condition
                })
                
                processed_days.add(day_key)
                
                if len(forecast) >= days:
                    break
        
        return forecast
    
    def _get_mock_forecast(self, days: int) -> List[Dict[str, Any]]:
        """Get mock forecast data."""
        
        mock_days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        mock_conditions = ['Sunny', 'Cloudy', 'Rainy', 'Sunny', 'Cloudy']
        
        forecast = []
        for i in range(days):
            day_idx = (datetime.now().weekday() + i + 1) % 7
            condition_idx = i % len(mock_conditions)
            
            forecast.append({
                'day': mock_days[day_idx],
                'high': 80 - i * 2,
                'low': 65 - i,
                'condition': mock_conditions[condition_idx]
            })
        
        return forecast
    
    def is_available(self) -> bool:
        """Check if weather service is available."""
        if self.mock:
            return True
        
        return self.api_key is not None


# Import fix
from typing import List


if __name__ == "__main__":
    # Test weather functionality
    import sys
    
    logging.basicConfig(level=logging.INFO)
    
    mock_mode = "--mock" in sys.argv
    
    print(f"Testing Weather functionality ({'mock' if mock_mode else 'live'} mode)...")
    
    weather = Weather(mock=mock_mode)
    
    if not weather.is_available():
        print("❌ Weather service not available")
        print("Set OPENWEATHER_API_KEY environment variable for live data")
        sys.exit(1)
    
    # Test current weather
    print("\n--- Current Weather ---")
    current = weather.get_current()
    print(f"🌡️  {current['temp']}°F")
    print(f"☁️  {current['condition']}")
    print(f"🕐 {current['time']}")
    print(f"📍 {current['city']}")
    
    # Test forecast
    print("\n--- 3-Day Forecast ---")
    forecast = weather.get_forecast(3)
    for day_data in forecast:
        print(f"{day_data['day']}: {day_data['high']}°/{day_data['low']}° {day_data['condition']}")
    
    # Test display formatting (as used in IDLE screen)
    print("\n--- Display Format (IDLE screen) ---")
    display_line1 = f"{current['temp']}F  {current['condition']}"
    display_line2 = "College Station TX"
    display_line3 = f"     {current['time']}"
    
    print("┌─────────────────────┐")
    print(f"│ {display_line1:<19} │")
    print(f"│ {display_line2:<19} │")
    print(f"│ {display_line3:<19} │")
    print(f"│ {'':19} │")
    print("└─────────────────────┘")
    
    print("\nWeather test complete")