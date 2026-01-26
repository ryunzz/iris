# Iris Smart Glasses

AI-powered smart glasses POC using Pi Zero W + OLED display. This is a TAMU Hacks hardware track project.

## Overview

Smart glasses that use your phone as eyes, ears, and mouth while a LT acts as the brain and a Pi Zero W drives a tiny OLED display.

## Architecture

```
              Phone (Galaxy S22+ running IP Webcam)
             ┌─────────────────────────────────────┐
             │                                     │
             │  👁️ Camera ──── video stream ──────┼──────▶ ┌────────────┐
             │                                     │        │            │
             │  👂 Mic ──────── audio stream ─────┼──────▶ │      LT     │
             │                                     │        │   (brain)  │
             │  👄 Speaker ◀─── TTS audio ────────┼─────── │            │
             │                                     │        └─────┬──────┘
             └─────────────────────────────────────┘              │
                                                                  │ SSH 
                                                                  ▼
                                                           ┌─────────────┐
                                                           │  Pi Zero W  │
                                                           │   (bridge)  │
                                                           └──────┬──────┘
                                                                  │ I2C
                                                                  ▼
                                                           ┌─────────────┐
                                                           │    OLED     │
                                                           │   128x64    │
                                                           └─────────────┘
```

## Component Roles

| Component | Role | What it does |
|-----------|------|--------------|
| **Phone (Galaxy S22+)** | Eyes, ears, mouth | Camera captures video. Mic captures voice. Speaker plays TTS audio output. |
| **Pi Zero W** | Dumb display terminal | Receives text strings from LT. Draws them on OLED. Zero logic. |


## Hardware Requirements

- **OLED:** Elegoo 0.96" 128x64, SSD1306 driver, I2C (4 pins), address 0x3c
- **Pi:** Raspberry Pi Zero W
- **Phone:** Galaxy S22+ running IP Webcam app (Thyoni Tech)
- **Network:** Phone WiFi hotspot connects LT + Pi

## Project Structure

```
iris-glasses/
├── .gitignore
├── .env.example                 # API keys and config
├── README.md
├── requirements.txt             # LT dependencies
├── config.yaml                  # Configuration file
├── main.py                      # Entry point (runs on LT)
│
├── core/                        # Core infrastructure (LT)
│   ├── __init__.py
│   ├── feature_base.py          # Abstract base class for features
│   ├── display.py               # Sends text to Pi over SSH
│   ├── audio.py                 # Audio I/O with phone via IP Webcam
│   ├── camera.py                # Video capture from phone
│   └── voice_trigger.py         # Wake word + command parsing
│
├── features/                    # Modular features (LT)
│   ├── __init__.py
│   ├── todo/                    # Voice-controlled todo list
│   ├── directions/              # Turn-by-turn navigation
│   └── translation/             # Live text translation via OCR
│
└── pi/                          # 0w
    ├── display_server.py        # Dumb terminal for OLED display
    ├── requirements.txt         # Pi dependencies
    └── setup.sh                 # Pi setup script
```

## Setup Instructions

### 1. LT Setup

```bash
# Clone the repository
git clone <repository-url>
cd iris-glasses

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your IP Webcam URL and API keys
```

### 2. Pi Zero W Setup

```bash
# On the Pi, run the setup script
cd ~
git clone <repository-url> iris
cd iris
chmod +x pi/setup.sh
./pi/setup.sh

# Follow the script's instructions to reboot and test
```

### 3. Phone Setup

1. Install **IP Webcam** app by Thyoni Tech from Google Play Store
2. Open the app and start the server
3. Note the IP address shown (e.g., http://192.168.43.1:8080)
4. Enable WiFi hotspot on your phone
5. Connect both LT and Pi to the phone's hotspot

### 4. Configuration

Edit `.env` on the LT:
```bash
# Update with your phone's IP Webcam URL
IP_WEBCAM_URL=http://192.168.43.1:8080

# Update Pi hostname if needed
PI_HOST=raspberrypi.local

# Add API keys for features
GOOGLE_MAPS_API_KEY=your_key_here
DEEPL_API_KEY=your_key_here
OPENAI_API_KEY=your_key_here
```

## Running the System

1. **Start the phone**: Open IP Webcam app and start server
2. **Start the Pi**: SSH into Pi and run display server (or it can be auto-started)
3. **Start the LT brain**: 
   ```bash
   cd iris-glasses
   source venv/bin/activate
   python main.py
   ```

## Voice Commands

### Global Commands
- **"Hey Iris, activate [feature]"** — Activate a specific feature
- **"Hey Iris, stop"** — Stop current feature and return to idle

### Features
- **todo** — Voice-controlled todo list
- **directions** — Turn-by-turn navigation  
- **translation** — Live text translation via camera OCR

See individual feature README files in `features/` for specific commands.

## Display Constraints

The 0.96" 128x64 OLED is tiny:
- **Max 4 lines** of text
- **Max 21 characters** per line
- Uses symbols to save space: ✓ ○ → ↑ ↓ ← ● ■

## Network Topology

```
Phone (Galaxy S22+) hosting WiFi hotspot
   │
   ├─── LT connects to hotspot
   │    └─── Runs main.py (brain)
   │
   └─── Pi Zero W connects to hotspot  
        └─── Runs display_server.py (display only)

LT SSHs to Pi to send display commands
```

## Development

### Adding New Features

1. Create a new directory in `features/`
2. Add `__init__.py` and `README.md`
3. Create `feature.py` inheriting from `FeatureBase`
4. Register in `main.py`

### Code Style
- Use type hints on all function signatures
- Include docstrings for classes and public methods  
- Use `logging` module, not print statements
- Handle errors gracefully with try/except
- Keep functions focused and short

## Troubleshooting

### Connection Issues
- Verify all devices are on the same WiFi network (phone's hotspot)
- Check IP Webcam URL in `.env` matches what's shown in the app
- Test Pi SSH connection: `ssh pi@raspberrypi.local`
- Use `i2cdetect -y 1` on Pi to verify OLED at address 0x3c

### Display Issues
- Ensure I2C is enabled on Pi (`sudo raspi-config`)
- Check OLED wiring: VCC, GND, SDA (pin 3), SCL (pin 5)
- Test display server: `echo "Test|Display|Working|OK" | python pi/display_server.py`

## Team Credits

- **Hardware**: Pi Zero W + OLED display integration
- **Software**: Python application architecture
- **Mobile**: IP Webcam integration for camera/audio
- **AI**: Voice recognition and command processing

Built for TAMU Hacks Hardware Track 2026
