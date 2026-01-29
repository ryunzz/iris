#!/usr/bin/env python3
"""
Unit tests for the IoT client system.

Tests device communication, mock mode, and error handling.
"""

import pytest
import aiohttp
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta

from core.iot import IoTClient
from core.discovery import create_registry


class TestIoTClient:
    """Test suite for IoTClient."""
    
    @pytest.fixture
    def mock_client(self):
        """Create IoT client with mock registry."""
        registry = create_registry(mock=True)
        return IoTClient(registry, mock=True)
    
    @pytest.fixture
    def real_client(self):
        """Create IoT client with real registry."""
        registry = create_registry(mock=True)  # Still use mock registry for tests
        return IoTClient(registry, mock=False)
    
    def test_initialization(self, mock_client):
        """Test IoT client initialization."""
        assert mock_client.registry is not None
        assert mock_client.mock is True
        assert len(mock_client._device_cache) == 0
    
    def test_mock_light_commands(self, mock_client):
        """Test mock light device commands."""
        # Turn on light
        response = mock_client.send_command("iris-light.local", "on")
        assert response["status"] == "success"
        assert "on" in response["message"].lower()
        
        # Turn off light
        response = mock_client.send_command("iris-light.local", "off")
        assert response["status"] == "success"
        assert "off" in response["message"].lower()
        
        # Invalid command
        response = mock_client.send_command("iris-light.local", "invalid")
        assert response["status"] == "error"
    
    def test_mock_fan_commands(self, mock_client):
        """Test mock fan device commands."""
        # Turn on fan
        response = mock_client.send_command("iris-fan.local", "on")
        assert response["status"] == "success"
        
        # Set fan speed
        response = mock_client.send_command("iris-fan.local", "low")
        assert response["status"] == "success"
        
        response = mock_client.send_command("iris-fan.local", "high")
        assert response["status"] == "success"
        
        # Turn off fan
        response = mock_client.send_command("iris-fan.local", "off")
        assert response["status"] == "success"
    
    def test_mock_motion_commands(self, mock_client):
        """Test mock motion sensor commands."""
        # Start monitoring
        response = mock_client.send_command("iris-motion.local", "start")
        assert response["status"] == "success"
        
        # Stop monitoring
        response = mock_client.send_command("iris-motion.local", "stop")
        assert response["status"] == "success"
        
        # Check status
        response = mock_client.send_command("iris-motion.local", "status")
        assert response["status"] == "success"
        assert "detected" in response
    
    def test_mock_distance_commands(self, mock_client):
        """Test mock distance sensor commands."""
        # Get distance
        response = mock_client.send_command("iris-distance.local", "distance")
        assert response["status"] == "success"
        assert "distance_cm" in response
        assert isinstance(response["distance_cm"], (int, float))
        
        # Start continuous mode
        response = mock_client.send_command("iris-distance.local", "start_continuous")
        assert response["status"] == "success"
        
        # Stop continuous mode
        response = mock_client.send_command("iris-distance.local", "stop_continuous")
        assert response["status"] == "success"
    
    def test_mock_glasses_commands(self, mock_client):
        """Test mock glasses commands."""
        # Send notification
        response = mock_client.send_command("iris-glasses2.local", "notify", 
                                          data={"message": "Test notification"})
        assert response["status"] == "success"
        
        # Send urgent message
        response = mock_client.send_command("iris-glasses2.local", "urgent",
                                          data={"message": "Urgent alert"})
        assert response["status"] == "success"
    
    def test_device_not_found(self, mock_client):
        """Test handling of non-existent devices."""
        response = mock_client.send_command("nonexistent.local", "on")
        assert response["status"] == "error"
        assert "not found" in response["message"].lower()
    
    def test_device_status_caching(self, mock_client):
        """Test device status caching."""
        hostname = "iris-light.local"
        
        # First call - should populate cache
        status1 = mock_client.get_device_status(hostname)
        assert hostname in mock_client._device_cache
        
        # Second call - should use cache
        status2 = mock_client.get_device_status(hostname)
        assert status1 == status2
        
        # Check cache expiry (artificially expire)
        cache_entry = mock_client._device_cache[hostname]
        cache_entry["timestamp"] = datetime.now() - timedelta(minutes=10)
        
        # Should refresh cache
        status3 = mock_client.get_device_status(hostname)
        new_timestamp = mock_client._device_cache[hostname]["timestamp"]
        assert new_timestamp > cache_entry["timestamp"]
    
    def test_send_to_glasses(self, mock_client):
        """Test glasses notification helper."""
        # Send normal notification
        response = mock_client.send_to_glasses("Test message")
        assert response["status"] == "success"
        
        # Send urgent notification
        response = mock_client.send_to_glasses("Urgent message", urgent=True)
        assert response["status"] == "success"
    
    @pytest.mark.asyncio
    async def test_get_distance_async(self, mock_client):
        """Test async distance reading."""
        distance = await mock_client.get_distance_async("iris-distance.local")
        assert isinstance(distance, (int, float))
        assert 0 <= distance <= 400  # Reasonable range for ultrasonic sensor
    
    @pytest.mark.asyncio 
    async def test_distance_not_found(self, mock_client):
        """Test distance reading with non-existent device."""
        distance = await mock_client.get_distance_async("nonexistent.local")
        assert distance is None
    
    @patch('aiohttp.ClientSession.post')
    @pytest.mark.asyncio
    async def test_real_http_request(self, mock_post, real_client):
        """Test real HTTP request with mocked aiohttp."""
        # Mock successful response
        mock_response = AsyncMock()
        mock_response.json = AsyncMock(return_value={"status": "success"})
        mock_response.status = 200
        mock_post.return_value.__aenter__.return_value = mock_response
        
        response = real_client.send_command("iris-light.local", "on")
        
        # Should have made HTTP request
        mock_post.assert_called_once()
        assert response["status"] == "success"
    
    @patch('aiohttp.ClientSession.post')
    @pytest.mark.asyncio
    async def test_http_request_error(self, mock_post, real_client):
        """Test HTTP request error handling."""
        # Mock failed response
        mock_post.side_effect = aiohttp.ClientError("Connection failed")
        
        response = real_client.send_command("iris-light.local", "on")
        
        assert response["status"] == "error"
        assert "failed" in response["message"].lower()
    
    def test_device_type_detection(self, mock_client):
        """Test device type detection from hostname."""
        # Should detect device types correctly
        light_status = mock_client.get_device_status("iris-light.local")
        assert light_status["type"] == "light"
        
        fan_status = mock_client.get_device_status("iris-fan.local")
        assert fan_status["type"] == "fan"
        
        motion_status = mock_client.get_device_status("iris-motion.local")
        assert motion_status["type"] == "motion"
    
    def test_cache_cleanup(self, mock_client):
        """Test cache cleanup functionality."""
        # Add some cached entries
        mock_client.get_device_status("iris-light.local")
        mock_client.get_device_status("iris-fan.local")
        
        assert len(mock_client._device_cache) == 2
        
        # Artificially expire one entry
        hostname = "iris-light.local"
        mock_client._device_cache[hostname]["timestamp"] = datetime.now() - timedelta(minutes=10)
        
        # Access should trigger cleanup
        mock_client.get_device_status("iris-fan.local")
        
        # Expired entry should be cleaned up on next access
        mock_client.get_device_status("iris-motion.local")
    
    def test_command_with_data(self, mock_client):
        """Test commands with additional data."""
        data = {"brightness": 75, "color": "blue"}
        response = mock_client.send_command("iris-light.local", "set", data=data)
        
        assert response["status"] == "success"
        # Data should be included in mock response
        assert "data" in response or "brightness" in str(response)
    
    def test_multiple_device_types(self, mock_client):
        """Test commands across multiple device types."""
        devices = [
            ("iris-light.local", "on"),
            ("iris-fan.local", "low"),
            ("iris-motion.local", "start"),
            ("iris-distance.local", "distance")
        ]
        
        for hostname, command in devices:
            response = mock_client.send_command(hostname, command)
            assert response["status"] == "success", f"Failed for {hostname}:{command}"


class TestIoTClientErrorHandling:
    """Test error handling and edge cases."""
    
    @pytest.fixture
    def client(self):
        """Create client for error testing."""
        registry = create_registry(mock=True)
        return IoTClient(registry, mock=True)
    
    def test_empty_command(self, client):
        """Test empty command handling."""
        response = client.send_command("iris-light.local", "")
        assert response["status"] == "error"
    
    def test_none_hostname(self, client):
        """Test None hostname handling."""
        response = client.send_command(None, "on")
        assert response["status"] == "error"
    
    def test_malformed_data(self, client):
        """Test malformed data handling."""
        # Should handle non-dict data gracefully
        response = client.send_command("iris-light.local", "set", data="invalid")
        # Should not crash, may succeed or fail depending on implementation
        assert "status" in response
    
    @pytest.mark.asyncio
    async def test_async_error_handling(self, client):
        """Test async method error handling."""
        # Non-existent device
        distance = await client.get_distance_async("invalid.local")
        assert distance is None
        
        # Empty hostname
        distance = await client.get_distance_async("")
        assert distance is None


if __name__ == "__main__":
    pytest.main([__file__])