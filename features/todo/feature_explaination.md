# Iris Smart Glasses - Technical Architecture Documentation

**Version:** 1.0  
**Last Updated:** January 2026  
**Audience:** AI Coding Agents & Technical Contributors

---

## 1. Architecture Overview

### System Topology

```
┌─────────────────────────────────────────────────────────────┐
│                    LENOVO TAB (LT) - "Brain"                 │
│                                                               │
│  ┌──────────────┐                                            │
│  │   main.py    │  ← Entry point, orchestrates everything    │
│  └──────┬───────┘                                            │
│         │                                                     │
│         ├─────────┬──────────┬──────────┬──────────┐        │
│         ▼         ▼          ▼          ▼          ▼         │
│    ┌────────┐ ┌──────┐  ┌────────┐ ┌────────┐ ┌──────────┐ │
│    │display │ │audio │  │camera  │ │voice   │ │features/ │ │
│    │.py     │ │.py   │  │.py     │ │trigger │ │   (N)    │ │
│    └────┬───┘ └───┬──┘  └───┬────┘ │.py     │ └──────────┘ │
│         │         │         │      └────────┘               │
└─────────┼─────────┼─────────┼──────────────────────────────┘
          │         │         │
          │         └─────────┴─────────┐
          │                             │
          ▼                             ▼
    ┌──────────┐              ┌──────────────────┐
    │ Pi Zero W│              │  Android Phone   │
    │  (OLED)  │              │  (Camera/Audio)  │
    └──────────┘              └──────────────────┘
       SSH stdin                 IP Webcam HTTP
```

### Three-Tier Architecture

**Tier 1: Hardware I/O (Dumb Terminals)**
- **Pi Zero W**: OLED display only - receives formatted text via SSH stdin
- **Android Phone**: Camera/microphone/speaker via IP Webcam app HTTP endpoints

**Tier 2: Core Managers (Hardware Abstraction)**
- `display.py` - SSH communication to Pi, formats text for OLED constraints
- `audio.py` - HTTP requests to phone for speech-to-text and text-to-speech
- `camera.py` - HTTP requests to phone for image capture
- `voice_trigger.py` - Wake word detection and command parsing

**Tier 3: Features (Business Logic)**
- Plugin architecture where each feature inherits from `FeatureBase`
- Features receive hardware managers and implement activation/voice/rendering logic
- Features are stateful and lifecycle-managed by main.py

### Key Design Principles

1. **Separation of Concerns**: Hardware I/O is completely isolated from business logic
2. **Dumb Terminals**: Pi and phone do NO processing - they are pure I/O devices
3. **Centralized Intelligence**: ALL logic runs on the LT (main.py orchestrates)
4. **Hot-Swappable Features**: Features can be activated/deactivated without system restart
5. **Fail-Safe Operation**: System continues if individual components fail

---

## 2. Module Breakdown

### 2.1 Core Module: `main.py`

**Purpose:** Application orchestrator - the "brain" that connects everything.

**Responsibilities:**
1. Load configuration from `config.yaml` and environment variables
2. Initialize all core managers (display, audio, camera, voice_trigger)
3. Register features into a dictionary: `{"feature_name": FeatureInstance}`
4. Test hardware connections at startup
5. Run main event loop that:
   - Listens for voice commands via VoiceTrigger
   - Routes commands to appropriate feature or handles activation/deactivation
   - Updates active feature (process_frame + render)
   - Handles errors and keeps system running

**Critical State:**
```python
current_feature: Optional[FeatureBase] = None  # The ONE active feature
features: Dict[str, FeatureBase] = {...}       # Registry of all features
```

**Command Flow:**
```
Voice Input → VoiceTrigger.listen_for_command()
            → VoiceTrigger.parse_command() 
            → Returns: {"action": str, "target": str, "text": str}

Action Types:
- "activate" → target = feature name → Deactivate current, activate target
- "stop"     → Deactivate current feature, set current_feature = None
- "passthrough" → Send text to current_feature.process_voice(text)
- "unknown" → Ignored
```

**Feature Lifecycle Management:**
```python
# Activation sequence
if current_feature:
    current_feature.deactivate()  # Clean up old feature

current_feature = features[target_name]
current_feature.activate()  # Initialize new feature

# Update loop (runs continuously while feature active)
if current_feature.is_active:
    frame = camera.get_snapshot()  # Optional
    current_feature.process_frame(frame)
    current_feature.render()
```

**Error Handling Philosophy:**
- Errors in main loop are logged but DO NOT crash the system
- Individual feature errors are caught and passed to feature.handle_error()
- Hardware connection failures are logged as warnings - system continues
- Fatal errors (config missing, etc.) exit immediately

---

### 2.2 Core Module: `core/display.py` (DisplayManager)

**Purpose:** Abstract SSH communication to Pi Zero W display server.

**Key Insight:** Display server is a DUMB TERMINAL - it has NO logic. DisplayManager formats text and pipes it via SSH stdin.

**Initialization:**
```python
DisplayManager(
    pi_host: str,           # Pi IP address
    pi_user: str,           # SSH username (default "pi")
    display_server_path: str # Path to display_server.py on Pi
)
```

**Connection Process:**
```python
def connect() -> bool:
    # Opens SSH connection with persistent stdin pipe:
    ssh_process = Popen([
        "ssh", f"{pi_user}@{pi_host}",
        f"cd ~/iris && source venv/bin/activate && python {display_server_path}"
    ], stdin=PIPE, stdout=PIPE, stderr=PIPE)
    
    # Waits 2 seconds for display_server to initialize
    # Returns True if process still running, False if died
```

**Display Protocol:**
```
Format: "Line1|Line2|Line3|Line4\n"
        
Rules:
- Pipe (|) delimiter between lines
- Max 4 lines
- Max 21 characters per line
- Newline (\n) terminates command
- Empty string ("") clears display
```

**Public Methods:**
```python
show_lines(lines: List[str]) -> bool
    # Sends up to 4 lines via SSH stdin
    # Auto-truncates lines > 21 chars with ellipsis
    # Returns True if sent, False if not connected

show_text(text: str) -> bool
    # Word-wraps text to fit 4 lines × 21 chars
    # Sends via show_lines()

clear() -> bool
    # Sends empty string to clear display

show_idle_screen() -> bool
    # Displays default "Ready for commands" screen
```

**Connection State:**
```python
self.connected: bool       # Are we connected?
self.ssh_process: Popen    # SSH process handle
```

**Critical Implementation Detail:**
The SSH process remains open for the entire session. Commands are sent by writing to `ssh_process.stdin` and flushing. If the process dies (`poll() != None`), `connected` is set to False and all commands fail gracefully.

---

### 2.3 Core Module: `core/audio.py` (AudioManager)

**Purpose:** Interface with phone microphone and speaker via IP Webcam HTTP endpoints.

**Initialization:**
```python
AudioManager(config: dict)
# config keys:
#   'ip_webcam_url': Base URL (e.g., "http://192.168.43.1:8080")
#   'audio_path': Audio capture endpoint (default "/audio.wav")
#   'tts_path': TTS upload endpoint (default "/audio.wav")
```

**Architecture:**
```
Phone (IP Webcam App)
  ↓ HTTP GET /audio.wav
LT captures audio bytes
  ↓ speech_recognition library
Transcribed text
  ↓ pyttsx3 or send to phone
Audio feedback
```

**Public Methods:**
```python
listen(timeout: int = 5) -> Optional[str]
    # 1. GET {base_url}/audio.wav → audio bytes
    # 2. speech_recognition.recognize_google(audio)
    # 3. Returns transcript.strip().lower() or None

speak(text: str) -> bool
    # 1. pyttsx3.save_to_file() → temp WAV file
    # 2. POST to {base_url}/audio.wav (if supported)
    # 3. Fallback: play locally on LT if upload fails
    # Returns True if spoken, False on error

test_connection() -> bool
    # GET /audio.wav with 5sec timeout
    # Returns True if 200 OK, False otherwise
```

**Speech Recognition Pipeline:**
```python
# Raw audio → Google Web Speech API → Text
1. Capture audio from phone microphone
2. Adjust for ambient noise (0.5s)
3. Send to Google for recognition
4. Return lowercase transcript
```

**TTS Pipeline:**
```python
# Text → WAV file → Phone speaker
1. Generate WAV with pyttsx3 (rate=150, volume=0.9)
2. Try uploading to phone via POST
3. If fails: play locally as fallback
4. Clean up temp file
```

**Error Handling:**
- Network failures → Returns None/False, logs error
- Speech not recognized → Returns None
- TTS failure → Attempts local fallback, returns False if both fail

---

### 2.4 Core Module: `core/camera.py` (CameraManager)

**Purpose:** Capture images from phone camera via IP Webcam HTTP endpoints.

**Initialization:**
```python
CameraManager(config: dict)
# config keys:
#   'ip_webcam_url': Base URL
#   'snapshot_path': Snapshot endpoint (default "/shot.jpg")
#   'video_path': Video stream endpoint (default "/video")
```

**Public Methods:**
```python
get_snapshot() -> Optional[bytes]
    # GET {base_url}/shot.jpg → JPEG bytes
    # Returns raw image data or None

get_frame_cv2() -> Optional[np.ndarray]
    # get_snapshot() → JPEG bytes
    # cv2.imdecode() → BGR numpy array
    # Returns OpenCV-compatible image

save_snapshot(filename: str) -> bool
    # get_snapshot() → save to file
    # Returns True if saved

test_connection() -> bool
    # GET /shot.jpg with 5sec timeout
    # Verifies content-type is image/*

get_camera_info() -> dict
    # Returns: {'connected': bool, 'resolution': str, 'format': str}
    # Attempts to determine camera capabilities
```

**Request Session:**
Uses `requests.Session()` for connection reuse across multiple snapshot requests (more efficient than creating new connections each time).

**Image Flow:**
```
Phone Camera → IP Webcam App → HTTP JPEG
            ↓ GET /shot.jpg
        JPEG bytes (LT memory)
            ↓ cv2.imdecode()
        NumPy array (for processing)
```

**Usage Pattern:**
Features that need camera input should call `get_frame_cv2()` in their `process_frame()` method. The frame is passed by main.py in the update loop.

---

### 2.5 Core Module: `core/voice_trigger.py` (VoiceTrigger)

**Purpose:** Wake word detection and command parsing - the "ears" of the system.

**Initialization:**
```python
VoiceTrigger(
    audio_manager: AudioManager,
    wake_word: str = "hey iris"
)
```

**Two-Stage Processing:**

**Stage 1: Wake Word Detection**
```python
listen_for_command(timeout: int = 10) -> Optional[str]
    # 1. audio_manager.listen(timeout)
    # 2. Check if wake_word in transcript
    # 3. Return full transcript if wake word found, else None
```

**Stage 2: Command Parsing**
```python
parse_command(raw_transcript: str) -> Dict[str, Any]
    # Input: "hey iris activate weather"
    # Output: {"action": "activate", "target": "weather", "text": None}
    
    # Input: "hey iris add buy milk"  (while todo active)
    # Output: {"action": "passthrough", "target": None, "text": "add buy milk"}
```

**Command Grammar:**
```
<wake_word> := "hey iris"
<command> := <activate> | <stop> | <passthrough>

<activate> := "activate" <feature_name>
<stop> := "stop" | "exit" | "quit" | "deactivate"
<passthrough> := <any_text>  (sent to active feature)

Examples:
"hey iris activate todo"        → action=activate, target=todo
"hey iris stop"                 → action=stop
"hey iris add buy groceries"    → action=passthrough, text="add buy groceries"
```

**Parsing Algorithm:**
```python
1. Remove wake word from beginning of transcript
2. Extract command_part (everything after wake word)
3. Check regex: r'^activate\s+(\w+)' 
   → If match: action=activate, target=feature_name
4. Check if command_part in ['stop', 'exit', 'quit', 'deactivate']
   → If match: action=stop
5. Else: action=passthrough, text=command_part
```

**Wake Word Matching:**
- Simple substring search: `wake_word in normalized_transcript`
- Case-insensitive
- Works anywhere in transcript (beginning, middle, end)

**Critical: No Memory**
VoiceTrigger has NO state between calls. It doesn't know which feature is active. The main.py loop maintains that state and routes accordingly.

---

### 2.6 Core Module: `core/feature_base.py` (FeatureBase)

**Purpose:** Abstract base class defining the interface ALL features must implement.

**Design Pattern:** Template Method pattern - defines lifecycle hooks that subclasses override.

**Class Variables:**
```python
name: str = "unnamed"  # MUST be overridden - used for voice activation
```

**Constructor Signature (ALL features must match):**
```python
def __init__(self, display, audio, camera, config):
    self.display = display      # DisplayManager instance
    self.audio = audio          # AudioManager instance
    self.camera = camera        # CameraManager instance
    self.config = config        # Dict from config.yaml
    self.is_active = False      # Activation state
```

**Abstract Methods (MUST implement):**
```python
@abstractmethod
def activate(self) -> None:
    """
    Called when: User says "hey iris activate {name}"
    
    Responsibilities:
    1. Set self.is_active = True
    2. Initialize any feature-specific state
    3. Call self.render() to show initial display
    4. Optionally: self.speak_feedback() for audio confirmation
    """
    pass

@abstractmethod
def deactivate(self) -> None:
    """
    Called when: User says "hey iris stop" OR another feature activates
    
    Responsibilities:
    1. Save any state (e.g., to disk)
    2. Set self.is_active = False
    3. Clean up resources
    4. Optionally: self.speak_feedback() for confirmation
    """
    pass

@abstractmethod
def process_voice(self, transcript: str) -> None:
    """
    Called when: User gives command while feature is active
    
    Args:
        transcript: Command text with wake word already removed
                   Example: "add buy milk" (NOT "hey iris add buy milk")
    
    Responsibilities:
    1. Parse the command for feature-specific syntax
    2. Execute the appropriate action
    3. Call self.render() to update display
    4. Optionally: self.speak_feedback() for confirmation
    """
    pass

@abstractmethod
def render(self) -> None:
    """
    Called: 
    - After activate()
    - After process_voice()
    - In main loop update cycle
    
    Responsibilities:
    1. Generate current display state
    2. Call self.display.show_lines() or .show_text()
    3. Handle 4-line × 21-char constraint
    """
    pass
```

**Optional Override:**
```python
def process_frame(self, frame: Optional[bytes]) -> None:
    """
    Called: In main loop if frame capture enabled
    
    Args:
        frame: JPEG image bytes from camera, or None
    
    Default: Does nothing (most features don't need camera)
    
    Override: If feature needs camera input (e.g., translation, object detection)
    """
    pass
```

**Helper Methods (Already Implemented):**
```python
def speak_feedback(self, text: str) -> None:
    # Wrapper around self.audio.speak()
    # Logs error if speech fails but doesn't crash

def handle_error(self, error: Exception, context: str) -> None:
    # Logs error with context
    # Shows error on display (2 lines)
    # Does NOT crash feature

def get_help_text(self) -> str:
    # Returns help text for voice commands
    # Default: basic info, features should override
```

**Context Manager Support:**
```python
with feature:
    # Calls activate() on entry
    # Calls deactivate() on exit
```

---

### 2.7 Pi Module: `pi/display_server.py`

**Purpose:** DUMB TERMINAL - receives formatted text via stdin, displays on OLED. NO LOGIC.

**Critical Design Decision:** This is intentionally stupid. It does ONE thing: text in → pixels out.

**Initialization:**
```python
# SSD1306 OLED via I2C
serial = i2c(port=1, address=0x3C)
device = ssd1306(serial, width=128, height=64)
```

**Main Loop:**
```python
for line in sys.stdin:
    lines = parse_input(line)   # Split on "|"
    display_lines(device, lines) # Draw to OLED
```

**Input Protocol:**
```
Format: "Line1|Line2|Line3|Line4\n"

Examples:
"> O Buy milk|  X Call mom||"  → 4 lines (2 empty)
"Hello|World"                   → 2 lines (+ 2 empty)
""                              → Clear display (4 empty lines)
```

**Display Rendering:**
```python
def display_lines(device, lines):
    with canvas(device) as draw:
        font = ImageFont.load_default()
        for i, line in enumerate(lines[:4]):  # Max 4 lines
            y = i * 16  # 16 pixels per line
            draw.text((0, y), line, font=font, fill=255)
```

**Physical Constraints:**
- **Display:** 128×64 pixels (monochrome)
- **Font:** Default PIL font (~7 pixels wide per char)
- **Lines:** 4 lines × 16 pixels each = 64 pixels
- **Chars:** ~21 chars per line (128px / 7px ≈ 18, with padding = 21)

**Error Handling:**
- Malformed input → Log error, show "Error:" on display
- Display hardware failure → Fatal error, exit
- KeyboardInterrupt → Graceful shutdown

**No Return Communication:**
Display server does NOT send acknowledgments back. It's one-way: LT → Pi.

**Why This Design?**
- **Simplicity:** No network protocols, no state, no coordination
- **Reliability:** Fewer moving parts = fewer failure modes
- **Latency:** SSH stdin is fast (~50ms typical)
- **Isolation:** Display logic separate from business logic

---

## 3. Feature Blueprint

### 3.1 Anatomy of a Standard Feature

**File Structure:**
```
features/
└── <feature_name>/
    ├── __init__.py          # Exports FeatureClass
    ├── feature.py           # Main feature implementation
    ├── README.md            # User-facing documentation
    └── FEATURE_EXPLANATION.md  # Technical documentation
```

**Minimal Feature Implementation:**
```python
# features/myfeature/feature.py
from core.feature_base import FeatureBase
import logging

logger = logging.getLogger(__name__)

class MyFeature(FeatureBase):
    # REQUIRED: Set feature name for voice activation
    name = "myfeature"
    
    def __init__(self, display, audio, camera, config):
        super().__init__(display, audio, camera, config)
        # Initialize feature-specific state here
        self.data = []
        logger.info(f"{self.name} feature initialized")
    
    def activate(self) -> None:
        self.is_active = True
        self.render()
        self.speak_feedback(f"{self.name} activated")
    
    def deactivate(self) -> None:
        self.is_active = False
        # Save state if needed
        self.speak_feedback(f"{self.name} deactivated")
    
    def process_voice(self, transcript: str) -> None:
        command = transcript.lower().strip()
        
        # Parse commands
        if command == "do something":
            self._handle_something()
        else:
            self.speak_feedback("Command not recognized")
    
    def render(self) -> None:
        lines = [
            f"{self.name}",
            "Line 2",
            "Line 3",
            ""
        ]
        self.display.show_lines(lines)
    
    def _handle_something(self):
        # Feature-specific logic
        self.data.append("item")
        self.render()
        self.speak_feedback("Something done")
```

**`__init__.py` Export:**
```python
# features/myfeature/__init__.py
from .feature import MyFeature

__all__ = ['MyFeature']
```

**Registration in `main.py`:**
```python
from features.myfeature import MyFeature

def register_features(display, audio, camera, config):
    features = {}
    features["myfeature"] = MyFeature(display, audio, camera, config)
    return features
```

---

### 3.2 Feature Expectations & Contracts

**What Features Receive (Constructor):**
```python
display: DisplayManager
    # Methods: show_lines(List[str]), show_text(str), clear()
    # Constraint: 4 lines × 21 chars

audio: AudioManager  
    # Methods: speak(str), listen(timeout)
    # Returns: transcript or None

camera: CameraManager
    # Methods: get_snapshot(), get_frame_cv2()
    # Returns: image bytes or NumPy array

config: dict
    # From config.yaml, includes API keys, settings
    # Feature-specific keys accessed via config.get('feature_key')
```

**What Features Must Return:**

**activate()** → None
- Side effects: Set `self.is_active = True`, update display

**deactivate()** → None
- Side effects: Set `self.is_active = False`, save state

**process_voice(transcript)** → None
- Side effects: Execute command, update display, speak feedback

**render()** → None
- Side effects: Update display with current state

**process_frame(frame)** → None
- Side effects: Process image if needed

---

### 3.3 Common Feature Patterns

**Pattern 1: Stateful Feature (Todo List)**
```python
class TodoFeature(FeatureBase):
    def __init__(self, display, audio, camera, config):
        super().__init__(display, audio, camera, config)
        self.todos = []
        self.cursor = 0
        self.load_from_disk()  # Load persistent state
    
    def deactivate(self):
        self.save_to_disk()  # Persist state
        super().deactivate()
```

**Pattern 2: API-Based Feature (Weather)**
```python
class WeatherFeature(FeatureBase):
    def __init__(self, display, audio, camera, config):
        super().__init__(display, audio, camera, config)
        self.api_key = config.get('weather_api_key')
        self.location = None
        self.weather_data = None
    
    def process_voice(self, transcript):
        if "weather in" in transcript:
            location = extract_location(transcript)
            self.weather_data = fetch_weather(location, self.api_key)
            self.render()
```

**Pattern 3: Camera-Using Feature (Translation)**
```python
class TranslationFeature(FeatureBase):
    def process_frame(self, frame):
        if frame and self.is_active:
            text = ocr_extract(frame)  # Extract text from image
            translated = translate(text, self.api_key)
            self.current_translation = translated
            self.render()
```

---

### 3.4 Feature Lifecycle States

```
[NOT CREATED] → __init__() → [CREATED, INACTIVE]
                                     ↓
                              activate()
                                     ↓
                            [ACTIVE, LISTENING]
                                     ↓
                    ┌────────────────┴────────────────┐
                    ↓                                  ↓
            process_voice()                    process_frame()
                    ↓                                  ↓
                render()                          render()
                    ↓                                  ↓
                    └─────────────→ [ACTIVE] ←────────┘
                                        ↓
                                 deactivate()
                                        ↓
                              [CREATED, INACTIVE]
```

**State Transitions:**
- `__init__`: Feature exists but not active
- `activate()`: Feature becomes active, starts responding to commands
- `process_voice()` / `process_frame()`: Handle inputs while active
- `deactivate()`: Feature stops responding, saves state
- Feature remains in memory after deactivation (can be reactivated)

---

## 4. State & Data Flow

### 4.1 Voice Command Flow (Detailed)

**End-to-End Example: "Hey Iris, activate todo"**

```
[1] USER SPEAKS
    ↓
[2] PHONE MICROPHONE (IP Webcam captures audio)
    ↓
[3] main_loop() calls voice_trigger.listen_for_command(timeout=5)
    ↓
[4] VoiceTrigger.listen_for_command()
    ├─ Calls audio_manager.listen(5)
    │  ├─ HTTP GET to phone: /audio.wav
    │  ├─ Receives audio bytes
    │  ├─ speech_recognition.recognize_google(audio)
    │  └─ Returns: "hey iris activate todo"
    └─ Checks: "hey iris" in "hey iris activate todo" → True
       └─ Returns: "hey iris activate todo"
    ↓
[5] main_loop() receives command: "hey iris activate todo"
    ↓
[6] Calls voice_trigger.parse_command("hey iris activate todo")
    ├─ Removes wake word: "activate todo"
    ├─ Regex match: r'^activate\s+(\w+)'
    └─ Returns: {"action": "activate", "target": "todo", "text": None}
    ↓
[7] main_loop() processes action="activate"
    ├─ Checks: "todo" in features dict → True
    ├─ Deactivates current_feature if any
    └─ Sets: current_feature = features["todo"]
    ↓
[8] Calls todo_feature.activate()
    ├─ Sets self.is_active = True
    ├─ Calls self.render()
    │  └─ Generates 4 lines: ["> O Buy milk", "  O Call mom", "", ""]
    │     ├─ Calls self.display.show_lines(lines)
    │     │  └─ Formats: "> O Buy milk|  O Call mom||"
    │     │     └─ Writes to ssh_process.stdin: "> O Buy milk|  O Call mom||\n"
    │     │        └─ SSH pipes to Pi display_server.py stdin
    │     │           └─ Pi parses and displays on OLED
    │     └─ Returns to activate()
    └─ Calls self.speak_feedback("Todo activated")
       └─ Calls self.audio.speak("Todo activated")
          ├─ Generates TTS with pyttsx3
          ├─ HTTP POST to phone (or local fallback)
          └─ Phone plays audio
    ↓
[9] main_loop() continues
    └─ Now current_feature = todo_feature (active)
```

---

### 4.2 Feature Command Flow (Detailed)

**End-to-End Example: "Hey Iris, add buy milk" (while todo active)**

```
[1] USER SPEAKS
    ↓
[2-4] (Same as above: capture, transcribe, parse)
    └─ Returns: {"action": "passthrough", "target": None, "text": "add buy milk"}
    ↓
[5] main_loop() processes action="passthrough"
    ├─ Checks: current_feature is not None → True (todo is active)
    └─ Calls: current_feature.process_voice("add buy milk")
    ↓
[6] TodoFeature.process_voice("add buy milk")
    ├─ Parses: command.startswith("add ") → True
    ├─ Extracts: item_text = "buy milk"
    └─ Calls: self._handle_add("buy milk")
       ├─ Creates: TodoItem(text="buy milk", completed=False)
       ├─ Appends to self.todos list
       ├─ Calls: self.save_todos() → Writes to JSON file
       ├─ Calls: self.render()
       │  └─ Generates new 4 lines with updated list
       │     └─ Updates OLED display (same flow as step 8 above)
       └─ Calls: self.speak_feedback("Added: buy milk")
          └─ Phone speaks confirmation
    ↓
[7] main_loop() continues
    └─ Display now shows new item, audio confirmed action
```

---

### 4.3 Display Update Flow

**From Feature to OLED (Step-by-Step):**

```
[Feature Code]
    lines = ["> O Buy milk", "  O Call mom", "", ""]
    self.display.show_lines(lines)
        ↓
[DisplayManager.show_lines()]
    1. Check: self.connected and self.ssh_process → True
    2. Truncate lines to 21 chars max
    3. Take first 4 lines only
    4. Join with pipe: "> O Buy milk|  O Call mom||"
    5. Add newline: "> O Buy milk|  O Call mom||\n"
    6. Write to self.ssh_process.stdin
    7. Flush stdin buffer
        ↓
[SSH Connection]
    Data travels over network to Pi Zero W
        ↓
[Pi display_server.py]
    1. sys.stdin reads line: "> O Buy milk|  O Call mom||\n"
    2. parse_input() splits on "|": ["> O Buy milk", "  O Call mom", "", ""]
    3. display_lines() called:
       - canvas(device) opens drawing context
       - For each line (i=0 to 3):
         * Calculate y = i * 16 pixels
         * draw.text((0, y), line, font=font, fill=255)
       - canvas.__exit__() commits to OLED hardware
        ↓
[SSD1306 OLED]
    Pixels illuminate, user sees:
    > O Buy milk
      O Call mom
    
    
```

**Timing:**
- Feature render call → DisplayManager → SSH write: **< 1ms**
- SSH network transmission: **10-50ms**
- Pi parse & draw: **< 10ms**
- Total latency: **20-60ms** (imperceptible to user)

---

### 4.4 Camera Frame Flow (Optional)

**When Enabled in main_loop():**

```
[main_loop()]
    frame = camera.get_snapshot()
        ↓
[CameraManager.get_snapshot()]
    1. HTTP GET to phone: {base_url}/shot.jpg
    2. Receives JPEG bytes
    3. Returns bytes
        ↓
[main_loop()]
    current_feature.process_frame(frame)
        ↓
[Feature.process_frame(frame)]
    # Most features: do nothing (default implementation)
    # Camera-using features: 
    if frame:
        image = cv2.imdecode(frame)  # Convert to NumPy array
        text = ocr(image)             # Extract text
        self.current_data = translate(text)
        self.render()
        ↓
[Display Update]
    (Same flow as 4.3)
```

**Performance Note:**
Camera capture is expensive (~200-500ms per frame). Only enable if feature actually uses it. The todo feature, for example, never calls camera operations.

---

## 5. Instructions for Future Coding Agents

### 5.1 Naming Conventions

**Feature Names:**
- **Class:** `<Name>Feature` (e.g., `TodoFeature`, `WeatherFeature`)
- **File:** `features/<name>/feature.py` (lowercase, singular)
- **Name attribute:** `name = "<name>"` (lowercase, matches voice activation)

**Managers:**
- **Class:** `<Name>Manager` (e.g., `DisplayManager`, `AudioManager`)
- **File:** `core/<name>.py` (lowercase)
- **Instance variable:** `<name>` (e.g., `display`, `audio`)

**Methods:**
- Public methods: `snake_case` (e.g., `process_voice`, `show_lines`)
- Private methods: `_snake_case` with leading underscore (e.g., `_handle_add`)
- Abstract methods: Documented with `@abstractmethod` decorator

**Variables:**
- Constants: `UPPER_SNAKE_CASE` (e.g., `MAX_LINES = 4`)
- Instance vars: `snake_case` (e.g., `self.is_active`)
- Local vars: `snake_case` (e.g., `current_feature`)

**Files:**
- Python: `snake_case.py`
- Config: `config.yaml`, `.env`
- Docs: `UPPERCASE.md` (e.g., `README.md`, `SETUP.md`)

---

### 5.2 "Do Not Touch" Zones

**🚫 CRITICAL - DO NOT MODIFY:**

1. **`FeatureBase` Interface** (`core/feature_base.py`)
   - **Why:** All existing features depend on this contract
   - **Exception:** Adding optional helper methods is OK
   - **Never:** Change abstract method signatures

2. **Display Protocol** (`core/display.py` ↔ `pi/display_server.py`)
   - **Format:** `"Line1|Line2|Line3|Line4\n"` is hardcoded
   - **Why:** Changing breaks Pi display server
   - **Exception:** Can add new methods to DisplayManager
   - **Never:** Change pipe delimiter or line format

3. **VoiceTrigger Command Structure** (`core/voice_trigger.py`)
   - **Output:** `{"action": str, "target": str, "text": str}`
   - **Why:** main.py routing logic depends on these keys
   - **Exception:** Can add new action types
   - **Never:** Remove or rename existing action types

4. **Config Structure** (`config.yaml`)
   - **Keys:** `pi`, `ip_webcam`, `voice`, `features`
   - **Why:** Initialization code expects these sections
   - **Exception:** Can add new feature-specific keys
   - **Never:** Remove or rename top-level sections

5. **Display Constraints**
   - **Hard limits:** 4 lines, 21 chars per line
   - **Why:** Physical OLED hardware limitation
   - **Exception:** None - this is immutable
   - **Never:** Attempt to show 5+ lines or 22+ chars

---

### 5.3 Safe Modification Zones

**✅ ENCOURAGED - MODIFY FREELY:**

1. **Adding New Features** (`features/<newfeature>/`)
   - Create new feature directory with `feature.py`
   - Implement FeatureBase interface
   - Register in `main.py` → `register_features()`

2. **Feature-Specific Logic** (`features/<name>/feature.py`)
   - All logic inside feature classes is isolated
   - Modify commands, rendering, state as needed
   - Changes don't affect other features

3. **Configuration Values** (`config.yaml`)
   - Change URLs, API keys, timeouts
   - Add new feature-specific config sections
   - Does not break core logic

4. **Logging** (any file)
   - Add/remove/change logger.debug/info/error calls
   - Does not affect functionality

5. **Helper Methods** (any class)
   - Add private `_helper()` methods as needed
   - Keeps code organized

---

### 5.4 Integration Checklist for New Features

When creating a new feature, verify:

- [ ] **Inherits from FeatureBase**
  ```python
  from core.feature_base import FeatureBase
  class MyFeature(FeatureBase):
  ```

- [ ] **Sets name attribute**
  ```python
  name = "myfeature"  # Lowercase, matches voice activation
  ```

- [ ] **Implements all abstract methods**
  - `activate()`
  - `deactivate()`
  - `process_voice(transcript)`
  - `render()`

- [ ] **Calls super().__init__()**
  ```python
  def __init__(self, display, audio, camera, config):
      super().__init__(display, audio, camera, config)
  ```

- [ ] **Sets is_active correctly**
  - `True` in `activate()`
  - `False` in `deactivate()`

- [ ] **Respects display constraints**
  - Max 4 lines
  - Max 21 chars per line
  - Truncates with ellipsis if needed

- [ ] **Registered in main.py**
  ```python
  from features.myfeature import MyFeature
  features["myfeature"] = MyFeature(display, audio, camera, config)
  ```

- [ ] **Exports in __init__.py**
  ```python
  from .feature import MyFeature
  __all__ = ['MyFeature']
  ```

- [ ] **Documents voice commands** (README.md)

- [ ] **Implements error handling**
  - Try/except in command handlers
  - Calls `self.handle_error()` for exceptions

- [ ] **Provides audio feedback**
  - Uses `self.speak_feedback()` after actions

---

### 5.5 Common Pitfalls to Avoid

**❌ Don't:**

1. **Assume features persist state between activations**
   - Features are kept in memory but user may not reactivate
   - Always save critical state in `deactivate()`

2. **Exceed display limits**
   - Bad: `display.show_lines([line1, line2, line3, line4, line5])`
   - Good: `display.show_lines(lines[:4])`

3. **Block in process_voice() or render()**
   - Main loop expects quick return (< 100ms ideal)
   - Long operations → move to background thread or async

4. **Forget to update display after state changes**
   - Every command that changes state should call `self.render()`

5. **Hardcode configuration values**
   - Bad: `api_key = "sk-12345"`
   - Good: `api_key = self.config.get('my_api_key')`

6. **Ignore None returns from managers**
   - `audio.listen()` returns `None` if no speech
   - `camera.get_snapshot()` returns `None` on failure
   - Always check before using

7. **Raise exceptions in lifecycle methods**
   - Use try/except and `self.handle_error()` instead
   - Unhandled exceptions crash the entire system

---

### 5.6 Testing Strategy

**Local Testing (No Hardware):**
```python
# Create mock managers
class MockDisplay:
    def show_lines(self, lines):
        print(f"DISPLAY: {lines}")

class MockAudio:
    def speak(self, text):
        print(f"AUDIO: {text}")

class MockCamera:
    pass

# Test feature in isolation
config = {"test_key": "value"}
feature = MyFeature(MockDisplay(), MockAudio(), MockCamera(), config)
feature.activate()
feature.process_voice("test command")
```

**Hardware Testing:**
1. Start display server on Pi: `python pi/display_server.py`
2. Run feature test with real managers
3. Verify display, audio, camera responses

**Integration Testing:**
1. Run full `main.py`
2. Test voice activation: "Hey Iris, activate myfeature"
3. Test commands while active
4. Test deactivation: "Hey Iris, stop"

---

### 5.7 Debugging Guidelines

**Display Issues:**
- Check SSH connection: `ssh user@pi_host`
- Verify display server running on Pi
- Check logs: `iris.log` and Pi logs
- Test with manual command: `echo "Test|Line|Three|" | ssh user@pi python display_server.py`

**Audio Issues:**
- Verify IP Webcam app running on phone
- Test URL: `curl http://192.168.43.1:8080/audio.wav`
- Check audio manager logs for recognition errors
- Test TTS locally: `python -c "import pyttsx3; e=pyttsx3.init(); e.say('test'); e.runAndWait()"`

**Voice Recognition Issues:**
- Check wake word in config.yaml matches spoken phrase
- Verify audio.listen() returns transcript (check logs)
- Test speech recognition independently
- Check network connection to phone

**Feature Not Activating:**
- Verify feature name matches voice command
- Check feature registered in `main.py`
- Verify `__init__.py` exports feature class
- Check logs for import errors

---

### 5.8 Performance Optimization Guidelines

**Display Updates:**
- Only call `render()` when state changes
- Don't render in tight loops
- Batch updates if possible

**Audio:**
- `speak()` is slow (~1-2 seconds)
- Don't speak after every tiny action
- Combine multiple actions into one announcement

**Camera:**
- `get_snapshot()` is expensive (~200-500ms)
- Only enable camera frame capture if feature needs it
- Process frames asynchronously if possible

**Memory:**
- Large data (images, recordings) should be processed and discarded
- Don't accumulate unbounded lists in memory
- Save to disk for long-term storage

---

### 5.9 Security Considerations

**API Keys:**
- Never hardcode in source files
- Store in `.env` or `config.yaml`
- Add `.env` to `.gitignore`
- Use environment variables for sensitive data

**Network Communication:**
- IP Webcam runs over local network (not encrypted by default)
- SSH to Pi uses key-based auth (secure)
- External API calls should use HTTPS

**User Data:**
- Features that store user data (like todo items) should save locally
- Implement data export/deletion if needed
- Don't send personal data to external APIs without consent

---

## 6. Advanced Topics

### 6.1 Multi-Feature Coordination

**Current Limitation:** Only ONE feature can be active at a time.

**Why:** Single OLED display, single audio channel - can't multiplex.

**Future Enhancement:** Could implement "background features" that don't render but listen for specific trigger phrases while another feature is active.

---

### 6.2 Adding New Hardware

**To add a new I/O device:**

1. Create `core/<device>.py` with `<Device>Manager` class
2. Initialize in `main.py` → `init_managers()`
3. Pass to features via constructor
4. Update `FeatureBase.__init__()` to accept new manager
5. Update all existing features' constructors

**Example: Adding GPS:**
```python
# core/gps.py
class GPSManager:
    def get_location(self) -> dict:
        # Return {'lat': float, 'lon': float}
        pass

# main.py
def init_managers(config):
    # ... existing managers
    gps = GPSManager(config)
    return display, audio, camera, voice_trigger, gps

# FeatureBase
def __init__(self, display, audio, camera, gps, config):
    self.gps = gps
    # ...

# All features must update:
def __init__(self, display, audio, camera, gps, config):
    super().__init__(display, audio, camera, gps, config)
```

---

### 6.3 Alternative Display Server Implementations

**Current:** SSH stdin pipe  
**Alternative:** Socket server (as implemented for testing)

**Socket Server Advantages:**
- Works better from Windows (no SSH issues)
- Bidirectional communication possible
- Can send acknowledgments

**Socket Server Implementation:**
```python
# pi/display_server_socket.py
server = socket.socket()
server.bind(('0.0.0.0', 5555))
server.listen(1)

while True:
    conn, addr = server.accept()
    data = conn.recv(1024).decode('utf-8')
    lines = data.split('|')
    display_lines(device, lines)
    conn.close()

# core/display.py
def show_lines(self, lines):
    sock = socket.socket()
    sock.connect((self.pi_host, 5555))
    sock.send('|'.join(lines).encode('utf-8'))
    sock.close()
```

**Trade-offs:**
- Socket: More code, but more flexible
- SSH stdin: Less code, Unix-native, but Windows issues

---

### 6.4 Feature State Persistence Patterns

**Pattern 1: JSON File**
```python
def save_state(self):
    with open('feature_data.json', 'w') as f:
        json.dump(self.data, f)

def load_state(self):
    if os.path.exists('feature_data.json'):
        with open('feature_data.json') as f:
            self.data = json.load(f)
```

**Pattern 2: SQLite Database**
```python
import sqlite3

def __init__(self, ...):
    self.db = sqlite3.connect('feature_data.db')
    self.db.execute('CREATE TABLE IF NOT EXISTS items (...)')

def save_item(self, item):
    self.db.execute('INSERT INTO items VALUES (?)', (item,))
    self.db.commit()
```

**Pattern 3: Config File**
```python
# For user preferences
def save_prefs(self):
    config_updates = {'my_feature': {'pref1': value}}
    # Write to config.yaml or separate file
```

---

## 7. Troubleshooting Reference

### 7.1 Common Error Messages

**"Failed to connect to Pi display"**
- **Cause:** SSH can't reach Pi or display_server.py not found
- **Fix:** Verify `ssh user@pi_host` works, check `display_server_path` in config

**"No connection could be made (WinError 10061)"**
- **Cause:** Socket connection refused (wrong IP or server not running)
- **Fix:** Verify server running on Pi, check IP address in config

**"Could not understand audio"**
- **Cause:** Speech recognition failed (unclear audio or no speech)
- **Fix:** Speak clearly near phone microphone, check ambient noise

**"Unknown feature: <name>"**
- **Cause:** Feature not registered or typo in voice command
- **Fix:** Check feature name in `register_features()`, verify voice command

**"Error: [Errno 13] Permission denied"**
- **Cause:** Can't write to file (wrong permissions or path)
- **Fix:** Check file path, ensure directory exists and is writable

---

### 7.2 Log Analysis

**Log Levels:**
- **DEBUG:** Detailed trace (voice transcripts, display commands)
- **INFO:** Normal operations (feature activation, connections)
- **WARNING:** Recoverable issues (command not recognized, connection retry)
- **ERROR:** Failures (can't save file, hardware disconnected)

**Key Log Patterns:**

```
INFO - Configuration loaded successfully
→ Config parsed OK

INFO - Registered 4 features: ['todo', 'weather', ...]
→ Features initialized

INFO - ✓ Pi display connection successful
→ Hardware connected

INFO - Activated feature: todo
→ Feature is now active

DEBUG - Sent command: "> O Buy milk|  O Call mom||"
→ Display update sent

ERROR - Failed to connect to Pi display
→ SSH connection failed - check network
```

---

## 8. Summary & Best Practices

### 8.1 Architecture Principles

1. **Separation of Concerns:** Hardware I/O ≠ Business Logic
2. **Single Responsibility:** Each module does ONE thing well
3. **Fail-Safe:** System continues despite individual component failures
4. **Stateless Protocols:** Display/audio commands have no memory
5. **Hot-Swappable:** Features can be added/removed without system changes

### 8.2 Development Workflow

**Adding a New Feature:**
1. Create `features/<name>/feature.py` implementing FeatureBase
2. Create `features/<name>/__init__.py` exporting feature class
3. Register in `main.py` → `register_features()`
4. Test with mock managers locally
5. Test with real hardware
6. Document in README.md

**Modifying Core:**
1. Understand impact on existing features
2. Update FeatureBase if interface changes
3. Update ALL features if constructor changes
4. Test entire system, not just modified code
5. Update documentation

### 8.3 Key Takeaways for AI Agents

- **FeatureBase is the contract:** All features MUST implement its interface
- **Display is 4×21:** Physical constraint, cannot be exceeded
- **main.py is the orchestrator:** It routes commands and manages lifecycle
- **Features are isolated:** Changes to one don't affect others
- **Logging is essential:** All operations should be logged for debugging
- **Error handling is required:** Features must not crash the system

---

**End of Technical Documentation**

*This document is the authoritative reference for Iris Smart Glasses internal architecture. When in doubt, consult this document first.*