# UNDERSTAND.md - Iris Smart Glasses Build Log

## Requirements Interpretation

Building voice-controlled smart glasses with three main components:
1. **Phone** (Android with IP Webcam) - Microphone and camera input
2. **Laptop** - "Brain" running STT, command parsing, and IoT coordination
3. **Pi Zero W** - Display driver for 128x64 OLED via SSH connection

**Key Architecture:** State machine-based command processing with dynamic device discovery, supporting multiple audio sources and full mock mode for testing without hardware.

## Architecture Decisions

### 1. Dynamic Discovery Over Hardcoded IPs
**Decision:** Use mDNS (Zeroconf) with UDP broadcast fallback instead of hardcoded IP addresses.
**Reasoning:** System needs to work in different network environments (hackathon venues, demos, development). Hardcoded IPs will break when network changes.
**Implementation:** DeviceRegistry singleton with background rescanning every 30 seconds.

### 2. State Machine Over Feature-Based Architecture  
**Decision:** Replace existing feature modules with centralized state machine in core/parser.py.
**Reasoning:** Voice commands need predictable context-aware responses. State machine provides clear command interpretation based on current screen/mode.
**Trade-off:** Less modularity but better UX and clearer command flow.

### 3. Pluggable Audio Sources
**Decision:** Support laptop microphone, IP Webcam, and mock keyboard input via command line flags.
**Reasoning:** Team has different hardware setups (iPhone vs Android), need testing without phone, and CI/CD needs mock mode.
**Options:**
- `--audio-source laptop` - Built-in mic (works everywhere, no phone needed)
- `--audio-source ipwebcam` - Android IP Webcam app (Texas team)  
- `--audio-source mock` - Keyboard input (testing)

### 4. Persistent SSH Connection to Pi
**Decision:** Maintain single SSH connection with open channel instead of new connection per update.
**Reasoning:** Display updates need <100ms latency. SSH handshake adds 100-500ms overhead per update.
**Implementation:** paramiko SSH client with invoke_shell() and automatic reconnection.

### 5. Thread-Safe Interrupt Handling
**Decision:** Use queue.Queue for motion alerts and other interrupts instead of direct callbacks.
**Reasoning:** Motion alerts arrive from Flask thread while main loop runs in different thread. Direct callbacks would cause race conditions with display updates.

## Assumptions Made

1. **Network Setup:** All devices (laptop, Pi, ESP32s, phone) on same WiFi network or hotspot
2. **Pi SSH Access:** Passwordless SSH key authentication already configured 
3. **mDNS Support:** Network allows mDNS traffic (some enterprise networks block it)
4. **Hardware API Contracts:** ESP32 devices implement exact JSON response formats as specified
5. **Phone IP Webcam:** Android phone with IP Webcam app configured and running
6. **Speech Recognition:** Google Speech Recognition API accessible (uses free tier)
7. **Display Protocol:** Pi accepts pipe-delimited text via stdin: "Line1|Line2|Line3|Line4\n"

## Design Trade-offs

### Discovery vs Performance
**Trade-off:** mDNS discovery adds ~5 second startup time vs instant with hardcoded IPs
**Choice:** Discovery - robustness more important than 5 second startup delay
**Mitigation:** Background rescanning + manual IP fallback if discovery fails

### Audio Source Flexibility vs Complexity  
**Trade-off:** Single IP Webcam audio source (simple) vs multiple sources (complex)
**Choice:** Multiple sources - enables testing without phone and accommodates team's different hardware
**Complexity:** Added factory pattern and source abstraction layer

### Mock Mode Completeness vs Development Time
**Trade-off:** Partial mock (some components real) vs full mock (everything simulated)
**Choice:** Full mock - must be able to test entire system without any hardware
**Development Cost:** ~30% more code for mock implementations, but enables CI/CD and development without hardware setup

### State Machine Centralization vs Modularity
**Trade-off:** Centralized state machine (less modular) vs distributed command handling (complex context management)
**Choice:** Centralized - voice UX requires predictable context-aware behavior
**Loss:** Features less modular, harder to add new features without touching parser.py

## Deviations from Spec

### 1. Added Hardware Debug Mode
**Deviation:** Spec didn't include hardware diagnostic functionality
**Addition:** `--debug-hardware` flag that tests each device's API endpoints and validates response formats
**Justification:** Integration with hardware team requires systematic testing and clear error messages

### 2. Enhanced Error Recovery
**Deviation:** Spec assumed devices always available
**Addition:** Graceful degradation when devices offline, automatic retry logic, device health monitoring
**Justification:** Demo environments are unreliable - system must continue functioning when some devices fail

### 3. Config File Flexibility
**Deviation:** Spec showed fixed config structure
**Addition:** Allow command line overrides for most config values, especially audio source and phone IP
**Justification:** Different team members and demo scenarios need different configurations

## Integration Notes

### For Hardware Team

**Critical: ESP32 devices MUST implement these exact API endpoints:**

#### Light (iris-light.local)
```
GET /on      → {"status": "on"}
GET /off     → {"status": "off"}  
GET /status  → {"status": "on"} or {"status": "off"}
```

#### Fan (iris-fan.local)
```
GET /on      → {"status": "on", "speed": "high"}
GET /off     → {"status": "off", "speed": "off"}
GET /low     → {"status": "on", "speed": "low"}
GET /high    → {"status": "on", "speed": "high"}
```

#### Motion Sensor (iris-motion.local)
```
GET /on      → {"alerts": "enabled"}
GET /off     → {"alerts": "disabled"}
Must POST to http://<laptop-ip>:5000/motion when triggered
```

#### Distance Sensor (iris-distance.local)  
```
GET /distance → {"distance_cm": 47}
```

**mDNS Setup Required:**
```cpp
#include <ESPmDNS.h>
MDNS.begin("iris-light");  // or iris-fan, iris-motion, etc.
MDNS.addService("_iris-iot", "_tcp", 80);
```

### For Pi Setup
1. Run `pi/setup.sh` to install dependencies and configure mDNS
2. Start `pi/advertise.py` to announce iris-pi.local
3. SSH keys must be configured for passwordless access from laptop

## Known Limitations

1. **mDNS Reliability:** Some networks block mDNS - fallback to manual IP entry required
2. **IP Webcam Latency:** Audio streaming over WiFi adds ~200-500ms latency vs direct mic
3. **SSH Connection Stability:** Network issues can drop SSH connection, requires reconnection
4. **Speech Recognition Accuracy:** Depends on Google API availability and ambient noise
5. **Distance Polling Overhead:** 200ms polling interval may cause network congestion with poor WiFi
6. **Single Device Limitation:** Cannot connect to multiple instances of same device type (e.g., two lights)

## Testing Instructions

### Phase 1: Mock Mode (No Hardware)
```bash
python main.py --mock
```
**Expected:** Keyboard input prompts, ASCII terminal display, fake device responses
**Validates:** State machine, command parsing, display rendering, core logic

### Phase 2: Laptop Audio (No Phone)  
```bash
python main.py --audio-source laptop
```
**Expected:** Speech recognition from laptop mic, terminal display (no Pi)
**Validates:** Audio capture, speech-to-text, voice command processing

### Phase 3: Pi Display (Laptop + Pi)
```bash
python main.py --audio-source laptop
```
**Prereq:** Pi running advertise.py and accessible via SSH
**Expected:** OLED display updates, persistent SSH connection
**Validates:** Device discovery, SSH connection, display protocol

### Phase 4: IoT Devices (Laptop + Pi + ESP32s)
```bash
python main.py --audio-source laptop
```
**Prereq:** ESP32 devices advertising via mDNS and responding to HTTP
**Expected:** Device discovery finds ESP32s, device control commands work
**Validates:** mDNS discovery, HTTP device communication, IoT integration

### Phase 5: IP Webcam (Full System)
```bash
python main.py --audio-source ipwebcam --phone-ip 192.168.43.1
```  
**Prereq:** Android phone with IP Webcam app running
**Expected:** Audio from phone, full system integration
**Validates:** IP Webcam audio streaming, complete system operation

### Hardware Debug Mode
```bash
python main.py --debug-hardware
```
**Expected:** Device scanning, API testing, response validation, fix instructions
**Validates:** Hardware integration, API contract compliance

## Build Progress

- [x] UNDERSTAND.md created and initial documentation
- [x] core/discovery.py - Dynamic device discovery with mDNS + UDP fallback
- [x] core/display.py - Persistent SSH connection with mock mode
- [x] core/audio.py - Pluggable audio sources (mock, laptop mic, IP Webcam)
- [x] core/parser.py - State machine implementation with timeout handling
- [x] Features implementation (todo, weather, translation)
- [x] core/iot.py - IoT client using device registry (no hardcoded IPs)
- [x] core/server.py - Flask server with thread-safe interrupt handling  
- [x] pi/advertise.py - mDNS advertisement for Pi discovery
- [x] pi/display_server.py - OLED driver updated for pipe-delimited input
- [x] main.py - Complete main orchestrator with async architecture
- [x] config.yaml - Configuration updated for discovery-based system
- [x] core/debug.py - Hardware diagnostic mode for integration testing
- [x] Test suite - Comprehensive tests for all major components
- [x] run_tests.py - Test runner with coverage reporting

## Issues Encountered

### 1. File Write Dependency Error
**Issue:** Encountered "File has not been read yet" error when trying to write .env.example
**Resolution:** Required reading existing file first before overwriting with Edit tool
**Impact:** Added Read tool call before Edit operations on existing files

### 2. Import Dependencies Management  
**Issue:** Optional dependencies (paramiko, zeroconf, deepl) need graceful handling when not installed
**Resolution:** Added try/except blocks with fallback to mock mode for missing dependencies
**Impact:** System functions in degraded mode rather than crashing when dependencies missing

### 3. State Machine vs Feature Architecture
**Issue:** Existing codebase used feature-based architecture, spec required state machine approach
**Resolution:** Completely replaced main.py and restructured command flow around parser.py
**Impact:** Better adherence to spec but required significant refactoring

## Performance Notes

*Will be updated with actual measurements during testing*

## Team Communication Log

*Will track questions/decisions made with hardware team*

## Testing Summary

### Test Coverage
- **test_parser.py**: 32 test methods covering complete state machine behavior
- **test_discovery.py**: 18 test methods for device discovery and registry management  
- **test_iot.py**: 25 test methods for IoT client communication and mock responses
- **test_features.py**: 20 test methods for todo, weather, and translation features
- **conftest.py**: Shared fixtures and test configuration
- **run_tests.py**: Test runner with coverage reporting and selective execution

### Running Tests
```bash
# Run all tests
./run_tests.py

# Run with coverage
./run_tests.py --coverage

# Run specific modules
./run_tests.py --parser    # State machine tests
./run_tests.py --iot       # IoT client tests
./run_tests.py --features  # Feature module tests
```

## Final System Status

**✅ IMPLEMENTATION COMPLETE**

The Iris Smart Glasses software system has been fully implemented according to specification:

1. **Architecture**: State machine-based voice command processing ✅
2. **Discovery**: Dynamic mDNS device discovery (no hardcoded IPs) ✅
3. **Audio**: Pluggable sources (laptop mic, IP Webcam, mock) ✅  
4. **Display**: Persistent SSH connection to Pi Zero W ✅
5. **IoT**: HTTP client with device registry integration ✅
6. **Interrupts**: Thread-safe motion alert handling ✅
7. **Mock Mode**: Complete system simulation for testing ✅
8. **Diagnostics**: Hardware integration testing mode ✅
9. **Tests**: Comprehensive test coverage across all modules ✅

**Ready for hardware integration and demo deployment.**

---

**Last Updated:** 2026-01-29 - Implementation completed with full test suite