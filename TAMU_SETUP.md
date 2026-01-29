# TEXAS TEAM SETUP GUIDE

## Quick Start (5 minutes per device)

### Prerequisites
- 4x ESP32 boards (flashed and working)
- Phone with hotspot capability
- Laptop with Python installed

---

## STEP 1: Set Up Phone Hotspot

Turn on your phone hotspot and note:
```
Hotspot Name: ____________________
Password:     ____________________
```

**All devices AND your laptop must connect to this same hotspot.**

---

## STEP 2: Update WiFi Credentials in Each ESP32

For **EACH** ESP32, change these lines to match your hotspot:

```cpp
const char* ssid = "YOUR_HOTSPOT_NAME";
const char* password = "YOUR_HOTSPOT_PASSWORD";
```

Then re-upload to the ESP32.

---

## STEP 3: Add mDNS to Each ESP32

Make sure each ESP32 has this code in `setup()` after WiFi connects:

### Light
```cpp
#include <ESPmDNS.h>

// Add after WiFi.begin() and connection loop:
if (MDNS.begin("iris-light")) {
  Serial.println("mDNS: iris-light.local");
}
```

### Fan
```cpp
if (MDNS.begin("iris-fan")) {
  Serial.println("mDNS: iris-fan.local");
}
```

### Motion Sensor
```cpp
if (MDNS.begin("iris-motion")) {
  Serial.println("mDNS: iris-motion.local");
}
```

### Distance Sensor
```cpp
if (MDNS.begin("iris-distance")) {
  Serial.println("mDNS: iris-distance.local");
}
```

---

## STEP 4: Verify API Endpoints

Each device MUST have these exact HTTP endpoints:

### Light (iris-light.local)
| Endpoint | Response |
|----------|----------|
| `GET /on` | `{"status":"on"}` |
| `GET /off` | `{"status":"off"}` |
| `GET /status` | `{"status":"on"}` or `{"status":"off"}` |
| `GET /health` | `{"device":"iris-light","ok":true}` |

### Fan (iris-fan.local)
| Endpoint | Response |
|----------|----------|
| `GET /on` | `{"status":"on","speed":"high"}` |
| `GET /off` | `{"status":"off","speed":"off"}` |
| `GET /low` | `{"status":"on","speed":"low"}` |
| `GET /high` | `{"status":"on","speed":"high"}` |
| `GET /status` | `{"status":"on","speed":"low"}` |

### Motion Sensor (iris-motion.local)
| Endpoint | Response |
|----------|----------|
| `GET /on` | `{"alerts":"enabled"}` |
| `GET /off` | `{"alerts":"disabled"}` |
| `GET /status` | `{"alerts":"enabled"}` or `{"alerts":"disabled"}` |

**IMPORTANT:** When motion is detected, POST to laptop:
```cpp
HTTPClient http;
http.begin("http://LAPTOP_IP:5001/motion");
http.POST("{}");
```

### Distance Sensor (iris-distance.local)
| Endpoint | Response |
|----------|----------|
| `GET /distance` | `{"distance_cm":47}` |
| `GET /health` | `{"device":"iris-distance","ok":true}` |

---

## STEP 5: Power On and Get IP Addresses

1. Power on each ESP32
2. Open Serial Monitor (115200 baud)
3. Note the IP address printed

Fill in below:

```
┌─────────────────────────────────────────────────────────┐
│ DEVICE IP ADDRESSES                                     │
├─────────────────────────────────────────────────────────┤
│                                                         │
│ Light IP:    ___.___.___.___                            │
│ Fan IP:      ___.___.___.___                            │
│ Motion IP:   ___.___.___.___                            │
│ Distance IP: ___.___.___.___                            │
│ Laptop IP:   ___.___.___.___                            │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

To find laptop IP:
- **Mac:** System Settings → Network → Wi-Fi → Details → IP Address
- **Windows:** `ipconfig` in Command Prompt

---

## STEP 6: Update config.yaml (if mDNS doesn't work)

If devices aren't discovered automatically, add manual IPs to `config.yaml`:

```yaml
# Manual device IPs (add at bottom of config.yaml)
manual_devices:
  light:
    ip: "192.168.x.x"  # Your light IP
    name: "Smart Light"
  fan:
    ip: "192.168.x.x"  # Your fan IP
    name: "Smart Fan"
  motion:
    ip: "192.168.x.x"  # Your motion sensor IP
    name: "Motion Sensor"
  distance:
    ip: "192.168.x.x"  # Your distance sensor IP
    name: "Distance Sensor"
```

---

## STEP 7: Run the Glasses Software

```bash
cd iris
source venv/bin/activate
python main.py --audio-source laptop --display terminal
```

Then say:
1. "Hey Iris"
2. "Connect"
3. "Light" (or "one")
4. "On"

Your light should turn on!

---

## Troubleshooting

### "No devices found"
- Check all devices are on same hotspot
- Check Serial Monitor for IP addresses
- Try manual IPs in config.yaml

### "Connection refused"
- Device might have wrong IP
- Check device is powered on
- Ping the device: `ping 192.168.x.x`

### "Command not recognized"
- Speak clearly and slowly
- Try typing command instead to test
- Check you're in the right menu state

### Motion sensor not triggering
- Make sure LAPTOP_IP is correct in motion sensor code
- Check laptop firewall isn't blocking port 5001

---

## Quick Test (without voice)

Test each device manually in browser:

```
http://LIGHT_IP/on      → Should turn on light
http://LIGHT_IP/off     → Should turn off light
http://FAN_IP/high      → Should turn fan on high
http://DISTANCE_IP/distance → Should show distance reading
```

---

## ESP32 Code Templates

If your code doesn't match the API format above, here are templates:

### Light Template
See: `hardware/smart-light/smart-light.ino`

### Fan Template  
See: `hardware/smart-fan/smart-fan.ino`

### Motion Template
See: `hardware/motion-sensor/motion-sensor.ino`

### Distance Template
See: `hardware/distance-sensor/distance-sensor.ino`

---

## Questions?

Contact the team (leigt js my Ryan Ni LOL) or check UNDERSTAND.md for architecture details.