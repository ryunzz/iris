#!/usr/bin/env python3
"""
Dynamic device discovery for Iris Smart Glasses.

Uses mDNS (Zeroconf) as primary method with UDP broadcast as fallback.
No hardcoded IP addresses - all devices discovered at runtime.
"""

import socket
import threading
import time
import json
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Optional, List, Dict, Callable
from zeroconf import Zeroconf, ServiceListener, ServiceBrowser, ServiceInfo


logger = logging.getLogger(__name__)


@dataclass
class DiscoveredDevice:
    """Represents a discovered device in the Iris ecosystem."""
    device_type: str      # "pi", "light", "fan", "motion", "distance", "glasses"
    name: str             # Human-readable name
    ip: str               # Discovered IP address
    port: int             # Service port
    last_seen: datetime   # For connection health tracking
    online: bool          # Current availability status
    hostname: str = ""    # mDNS hostname (e.g. "iris-light.local")
    
    def __post_init__(self):
        if not self.hostname:
            self.hostname = f"iris-{self.device_type}.local"


class IrisServiceListener(ServiceListener):
    """Listens for Iris device mDNS advertisements."""
    
    def __init__(self, registry: 'DeviceRegistry'):
        self.registry = registry
    
    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        """Called when a new service is discovered."""
        try:
            info = zc.get_service_info(type_, name)
            if info:
                self._process_service_info(info, True)
        except Exception as e:
            logger.warning(f"Error processing new service {name}: {e}")
    
    def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        """Called when a service is removed."""
        # Try to match by name and mark as offline
        for device in self.registry._devices.values():
            if name.startswith(f"iris-{device.device_type}"):
                device.online = False
                logger.info(f"Device {device.name} went offline")
                break
    
    def update_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        """Called when a service is updated."""
        try:
            info = zc.get_service_info(type_, name)
            if info:
                self._process_service_info(info, False)
        except Exception as e:
            logger.warning(f"Error updating service {name}: {e}")
    
    def _process_service_info(self, info: ServiceInfo, is_new: bool) -> None:
        """Extract device info from mDNS service info."""
        if not info.addresses:
            return
            
        # Get IP address (use first address)
        ip = socket.inet_ntoa(info.addresses[0])
        
        # Extract device type from service name
        device_type = None
        name_parts = info.name.lower().split('.')
        if len(name_parts) > 0:
            service_name = name_parts[0]
            if service_name.startswith('iris-'):
                device_type = service_name[5:]  # Remove 'iris-' prefix
        
        if not device_type:
            return
            
        # Map device types
        type_mapping = {
            'pi': 'pi',
            'light': 'light', 
            'fan': 'fan',
            'motion': 'motion',
            'distance': 'distance',
            'glasses2': 'glasses'
        }
        
        device_type = type_mapping.get(device_type)
        if not device_type:
            return
        
        # Create device object
        device = DiscoveredDevice(
            device_type=device_type,
            name=self._get_device_name(device_type),
            ip=ip,
            port=info.port,
            last_seen=datetime.now(),
            online=True,
            hostname=info.server
        )
        
        # Add to registry
        old_device = self.registry._devices.get(device_type)
        self.registry._devices[device_type] = device
        
        if is_new or not old_device:
            logger.info(f"Discovered {device.name} at {ip}:{info.port}")
        else:
            logger.debug(f"Updated {device.name} at {ip}:{info.port}")
    
    def _get_device_name(self, device_type: str) -> str:
        """Get human-readable name for device type."""
        names = {
            'pi': 'Pi Display',
            'light': 'Lights',
            'fan': 'Smart Fan', 
            'motion': 'Motion Sensor',
            'distance': 'Distance Sensor',
            'glasses': 'Glasses 2'
        }
        return names.get(device_type, f'Unknown Device ({device_type})')


class DeviceRegistry:
    """
    Singleton that maintains discovered devices.
    Handles mDNS discovery with UDP broadcast fallback.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, mock: bool = False, config: dict = None):
        # Prevent re-initialization
        if hasattr(self, '_initialized'):
            return
            
        self._initialized = True
        self.mock = mock
        self.config = config or {}
        self._devices: Dict[str, DiscoveredDevice] = {}
        self._zeroconf: Optional[Zeroconf] = None
        self._browser: Optional[ServiceBrowser] = None
        self._scan_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        
        # Load expected hostnames from config
        self.expected_hostnames = self.config.get('device_hostnames', {
            'pi': 'iris-pi.local',
            'light': 'iris-light.local', 
            'fan': 'iris-fan.local',
            'motion': 'iris-motion.local',
            'distance': 'iris-distance.local',
            'glasses': 'iris-glasses2.local'
        })
        
        if self.mock:
            self._setup_mock_devices()
        else:
            self._setup_discovery()
    
    def _setup_mock_devices(self) -> None:
        """Create mock devices for testing."""
        mock_devices = {
            'pi': DiscoveredDevice('pi', 'Mock Pi Display', '127.0.0.1', 22, datetime.now(), True),
            'light': DiscoveredDevice('light', 'Mock Lights', '127.0.0.1', 80, datetime.now(), True),
            'fan': DiscoveredDevice('fan', 'Mock Smart Fan', '127.0.0.1', 80, datetime.now(), True),
            'motion': DiscoveredDevice('motion', 'Mock Motion Sensor', '127.0.0.1', 80, datetime.now(), True),
            'distance': DiscoveredDevice('distance', 'Mock Distance Sensor', '127.0.0.1', 80, datetime.now(), True),
            'glasses': DiscoveredDevice('glasses', 'Mock Glasses 2', '127.0.0.1', 80, datetime.now(), True)
        }
        self._devices = mock_devices
        logger.info("Loaded mock devices for testing")
    
    def _setup_discovery(self) -> None:
        """Initialize mDNS discovery system."""
        try:
            self._zeroconf = Zeroconf()
            listener = IrisServiceListener(self)
            
            # Listen for Iris device services
            # Devices should advertise as "_iris-iot._tcp.local." or "_iris-display._tcp.local."
            services = ["_iris-iot._tcp.local.", "_iris-display._tcp.local.", "_http._tcp.local."]
            self._browser = ServiceBrowser(self._zeroconf, services, listener)
            
            logger.info("mDNS discovery initialized")
        except Exception as e:
            logger.error(f"Failed to initialize mDNS discovery: {e}")
            logger.info("Will use UDP broadcast fallback only")
    
    def discover_all(self, timeout: float = 5.0) -> List[DiscoveredDevice]:
        """
        Discover all Iris devices on the network.
        
        Args:
            timeout: How long to wait for discovery
            
        Returns:
            List of discovered devices
        """
        if self.mock:
            return list(self._devices.values())
        
        logger.info(f"Starting device discovery (timeout: {timeout}s)")
        
        # Give mDNS time to work
        if self._zeroconf:
            time.sleep(min(timeout, 3.0))
        
        # Try UDP broadcast as fallback
        self._udp_broadcast_discovery(timeout=2.0)
        
        # Load manual devices from config (fallback for discovery failures)
        self._load_manual_devices()
        
        # Return what we found
        devices = [d for d in self._devices.values() if d.online]
        logger.info(f"Discovery complete: found {len(devices)} devices")
        
        return devices
    
    def _udp_broadcast_discovery(self, timeout: float = 2.0) -> None:
        """
        Fallback UDP broadcast discovery for devices that don't support mDNS.
        """
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.settimeout(0.5)
            
            # Broadcast discovery message
            message = json.dumps({"discover": "iris"}).encode()
            broadcast_port = self.config.get('discovery', {}).get('udp_broadcast_port', 5353)
            
            # Try multiple broadcast addresses
            broadcast_addresses = ['255.255.255.255', '192.168.1.255', '192.168.43.255', '10.0.0.255']
            
            for addr in broadcast_addresses:
                try:
                    sock.sendto(message, (addr, broadcast_port))
                except:
                    continue
            
            # Listen for responses
            start_time = time.time()
            while time.time() - start_time < timeout:
                try:
                    data, addr = sock.recvfrom(1024)
                    response = json.loads(data.decode())
                    self._process_udp_response(response, addr[0])
                except socket.timeout:
                    continue
                except Exception as e:
                    logger.debug(f"UDP discovery error: {e}")
                    continue
        
        except Exception as e:
            logger.debug(f"UDP broadcast discovery failed: {e}")
        finally:
            try:
                sock.close()
            except:
                pass
    
    def _process_udp_response(self, response: dict, ip: str) -> None:
        """Process UDP discovery response."""
        device_type = response.get('type')
        device_name = response.get('name', f'Unknown {device_type}')
        port = response.get('port', 80)
        
        if device_type and device_type in ['pi', 'light', 'fan', 'motion', 'distance', 'glasses']:
            device = DiscoveredDevice(
                device_type=device_type,
                name=device_name,
                ip=ip,
                port=port,
                last_seen=datetime.now(),
                online=True
            )
            
            self._devices[device_type] = device
            logger.info(f"UDP discovery: found {device_name} at {ip}:{port}")
    
    def get_device(self, device_type: str) -> Optional[DiscoveredDevice]:
        """
        Get a specific device by type.
        
        Args:
            device_type: Type of device ("pi", "light", "fan", etc.)
            
        Returns:
            DiscoveredDevice or None if not found
        """
        device = self._devices.get(device_type)
        if device and self._is_device_stale(device):
            device.online = False
        return device
    
    def wait_for_device(self, device_type: str, timeout: float = 30.0) -> DiscoveredDevice:
        """
        Wait for a specific device to be discovered.
        
        Args:
            device_type: Type of device to wait for
            timeout: Maximum time to wait
            
        Returns:
            DiscoveredDevice when found
            
        Raises:
            TimeoutError: If device not found within timeout
        """
        if self.mock:
            return self._devices[device_type]
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            device = self.get_device(device_type)
            if device and device.online:
                return device
            
            # Try discovery again
            self.discover_all(timeout=2.0)
            time.sleep(1.0)
        
        raise TimeoutError(f"Device '{device_type}' not found within {timeout} seconds")
    
    def is_device_online(self, device_type: str) -> bool:
        """Check if a device is currently online."""
        device = self.get_device(device_type)
        return device is not None and device.online
    
    def get_all_online(self) -> List[DiscoveredDevice]:
        """Get all currently online devices."""
        return [d for d in self._devices.values() if d.online and not self._is_device_stale(d)]
    
    def _is_device_stale(self, device: DiscoveredDevice) -> bool:
        """Check if device info is stale (not seen recently)."""
        if self.mock:
            return False
        
        stale_timeout = timedelta(minutes=2)
        return datetime.now() - device.last_seen > stale_timeout
    
    def start_background_scan(self) -> None:
        """Start background thread for periodic device rescanning."""
        if self.mock or self._scan_thread:
            return
        
        self._scan_thread = threading.Thread(
            target=self._background_scan_worker,
            daemon=True
        )
        self._scan_thread.start()
        logger.info("Background device scanning started")
    
    def _background_scan_worker(self) -> None:
        """Background worker that periodically rescans for devices."""
        rescan_interval = self.config.get('discovery', {}).get('rescan_interval', 30)
        
        while not self._stop_event.wait(rescan_interval):
            try:
                logger.debug("Background rescan for devices...")
                self.discover_all(timeout=3.0)
                
                # Mark stale devices as offline
                for device in self._devices.values():
                    if self._is_device_stale(device):
                        if device.online:
                            logger.info(f"Device {device.name} marked offline (stale)")
                            device.online = False
                        
            except Exception as e:
                logger.error(f"Background scan error: {e}")
    
    def stop(self) -> None:
        """Stop discovery services."""
        self._stop_event.set()
        
        if self._browser:
            self._browser.cancel()
        
        if self._zeroconf:
            self._zeroconf.close()
        
        if self._scan_thread and self._scan_thread.is_alive():
            self._scan_thread.join(timeout=5.0)
        
        logger.info("Device discovery stopped")
    
    def get_device_list_for_display(self) -> List[Dict[str, str]]:
        """
        Get device list formatted for display in DEVICE_LIST state.
        Uses specific order: Lights, Fan, Distance, Motion.
        
        Returns:
            List of dict with 'name' and 'status' keys
        """
        devices = []
        
        # Define desired order: Lights, Fan, Distance, Motion
        device_order = ['light', 'fan', 'distance', 'motion']
        
        # Add devices in the specified order
        for device_type in device_order:
            if device_type in self._devices:
                device = self._devices[device_type]
                status = "Online" if device.online else "Offline"
                devices.append({
                    'name': device.name,
                    'status': status,
                    'type': device.device_type
                })
        
        # Add any other devices not in the predefined order (pi, glasses, etc.)
        for device in self._devices.values():
            if device.device_type not in device_order:
                status = "Online" if device.online else "Offline"
                devices.append({
                    'name': device.name,
                    'status': status,
                    'type': device.device_type
                })
        
        return devices
    
    def add_manual_device(self, device_type: str, ip: str, port: int = 80) -> None:
        """
        Manually add a device (fallback when discovery fails).
        
        Args:
            device_type: Type of device
            ip: IP address
            port: Service port
        """
        device = DiscoveredDevice(
            device_type=device_type,
            name=self._get_device_name(device_type),
            ip=ip,
            port=port,
            last_seen=datetime.now(),
            online=True
        )
        
        self._devices[device_type] = device
        logger.info(f"Manually added {device.name} at {ip}:{port}")
    
    def _is_valid_ip(self, ip: str) -> bool:
        """
        Validate IPv4 address format and check for placeholder values.
        
        Args:
            ip: IP address string to validate
            
        Returns:
            True if valid IPv4 address, False otherwise
        """
        if not ip or not isinstance(ip, str):
            return False
            
        # Skip placeholder values
        placeholders = ['CHANGE_ME', 'change_me', 'placeholder', '', '0.0.0.0']
        if ip.strip() in placeholders:
            return False
            
        # Validate IPv4 format
        try:
            parts = ip.split('.')
            if len(parts) != 4:
                return False
                
            for part in parts:
                num = int(part)
                if num < 0 or num > 255:
                    return False
                    
            return True
        except (ValueError, AttributeError):
            return False
    
    def _load_manual_devices(self) -> None:
        """
        Load manual devices from config.yaml.
        Called after mDNS/UDP discovery to add configured fallback devices.
        Validates IPs and skips placeholder values.
        """
        manual_devices = self.config.get('manual_devices', {})
        if not manual_devices:
            logger.debug("No manual devices configured")
            return
        
        loaded_count = 0
        skipped_count = 0
        
        for device_type, device_config in manual_devices.items():
            # Skip if device was already discovered
            if device_type in self._devices and self._devices[device_type].online:
                logger.debug(f"Skipping manual device '{device_type}' - already discovered via mDNS/UDP")
                continue
                
            # Extract config
            ip = device_config.get('ip')
            if not ip:
                logger.warning(f"Manual device '{device_type}' missing IP address")
                skipped_count += 1
                continue
                
            # Validate IP address
            if not self._is_valid_ip(ip):
                logger.warning(f"Manual device '{device_type}' has invalid/placeholder IP: {ip} - skipping")
                skipped_count += 1
                continue
                
            name = device_config.get('name', self._get_device_name(device_type))
            port = device_config.get('port', 80)
            
            # Validate port number
            if not isinstance(port, int) or port < 1 or port > 65535:
                logger.warning(f"Manual device '{device_type}' has invalid port: {port} - using default 80")
                port = 80
            
            # Add the device
            device = DiscoveredDevice(
                device_type=device_type,
                name=name,
                ip=ip,
                port=port,
                last_seen=datetime.now(),
                online=True
            )
            
            self._devices[device_type] = device
            logger.info(f"Loaded manual device: {name} at {ip}:{port}")
            loaded_count += 1
        
        if loaded_count > 0:
            logger.info(f"Loaded {loaded_count} manual device(s) from config")
        if skipped_count > 0:
            logger.info(f"Skipped {skipped_count} invalid manual device(s)")
    
    def _get_device_name(self, device_type: str) -> str:
        """Get human-readable name for device type."""
        names = {
            'pi': 'Pi Display',
            'light': 'Lights',
            'fan': 'Smart Fan',
            'motion': 'Motion Sensor', 
            'distance': 'Distance Sensor',
            'glasses': 'Glasses 2'
        }
        return names.get(device_type, f'Unknown Device ({device_type})')


# Convenience functions for external use
def create_registry(mock: bool = False, config: dict = None) -> DeviceRegistry:
    """Create or get the singleton device registry."""
    return DeviceRegistry(mock=mock, config=config)


def discover_devices(timeout: float = 5.0, mock: bool = False) -> List[DiscoveredDevice]:
    """Quick device discovery function."""
    registry = create_registry(mock=mock)
    return registry.discover_all(timeout=timeout)


if __name__ == "__main__":
    # Test discovery
    import sys
    
    mock_mode = "--mock" in sys.argv
    
    logging.basicConfig(level=logging.INFO)
    logger.info(f"Testing device discovery (mock={mock_mode})")
    
    registry = create_registry(mock=mock_mode)
    devices = registry.discover_all(timeout=10.0)
    
    print(f"\nFound {len(devices)} devices:")
    for device in devices:
        status = "✅" if device.online else "❌"
        print(f"{status} {device.name} ({device.device_type}) - {device.ip}:{device.port}")
    
    # Test waiting for specific device
    if not mock_mode:
        try:
            print(f"\nWaiting for Pi...")
            pi = registry.wait_for_device("pi", timeout=10.0)
            print(f"✅ Found Pi at {pi.ip}")
        except TimeoutError:
            print("❌ Pi not found within timeout")
    
    registry.stop()