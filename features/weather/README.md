# Weather Feature

Displays current weather conditions on OLED display using OpenWeatherMap API.

## Activation

"Hey Iris, activate weather"

## Voice Commands (while active)

- "update" / "refresh" — Fetch latest weather data
- "location [city]" — Change location (supports New York, London, Tokyo)
- "help" — Get available commands

## Display Format

```
New York
75°F Clear Sky
Humidity: 45%
Updated 2m ago
```

- Line 1: City name
- Line 2: Temperature and weather description
- Line 3: Humidity percentage
- Line 4: Last update time

## Setup Requirements

### 1. OpenWeatherMap API Key

1. Sign up for free at [OpenWeatherMap](https://openweathermap.org/api)
2. Get your API key
3. Add to your `.env` file:
   ```
   OPENWEATHER_API_KEY=your_api_key_here
   ```

### 2. Configuration

Add to your `config.yaml`:
```yaml
# Weather settings
weather_location: "New York,US"  # Default location
openweather_api_key: ${OPENWEATHER_API_KEY}  # Will load from .env
```

### 3. Enable Feature

Uncomment these lines in `main.py`:
```python
# Line ~29: Add import
from features.weather.feature import WeatherFeature

# Line ~142: Register feature  
features["weather"] = WeatherFeature(display, audio, camera, config)
```

## Implementation Notes

- Weather updates automatically every 10 minutes
- Temperature displayed in Fahrenheit
- Supports basic location switching via voice
- Handles API errors gracefully with display feedback
- Uses requests library for HTTP calls

## Supported Locations

Currently supports quick voice switching to:
- "New York" → New York, US
- "London" → London, UK  
- "Tokyo" → Tokyo, JP

Additional locations can be added by modifying the `process_voice()` method.