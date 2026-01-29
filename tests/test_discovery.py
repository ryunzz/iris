#!/usr/bin/env python3
"""
Unit tests for the device discovery system.

Tests mDNS discovery, device registry, and mock mode.
"""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock

from core.discovery import DeviceRegistry, create_registry


class TestDeviceRegistry:
    """Test suite for DeviceRegistry."""
    
    @pytest.fixture
    def mock_registry(self):
        """Create a mock registry for testing."""
        return create_registry(mock=True)
    
    @pytest.fixture  
    def real_registry(self):
        """Create a real registry for testing."""
        with patch('zeroconf.Zeroconf'):
            return create_registry(mock=False)
    
    def test_singleton_behavior(self):
        """Test that registry behaves as singleton."""
        reg1 = create_registry(mock=True)
        reg2 = create_registry(mock=True)
        assert reg1 is reg2
    
    def test_mock_registry_devices(self, mock_registry):
        """Test mock registry returns mock devices."""
        devices = mock_registry.get_devices()
        
        # Should have mock devices
        assert len(devices) > 0
        
        # Check for expected mock devices
        device_names = [d.name for d in devices]
        assert "iris-pi.local" in device_names
        assert "iris-light.local" in device_names
        assert "iris-fan.local" in device_names
    
    def test_mock_device_properties(self, mock_registry):
        """Test mock device properties."""
        devices = mock_registry.get_devices()
        pi_device = next(d for d in devices if d.name == "iris-pi.local")
        
        assert pi_device.ip.startswith("192.168.1.")
        assert pi_device.port == 22
        assert pi_device.type == "ssh"
        assert pi_device.last_seen is not None
    
    def test_get_device_by_hostname(self, mock_registry):
        """Test device lookup by hostname."""
        device = mock_registry.get_device("iris-pi.local")
        assert device is not None
        assert device.name == "iris-pi.local"
        
        # Non-existent device
        assert mock_registry.get_device("nonexistent.local") is None
    
    def test_get_devices_by_type(self, mock_registry):
        """Test filtering devices by type."""
        ssh_devices = mock_registry.get_devices_by_type("ssh")
        assert len(ssh_devices) == 1
        assert ssh_devices[0].name == "iris-pi.local"
        
        http_devices = mock_registry.get_devices_by_type("http")
        assert len(http_devices) >= 4  # light, fan, motion, distance
    
    def test_device_health_updates(self, mock_registry):
        """Test device health status updates."""
        devices = mock_registry.get_devices()
        initial_count = len(devices)
        
        # All devices should be healthy initially
        healthy_devices = [d for d in devices if d.is_healthy()]
        assert len(healthy_devices) == initial_count
        
        # Update health
        mock_registry.update_device_health("iris-light.local", False)
        
        # Device should now be unhealthy
        device = mock_registry.get_device("iris-light.local")
        assert device is not None
        assert not device.is_healthy()
    
    def test_start_stop_scanning(self, mock_registry):
        """Test background scanning control."""
        # Should not crash in mock mode
        mock_registry.start_scanning()
        assert mock_registry._scanning
        
        mock_registry.stop_scanning()
        assert not mock_registry._scanning
    
    @patch('zeroconf.Zeroconf')
    @patch('zeroconf.ServiceBrowser')
    def test_real_registry_initialization(self, mock_browser, mock_zeroconf):
        """Test real registry initialization with mocks."""
        registry = DeviceRegistry()
        
        # Should initialize zeroconf
        mock_zeroconf.assert_called_once()
        
        # Should create service browser
        mock_browser.assert_called_once()
    
    def test_device_aging(self, mock_registry):
        """Test that old devices are marked unhealthy."""
        devices = mock_registry.get_devices()
        light_device = next(d for d in devices if d.name == "iris-light.local")
        
        # Artificially age the device
        old_time = time.time() - 120  # 2 minutes ago
        light_device.last_seen = old_time
        
        # Should be unhealthy now
        assert not light_device.is_healthy()
    
    def test_network_interface_detection(self, mock_registry):
        """Test network interface IP detection."""
        ip = mock_registry._get_local_ip()
        
        # Should return a valid IP format
        assert ip is not None
        parts = ip.split('.')
        assert len(parts) == 4
        assert all(part.isdigit() for part in parts)
    
    def test_udp_broadcast_setup(self, mock_registry):
        """Test UDP broadcast socket setup."""
        # Should not crash in mock mode
        mock_registry._setup_udp_broadcast()
        
        # In mock mode, socket should be None
        assert mock_registry._udp_socket is None
    
    def test_service_listener_callbacks(self, real_registry):
        """Test service listener callback methods."""
        listener = real_registry._service_listener
        
        # Mock service info
        mock_info = Mock()
        mock_info.name = "iris-test._http._tcp.local."
        mock_info.parsed_addresses.return_value = ["192.168.1.100"]
        mock_info.port = 80
        
        # Should handle add service
        listener.add_service(None, None, mock_info.name)
        
        # Should handle remove service  
        listener.remove_service(None, None, mock_info.name)
        
        # Should handle update service
        listener.update_service(None, None, mock_info.name)


class TestDeviceRegistryIntegration:
    """Integration tests for device registry."""
    
    def test_create_registry_mock_mode(self):
        """Test creating registry in mock mode."""
        registry = create_registry(mock=True)
        assert registry is not None
        assert len(registry.get_devices()) > 0
    
    @patch('zeroconf.Zeroconf')
    def test_create_registry_real_mode(self, mock_zeroconf):
        """Test creating registry in real mode."""
        registry = create_registry(mock=False)
        assert registry is not None
        mock_zeroconf.assert_called_once()
    
    def test_registry_persistence(self):
        """Test that registry maintains state."""
        # Create first registry
        reg1 = create_registry(mock=True)
        initial_devices = reg1.get_devices()
        
        # Create second registry (should be same instance)
        reg2 = create_registry(mock=True)
        second_devices = reg2.get_devices()
        
        # Should have same devices
        assert len(initial_devices) == len(second_devices)
        assert reg1 is reg2


if __name__ == "__main__":
    pytest.main([__file__])