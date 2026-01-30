# Arduino Nano OLED Setup for Iris Smart Glasses

This guide will help you set up your Arduino Nano with OLED display to work with the Iris smart glasses software.

## Hardware Requirements

### Components Needed:
- **Arduino Nano** (or compatible)
- **128x64 OLED Display** (SSD1306 controller)
- **USB Cable** (to connect Nano to laptop)
- **Jumper Wires** (if OLED isn't pre-wired)

### OLED Display Wiring:
```
OLED Display    Arduino Nano
============    ============
VCC      →      3.3V or 5V
GND      →      GND
SDA      →      A4 (SDA)
SCL      →      A5 (SCL)
```

## Software Setup

### Step 1: Install Arduino IDE
1. Download Arduino IDE from https://arduino.cc
2. Install and open Arduino IDE

### Step 2: Install Required Libraries
In Arduino IDE:
1. Go to **Tools > Manage Libraries**
2. Search for and install:
   - **"Adafruit SSD1306"** by Adafruit
   - **"Adafruit GFX Library"** by Adafruit

### Step 3: Upload the Sketch
1. Open the file: `arduino_nano_oled_display.ino`
2. Select your board: **Tools > Board > Arduino Nano**
3. Select processor: **Tools > Processor > ATmega328P (Old Bootloader)** 
   - Try "ATmega328P" if Old Bootloader doesn't work
4. Select port: **Tools > Port > /dev/ttyUSB0** (or similar)
5. Click **Upload** button (→)

### Step 4: Verify Upload
1. Open **Tools > Serial Monitor**
2. Set baud rate to **9600**
3. You should see: `NANO_DISPLAY_READY`
4. OLED should show "Iris Smart Glasses Nano Display Ready"

## Testing with Iris Software

### Basic Test (Mock Mode):
```bash
cd ~/path/to/iris
python3 main.py --display nano --mock
```

### Full Test (with Voice):
```bash
python3 main.py --display nano --audio-source laptop
```

### Manual Port Selection:
If auto-detection fails:
```bash
python3 main.py --display nano --serial-port /dev/ttyUSB0 --audio-source laptop
```

## Expected Behavior

### Startup:
1. **Arduino**: OLED shows "Iris Smart Glasses..." 
2. **Python**: Logs "Display: Arduino Nano on /dev/ttyUSB0"
3. **OLED**: Shows current time and weather

### Voice Commands:
1. Say: **"hey iris"**
2. **OLED** shows:
   ```
   MAIN MENU
   > 1. Todo List
     2. Translation
     3. Connect
   ```

### Menu Navigation:
- Say **"iris one"** → Todo menu
- Say **"iris two"** → Translation mode  
- Say **"iris three"** → Device list
- Say **"iris back"** → Previous menu

## Troubleshooting

### OLED Not Working:
- **Check wiring** (especially SDA/SCL on A4/A5)
- **Try different I2C address**: Change `0x3C` to `0x3D` in sketch
- **Check power**: OLED needs 3.3V or 5V
- **Test with I2C scanner**: Upload I2C scanner sketch first

### Arduino Not Detected:
- **Check USB cable** (some cables are power-only)
- **Try different USB port**
- **Install drivers**: Windows may need CH340 or FTDI drivers
- **Check board/processor settings** in Arduino IDE

### Python Connection Issues:
```bash
# Check available ports
ls /dev/tty* | grep -E "(USB|ACM)"

# Check permissions (Linux)
sudo usermod -a -G dialout $USER
# Then logout/login

# Test manual port
python3 main.py --display nano --serial-port /dev/ttyUSB0
```

### Serial Communication Issues:
- **Verify baud rate**: Must be 9600 on both sides
- **Check serial monitor**: Should see "DISPLAYED: ..." messages
- **Reset Arduino**: Press reset button or unplug/replug USB

## Data Format

The Python software sends display data in this format:
```
"line1|line2|line3|line4\n"
```

Examples:
```
"MAIN MENU|> 1. Todo List|  2. Translation|  3. Connect\n"
"TODO LIST|○  Buy groceries|○  Walk dog|○  Study for exam\n"
"12:34|22°C|Sunny|01/29\n"
```

## Hardware Notes

### OLED Display Types:
- **0.96" 128x64** → Most common, works perfectly
- **1.3" 128x64** → Also works, slightly larger
- **Different controllers** → May need different library

### Arduino Variants:
- **Arduino Nano** → Recommended
- **Arduino Uno** → Works but larger
- **ESP32/ESP8266** → Use HTTP display mode instead

### Power Considerations:
- **USB powered** → No external power needed
- **3.3V OLED** → More reliable than 5V versions
- **Current draw** → ~20-30mA for OLED + ~15mA for Nano

## Success Checklist

✅ **OLED shows startup message**  
✅ **Serial monitor shows "NANO_DISPLAY_READY"**  
✅ **Python logs "Display: Arduino Nano on /dev/ttyXXX"**  
✅ **Voice command "hey iris" changes OLED display**  
✅ **Menu navigation works with voice commands**  

## Next Steps

Once your nano display is working:

1. **Test all features**: Todo lists, translation, device control
2. **Adjust display brightness**: Add potentiometer if needed
3. **Mount in glasses frame**: Secure wiring and components
4. **Configure audio source**: Set up laptop mic or phone input
5. **Add IoT devices**: Set up smart lights, fans, sensors

Your smart glasses display is now ready! 🤓