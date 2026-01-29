#!/usr/bin/env python3
"""
Pytest configuration and shared fixtures.

Provides common test setup and utilities.
"""

import pytest
import tempfile
import os
import sys
from unittest.mock import patch

# Add project root to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


@pytest.fixture(scope="session")
def mock_environment():
    """Set up mock environment variables for testing."""
    test_env = {
        'OPENWEATHER_API_KEY': 'test_weather_key',
        'DEEPL_API_KEY': 'test_deepl_key'
    }
    
    with patch.dict(os.environ, test_env):
        yield test_env


@pytest.fixture
def temp_config_file():
    """Create temporary config file for testing."""
    config_content = """
# Test configuration
audio_source: "mock"
phone_ip: ""

discovery:
  mdns_timeout: 1
  rescan_interval: 5

device_hostnames:
  pi: "iris-pi.local"
  light: "iris-light.local"
  fan: "iris-fan.local"

server:
  port: 5001

weather:
  location: "Test City"
  lat: 30.0
  lon: -96.0

translation:
  source: "en"
  target: "fr"

timeout_seconds: 1
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(config_content)
        temp_path = f.name
    
    yield temp_path
    
    # Cleanup
    os.unlink(temp_path)


@pytest.fixture
def mock_discovery_registry():
    """Create mock discovery registry for testing."""
    from core.discovery import create_registry
    return create_registry(mock=True)


@pytest.fixture
def disable_network():
    """Disable network calls during testing."""
    with patch('socket.socket') as mock_socket, \
         patch('aiohttp.ClientSession') as mock_session, \
         patch('requests.get') as mock_requests:
        
        # Make network calls fail or return mocks
        mock_socket.side_effect = OSError("Network disabled in tests")
        mock_session.side_effect = OSError("Network disabled in tests") 
        mock_requests.side_effect = OSError("Network disabled in tests")
        
        yield