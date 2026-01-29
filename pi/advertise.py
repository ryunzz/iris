#!/usr/bin/env python3
"""
mDNS advertisement service for Iris Pi Display.

Runs on Pi Zero W to advertise its presence via mDNS.
Start this before display_server.py to ensure discovery works.
"""

import socket
import logging
import time
import signal
import sys
from datetime import datetime

try:
    from zeroconf import Zeroconf, ServiceInfo
    ZEROCONF_AVAILABLE = True
except ImportError:
    ZEROCONF_AVAILABLE = False
    print("ERROR: zeroconf not available")
    print("Install with: pip3 install zeroconf")
    sys.exit(1)


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_local_ip():
    """Get the Pi's local IP address."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Connect to a non-routable address to get local IP
        s.connect(('10.255.255.255', 1))
        ip = s.getsockname()[0]
    except Exception:
        # Fallback to localhost
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip


def create_service_info(ip_address: str) -> ServiceInfo:
    """
    Create mDNS service info for Iris Pi Display.
    
    Args:
        ip_address: Pi's IP address
        
    Returns:
        ServiceInfo object for registration
    """
    hostname = socket.gethostname()
    
    # Service details
    service_type = "_iris-display._tcp.local."
    service_name = f"Iris Pi Display._iris-display._tcp.local."
    
    # Properties to include in mDNS record
    properties = {
        'type': 'display',
        'version': '1.0',
        'device': 'pi',
        'hostname': hostname,
        'started_at': datetime.now().isoformat()
    }
    
    # Create service info
    info = ServiceInfo(
        service_type,
        service_name,
        addresses=[socket.inet_aton(ip_address)],
        port=22,  # SSH port
        properties=properties,
        server=f"{hostname}.local."
    )
    
    return info


class IrisAdvertiser:
    """Manages mDNS advertisement for Iris Pi."""
    
    def __init__(self):
        self.zeroconf = None
        self.service_info = None
        self.running = False
        
        # Setup signal handlers for clean shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def start(self) -> bool:
        """
        Start mDNS advertisement.
        
        Returns:
            True if started successfully
        """
        try:
            # Get local IP
            ip_address = get_local_ip()
            logger.info(f"Local IP address: {ip_address}")
            
            # Create Zeroconf instance
            self.zeroconf = Zeroconf()
            
            # Create service info
            self.service_info = create_service_info(ip_address)
            
            # Register service
            logger.info("Registering mDNS service...")
            self.zeroconf.register_service(self.service_info)
            
            self.running = True
            
            logger.info("🎉 mDNS advertisement started successfully!")
            logger.info(f"   Service: {self.service_info.name}")
            logger.info(f"   Address: {ip_address}:22")
            logger.info(f"   Hostname: iris-pi.local")
            logger.info("")
            logger.info("The Pi is now discoverable by the Iris system.")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to start mDNS advertisement: {e}")
            return False
    
    def stop(self):
        """Stop mDNS advertisement."""
        if not self.running:
            return
        
        logger.info("Stopping mDNS advertisement...")
        
        try:
            if self.service_info and self.zeroconf:
                self.zeroconf.unregister_service(self.service_info)
                
            if self.zeroconf:
                self.zeroconf.close()
                
            self.running = False
            logger.info("mDNS advertisement stopped")
            
        except Exception as e:
            logger.error(f"Error stopping mDNS advertisement: {e}")
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, shutting down...")
        self.stop()
        sys.exit(0)
    
    def run_forever(self):
        """Run advertisement until interrupted."""
        if not self.running:
            logger.error("Advertisement not started")
            return
        
        try:
            logger.info("Press Ctrl+C to stop advertisement")
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Interrupted by user")
        finally:
            self.stop()


def test_advertisement():
    """Test mDNS advertisement functionality."""
    logger.info("Testing mDNS advertisement...")
    
    advertiser = IrisAdvertiser()
    
    if advertiser.start():
        logger.info("✅ Advertisement test successful")
        
        # Run for a short time in test mode
        logger.info("Running test for 10 seconds...")
        try:
            time.sleep(10)
        except KeyboardInterrupt:
            pass
        
        advertiser.stop()
        logger.info("Test complete")
    else:
        logger.error("❌ Advertisement test failed")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Iris Pi mDNS Advertisement')
    parser.add_argument('--test', action='store_true', 
                       help='Run test mode (10 seconds then exit)')
    parser.add_argument('--daemon', action='store_true',
                       help='Run as daemon (no console output)')
    
    args = parser.parse_args()
    
    # Configure logging for daemon mode
    if args.daemon:
        # Setup file logging for daemon mode
        file_handler = logging.FileHandler('/var/log/iris-advertise.log')
        file_handler.setFormatter(
            logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        )
        logger.addHandler(file_handler)
        logger.removeHandler(logging.getLogger().handlers[0])  # Remove console handler
    
    logger.info("=" * 50)
    logger.info("    IRIS PI MDNS ADVERTISEMENT")
    logger.info("=" * 50)
    
    # Check if running on Pi (basic check)
    try:
        with open('/proc/cpuinfo', 'r') as f:
            cpuinfo = f.read()
            if 'Raspberry Pi' not in cpuinfo:
                logger.warning("This doesn't appear to be running on a Raspberry Pi")
    except:
        pass
    
    if args.test:
        test_advertisement()
    else:
        advertiser = IrisAdvertiser()
        
        if advertiser.start():
            advertiser.run_forever()
        else:
            logger.error("Failed to start advertisement")
            sys.exit(1)


if __name__ == "__main__":
    main()