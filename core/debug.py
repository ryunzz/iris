#!/usr/bin/env python3
"""
Hardware diagnostic mode for Iris Smart Glasses.

Comprehensive testing and validation of hardware integration.
Helps diagnose issues and provides exact fix instructions.
"""

import asyncio
import logging
import requests
import time
from typing import Dict, List, Optional, Any
from datetime import datetime

from .discovery import create_registry, DeviceRegistry
from .iot import IoTClient, DeviceOfflineError
from .display import Display


logger = logging.getLogger(__name__)


class HardwareDiagnostic:
    """Comprehensive hardware testing and validation."""
    
    def __init__(self):
        self.results: Dict[str, Any] = {}
        self.issues: List[Dict[str, str]] = []
        self.registry: Optional[DeviceRegistry] = None
        self.iot: Optional[IoTClient] = None
        
    async def run_full_diagnostic(self) -> Dict[str, Any]:
        """Run complete hardware diagnostic suite."""
        print("🔧 IRIS HARDWARE DIAGNOSTIC MODE")
        print("=" * 50)
        
        # Step 1: Show expected contracts
        self._show_hardware_contracts()
        
        # Step 2: Network discovery
        print("\n🌐 NETWORK DISCOVERY")
        print("-" * 30)
        await self._test_discovery()
        
        # Step 3: Device testing
        print("\n🔌 DEVICE TESTING")  
        print("-" * 30)
        await self._test_all_devices()
        
        # Step 4: Pi testing
        print("\n🖥️  PI DISPLAY TESTING")
        print("-" * 30)
        await self._test_pi_display()
        
        # Step 5: Motion server testing
        print("\n📡 MOTION SERVER TESTING")
        print("-" * 30)
        await self._test_motion_server()
        
        # Step 6: Summary and fixes
        print("\n📋 DIAGNOSTIC SUMMARY")
        print("-" * 30)
        self._show_summary()
        
        return self.results
    
    def _show_hardware_contracts(self):
        """Display expected hardware API contracts."""
        print("Expected devices and their API contracts:")
        print()
        
        contracts = {
            "LIGHT (iris-light.local)": [
                "GET /on      → {\"status\": \"on\"}",
                "GET /off     → {\"status\": \"off\"}",
                "GET /status  → {\"status\": \"on\"} or {\"status\": \"off\"}",
                "GET /health  → {\"device\": \"iris-light\", \"ok\": true}"
            ],
            "FAN (iris-fan.local)": [
                "GET /on      → {\"status\": \"on\", \"speed\": \"high\"}",
                "GET /off     → {\"status\": \"off\", \"speed\": \"off\"}",
                "GET /low     → {\"status\": \"on\", \"speed\": \"low\"}",
                "GET /high    → {\"status\": \"on\", \"speed\": \"high\"}",
                "GET /status  → {\"status\": \"on\", \"speed\": \"low\"}",
                "GET /health  → {\"device\": \"iris-fan\", \"ok\": true}"
            ],
            "MOTION (iris-motion.local)": [
                "GET /on      → {\"alerts\": \"enabled\"}",
                "GET /off     → {\"alerts\": \"disabled\"}",
                "GET /status  → {\"alerts\": \"enabled\"} or {\"alerts\": \"disabled\"}",
                "Must POST to http://<laptop>:5000/motion when triggered"
            ],
            "DISTANCE (iris-distance.local)": [
                "GET /distance → {\"distance_cm\": <number>}",
                "GET /health   → {\"device\": \"iris-distance\", \"ok\": true}"
            ],
            "PI DISPLAY (iris-pi.local)": [
                "SSH on port 22",
                "Receives: \"Line1|Line2|Line3|Line4\\n\" via stdin"
            ]
        }
        
        for device, endpoints in contracts.items():
            print(f"{device}:")
            for endpoint in endpoints:
                print(f"  {endpoint}")
            print()
    
    async def _test_discovery(self):
        """Test device discovery system."""
        print("Testing device discovery...")
        
        self.registry = create_registry(mock=False)
        devices = self.registry.discover_all(timeout=10.0)
        
        print(f"Discovery completed. Found {len(devices)} devices:")
        
        for device in devices:
            status = "✅" if device.online else "❌"
            print(f"{status} {device.name} ({device.device_type}) - {device.ip}:{device.port}")
            
            if device.device_type not in self.results:
                self.results[device.device_type] = {}
            
            self.results[device.device_type]['discovered'] = device.online
            self.results[device.device_type]['ip'] = device.ip
            self.results[device.device_type]['port'] = device.port
        
        # Check for missing critical devices
        required_devices = ['pi']
        for device_type in required_devices:
            if not self.registry.is_device_online(device_type):
                self.issues.append({
                    'severity': 'critical',
                    'device': device_type,
                    'issue': 'Device not found via discovery',
                    'fix': f'1. Ensure {device_type} is powered on\n2. Check it\'s on same network\n3. Verify mDNS is working'
                })
    
    async def _test_all_devices(self):
        """Test all discovered IoT devices."""
        if not self.registry:
            print("❌ No registry available for device testing")
            return
        
        self.iot = IoTClient(registry=self.registry, mock=False)
        
        # Test each device type
        device_tests = {
            'light': self._test_light_device,
            'fan': self._test_fan_device, 
            'motion': self._test_motion_device,
            'distance': self._test_distance_device,
            'glasses': self._test_glasses_device
        }
        
        for device_type, test_func in device_tests.items():
            if self.registry.is_device_online(device_type):
                print(f"\nTesting {device_type}...")
                await test_func(device_type)
            else:
                print(f"\n⚪ {device_type} not found, skipping tests")
    
    async def _test_light_device(self, device_type: str):
        """Test light device API."""
        device = self.registry.get_device(device_type)
        base_url = f"http://{device.ip}:{device.port}"
        
        tests = [
            ('/health', 'GET', None, lambda r: 'device' in r and 'ok' in r),
            ('/status', 'GET', None, lambda r: 'status' in r),
            ('/on', 'GET', None, lambda r: r.get('status') == 'on'),
            ('/off', 'GET', None, lambda r: r.get('status') == 'off'),
        ]
        
        await self._run_device_tests(device_type, base_url, tests)
    
    async def _test_fan_device(self, device_type: str):
        """Test fan device API."""
        device = self.registry.get_device(device_type)
        base_url = f"http://{device.ip}:{device.port}"
        
        tests = [
            ('/health', 'GET', None, lambda r: 'device' in r and 'ok' in r),
            ('/status', 'GET', None, lambda r: 'status' in r and 'speed' in r),
            ('/on', 'GET', None, lambda r: r.get('status') == 'on' and 'speed' in r),
            ('/off', 'GET', None, lambda r: r.get('status') == 'off'),
            ('/low', 'GET', None, lambda r: r.get('status') == 'on' and r.get('speed') == 'low'),
            ('/high', 'GET', None, lambda r: r.get('status') == 'on' and r.get('speed') == 'high'),
        ]
        
        await self._run_device_tests(device_type, base_url, tests)
    
    async def _test_motion_device(self, device_type: str):
        """Test motion sensor device API."""
        device = self.registry.get_device(device_type)
        base_url = f"http://{device.ip}:{device.port}"
        
        tests = [
            ('/health', 'GET', None, lambda r: 'device' in r and 'ok' in r),
            ('/status', 'GET', None, lambda r: 'alerts' in r),
            ('/on', 'GET', None, lambda r: r.get('alerts') == 'enabled'),
            ('/off', 'GET', None, lambda r: r.get('alerts') == 'disabled'),
        ]
        
        await self._run_device_tests(device_type, base_url, tests)
        
        # Note about motion alerts
        print(f"  ℹ️  Motion sensor should POST to http://[laptop]:5000/motion when triggered")
    
    async def _test_distance_device(self, device_type: str):
        """Test distance sensor device API."""
        device = self.registry.get_device(device_type)
        base_url = f"http://{device.ip}:{device.port}"
        
        tests = [
            ('/health', 'GET', None, lambda r: 'device' in r and 'ok' in r),
            ('/distance', 'GET', None, lambda r: 'distance_cm' in r and isinstance(r['distance_cm'], (int, float))),
        ]
        
        await self._run_device_tests(device_type, base_url, tests)
        
        # Test multiple readings
        print("  Testing distance readings...")
        for i in range(3):
            try:
                response = requests.get(f"{base_url}/distance", timeout=2)
                data = response.json()
                distance = data.get('distance_cm')
                print(f"    Reading {i+1}: {distance} cm")
                await asyncio.sleep(0.5)
            except Exception as e:
                print(f"    Reading {i+1}: Failed - {e}")
    
    async def _test_glasses_device(self, device_type: str):
        """Test glasses device API."""
        device = self.registry.get_device(device_type)
        base_url = f"http://{device.ip}:{device.port}"
        
        # Test display endpoint
        try:
            test_lines = ["Test Message", "From Glasses 1", "", ""]
            response = requests.post(
                f"{base_url}/display",
                json={"lines": test_lines},
                headers={'Content-Type': 'application/json'},
                timeout=3
            )
            
            if response.status_code == 200:
                print("  ✅ Display message sent successfully")
                data = response.json()
                if data.get('success'):
                    print("    Response indicates success")
                else:
                    print(f"    Response: {data}")
            else:
                print(f"  ❌ Display endpoint returned {response.status_code}")
                self._add_api_fix('glasses', '/display', f"HTTP {response.status_code}", "Should return 200 with success: true")
                
        except Exception as e:
            print(f"  ❌ Display test failed: {e}")
    
    async def _run_device_tests(self, device_type: str, base_url: str, tests: List[tuple]):
        """Run a series of API tests on a device."""
        if device_type not in self.results:
            self.results[device_type] = {}
        
        self.results[device_type]['tests'] = []
        
        for endpoint, method, data, validator in tests:
            try:
                if method == 'GET':
                    response = requests.get(f"{base_url}{endpoint}", timeout=3)
                else:
                    response = requests.post(f"{base_url}{endpoint}", json=data, timeout=3)
                
                if response.status_code == 200:
                    try:
                        json_data = response.json()
                        
                        if validator(json_data):
                            print(f"  ✅ {endpoint} - OK")
                            self.results[device_type]['tests'].append({
                                'endpoint': endpoint,
                                'status': 'pass',
                                'response': json_data
                            })
                        else:
                            print(f"  ❌ {endpoint} - WRONG FORMAT")
                            print(f"    Got: {json_data}")
                            self.results[device_type]['tests'].append({
                                'endpoint': endpoint,
                                'status': 'format_error',
                                'response': json_data
                            })
                            self._add_api_fix(device_type, endpoint, str(json_data), "Check API specification")
                            
                    except ValueError:
                        print(f"  ❌ {endpoint} - NOT JSON")
                        print(f"    Got: {response.text[:100]}")
                        self._add_api_fix(device_type, endpoint, response.text[:50], "Should return JSON")
                else:
                    print(f"  ❌ {endpoint} - HTTP {response.status_code}")
                    self._add_api_fix(device_type, endpoint, f"HTTP {response.status_code}", "Should return HTTP 200")
                    
            except requests.RequestException as e:
                print(f"  ❌ {endpoint} - CONNECTION ERROR: {e}")
                self.results[device_type]['tests'].append({
                    'endpoint': endpoint,
                    'status': 'connection_error',
                    'error': str(e)
                })
    
    async def _test_pi_display(self):
        """Test Pi display connection."""
        if not self.registry or not self.registry.is_device_online("pi"):
            print("❌ Pi not available for display testing")
            return
        
        print("Testing Pi display connection...")
        
        try:
            display = Display(registry=self.registry, mock=False)
            
            if display.connected:
                print("✅ Pi display connection successful")
                
                # Test display update
                test_lines = ["Hardware Test", "Display Works", str(datetime.now().strftime("%H:%M:%S")), ""]
                success = display.update(test_lines)
                
                if success:
                    print("✅ Display update successful")
                    self.results['pi']['display_test'] = 'pass'
                else:
                    print("❌ Display update failed")
                    self.results['pi']['display_test'] = 'fail'
                
                display.disconnect()
            else:
                print("❌ Failed to connect to Pi display")
                self.results['pi']['display_test'] = 'connection_failed'
                self.issues.append({
                    'severity': 'high',
                    'device': 'pi',
                    'issue': 'Cannot establish SSH connection',
                    'fix': '1. Check SSH is enabled on Pi\n2. Verify SSH key or password auth\n3. Test: ssh pi@iris-pi.local'
                })
                
        except Exception as e:
            print(f"❌ Pi display test error: {e}")
            self.results['pi']['display_test'] = f'error: {e}'
    
    async def _test_motion_server(self):
        """Test motion alert server."""
        print("Testing motion alert server...")
        
        try:
            # Test health endpoint
            response = requests.get('http://localhost:5000/health', timeout=2)
            if response.status_code == 200:
                print("✅ Motion server health check passed")
                health_data = response.json()
                print(f"    Server: {health_data.get('service')}")
                print(f"    Queue size: {health_data.get('queue_size', 0)}")
            else:
                print(f"❌ Motion server health check failed: HTTP {response.status_code}")
            
            # Test motion endpoint
            test_alert = {"device": "test", "timestamp": datetime.now().isoformat()}
            response = requests.post('http://localhost:5000/motion', json=test_alert, timeout=2)
            
            if response.status_code == 200:
                print("✅ Motion alert endpoint working")
                self.results['motion_server'] = 'working'
            else:
                print(f"❌ Motion alert endpoint failed: HTTP {response.status_code}")
                self.results['motion_server'] = f'failed_{response.status_code}'
                
        except requests.ConnectionError:
            print("❌ Motion server not running")
            self.results['motion_server'] = 'not_running'
            self.issues.append({
                'severity': 'medium',
                'device': 'motion_server',
                'issue': 'Motion alert server not accessible',
                'fix': 'Server should start automatically with main.py'
            })
        except Exception as e:
            print(f"❌ Motion server test error: {e}")
            self.results['motion_server'] = f'error: {e}'
    
    def _add_api_fix(self, device_type: str, endpoint: str, current: str, expected: str):
        """Add API fix instruction."""
        self.issues.append({
            'severity': 'high',
            'device': device_type,
            'issue': f'{endpoint} returns wrong format',
            'current': current,
            'expected': expected,
            'fix': f'Update {device_type} code for {endpoint} endpoint'
        })
    
    def _show_summary(self):
        """Show diagnostic summary and fixes."""
        total_devices = len(self.results)
        online_devices = sum(1 for result in self.results.values() 
                           if isinstance(result, dict) and result.get('discovered', False))
        
        print(f"Devices discovered: {online_devices}/{total_devices}")
        print(f"Issues found: {len(self.issues)}")
        print()
        
        if not self.issues:
            print("🎉 All tests passed! Hardware integration looks good.")
            return
        
        # Group issues by severity
        critical_issues = [i for i in self.issues if i['severity'] == 'critical']
        high_issues = [i for i in self.issues if i['severity'] == 'high']
        medium_issues = [i for i in self.issues if i['severity'] == 'medium']
        
        if critical_issues:
            print("🚨 CRITICAL ISSUES (Must fix):")
            for issue in critical_issues:
                print(f"   {issue['device']}: {issue['issue']}")
                print(f"   Fix: {issue['fix']}")
                print()
        
        if high_issues:
            print("⚠️  HIGH PRIORITY ISSUES:")
            for issue in high_issues:
                print(f"   {issue['device']}: {issue['issue']}")
                if 'current' in issue:
                    print(f"   Current: {issue['current']}")
                    print(f"   Expected: {issue['expected']}")
                print(f"   Fix: {issue['fix']}")
                print()
        
        if medium_issues:
            print("ℹ️  MEDIUM PRIORITY ISSUES:")
            for issue in medium_issues:
                print(f"   {issue['device']}: {issue['issue']}")
                print(f"   Fix: {issue['fix']}")
                print()
        
        print("💡 NEXT STEPS:")
        print("1. Fix critical and high priority issues")
        print("2. Re-run diagnostic: python main.py --debug-hardware")
        print("3. When all tests pass, hardware integration is complete")


async def run_hardware_debug():
    """Entry point for hardware diagnostic mode."""
    diagnostic = HardwareDiagnostic()
    await diagnostic.run_full_diagnostic()


if __name__ == "__main__":
    asyncio.run(run_hardware_debug())