#!/usr/bin/env python3
"""
State machine and command parser for Iris Smart Glasses.

Handles voice command parsing based on current state and manages state transitions.
"""

import time
import logging
from enum import Enum
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

from .discovery import DeviceRegistry


logger = logging.getLogger(__name__)


class State(Enum):
    """System states for voice command processing."""
    IDLE = "idle"                         # Weather/time display
    MAIN_MENU = "main_menu"               # 1.Todo 2.Translation 3.Connect
    TODO_MENU = "todo_menu"               # Todo instructions and options
    TODO_LIST = "todo_list"               # Show todos
    TODO_ADD = "todo_add"                 # Voice input for new todo
    TODO_INSTRUCTIONS = "todo_instructions"  # Show todo usage instructions
    TRANSLATION = "translation"           # Live translation feed
    DEVICE_LIST = "device_list"           # Dynamic list of IoT devices
    CONNECTED_LIGHT = "connected_light"
    CONNECTED_FAN = "connected_fan"
    CONNECTED_MOTION = "connected_motion"
    CONNECTED_DISTANCE = "connected_distance"
    CONNECTED_GLASSES = "connected_glasses"


@dataclass
class ParseResult:
    """Result from parsing a voice command."""
    new_state: Optional[State] = None     # New state to transition to
    action: Optional[str] = None          # Action to perform
    data: Dict[str, Any] = None          # Additional data for action
    
    def __post_init__(self):
        if self.data is None:
            self.data = {}


class CommandParser:
    """
    State machine for voice command processing.
    
    Handles state transitions based on current state and voice input.
    Manages timeout behavior for menu states.
    """
    
    # States with 10-second timeout (return to IDLE if no input)
    TIMEOUT_STATES = {
        State.MAIN_MENU,
        State.TODO_LIST,
        State.DEVICE_LIST
    }
    
    # States with timeout that go to specific state (not IDLE)
    CUSTOM_TIMEOUT_STATES = {
        State.TODO_ADD: State.TODO_LIST  # TODO_ADD times out to TODO_LIST (cancel)
    }
    
    # States that never timeout (require explicit exit command)
    NO_TIMEOUT_STATES = {
        State.IDLE,
        State.TRANSLATION,
        State.CONNECTED_LIGHT,
        State.CONNECTED_FAN,
        State.CONNECTED_MOTION,
        State.CONNECTED_DISTANCE,
        State.CONNECTED_GLASSES
    }
    
    def __init__(self, registry: DeviceRegistry, timeout_seconds: float = 10.0):
        self.registry = registry
        self.timeout_seconds = timeout_seconds
        self.current_state = State.IDLE
        self.last_command_time = datetime.now()
        self.state_data: Dict[str, Any] = {}  # Persistent data for current state
        
        logger.info("Command parser initialized in IDLE state")
    
    def parse(self, transcript: str) -> ParseResult:
        """
        Parse voice command based on current state.
        
        Args:
            transcript: Voice input transcript (lowercase, trimmed)
            
        Returns:
            ParseResult with new state and/or action
        """
        if not transcript:
            return ParseResult()
        
        # Strip "iris" prefix from commands (preserves "hey iris" wake word)
        cleaned_transcript = self._strip_iris_prefix(transcript)
        
        # Update last command time
        self.last_command_time = datetime.now()
        
        logger.info(f"Parsing command '{cleaned_transcript}' in state {self.current_state.value}")
        
        # Route to appropriate parser based on current state
        if self.current_state == State.IDLE:
            result = self._parse_idle(cleaned_transcript)
        elif self.current_state == State.MAIN_MENU:
            result = self._parse_main_menu(cleaned_transcript)
        elif self.current_state == State.TODO_MENU:
            result = self._parse_todo_menu(cleaned_transcript)
        elif self.current_state == State.TODO_INSTRUCTIONS:
            result = self._parse_todo_instructions(cleaned_transcript)
        elif self.current_state == State.TODO_LIST:
            result = self._parse_todo_list(cleaned_transcript)
        elif self.current_state == State.TODO_ADD:
            result = self._parse_todo_add(cleaned_transcript)
        elif self.current_state == State.TRANSLATION:
            result = self._parse_translation(cleaned_transcript)
        elif self.current_state == State.DEVICE_LIST:
            result = self._parse_device_list(cleaned_transcript)
        elif self.current_state == State.CONNECTED_LIGHT:
            result = self._parse_connected_light(cleaned_transcript)
        elif self.current_state == State.CONNECTED_FAN:
            result = self._parse_connected_fan(cleaned_transcript)
        elif self.current_state == State.CONNECTED_MOTION:
            result = self._parse_connected_motion(cleaned_transcript)
        elif self.current_state == State.CONNECTED_DISTANCE:
            result = self._parse_connected_distance(cleaned_transcript)
        elif self.current_state == State.CONNECTED_GLASSES:
            result = self._parse_connected_glasses(cleaned_transcript)
        else:
            logger.warning(f"No parser for state {self.current_state}")
            result = ParseResult()
        
        # Update current state if new state specified
        if result.new_state:
            self._transition_to(result.new_state)
        
        return result
    
    def check_timeout(self) -> Optional[State]:
        """
        Check if current state has timed out.
        
        Returns:
            New state to transition to if timeout occurred, None otherwise
        """
        time_since_last_command = datetime.now() - self.last_command_time
        
        if time_since_last_command.total_seconds() < self.timeout_seconds:
            return None
        
        # Check timeout behavior based on current state
        if self.current_state in self.TIMEOUT_STATES:
            logger.info(f"State {self.current_state.value} timed out, returning to IDLE")
            self._transition_to(State.IDLE)
            return State.IDLE
        
        elif self.current_state in self.CUSTOM_TIMEOUT_STATES:
            new_state = self.CUSTOM_TIMEOUT_STATES[self.current_state]
            logger.info(f"State {self.current_state.value} timed out, going to {new_state.value}")
            self._transition_to(new_state)
            return new_state
        
        # No timeout for this state
        return None
    
    def _transition_to(self, new_state: State) -> None:
        """Transition to a new state."""
        old_state = self.current_state
        self.current_state = new_state
        self.last_command_time = datetime.now()
        
        # Clear state data when changing states
        if old_state != new_state:
            self.state_data.clear()
        
        logger.info(f"State transition: {old_state.value} → {new_state.value}")
    
    def get_current_state(self) -> State:
        """Get current state."""
        return self.current_state
    
    def set_state_data(self, key: str, value: Any) -> None:
        """Set persistent data for current state."""
        self.state_data[key] = value
    
    def get_state_data(self, key: str, default: Any = None) -> Any:
        """Get persistent data for current state."""
        return self.state_data.get(key, default)
    
    def _strip_iris_prefix(self, transcript: str) -> str:
        """
        Strip 'iris' prefix from commands while preserving 'hey iris' wake word.
        
        Args:
            transcript: Raw transcript from speech recognition
            
        Returns:
            Cleaned transcript with iris prefix removed (if applicable)
        """
        if not transcript:
            return transcript
            
        # Preserve "hey iris" wake command - don't strip anything
        if transcript.startswith("hey iris"):
            return transcript
            
        # Strip "iris " prefix for standalone commands
        if transcript.startswith("iris "):
            cleaned = transcript[5:].strip()  # Remove "iris " and any extra spaces
            logger.debug(f"Stripped iris prefix: '{transcript}' → '{cleaned}'")
            return cleaned
            
        # Return as-is for backward compatibility
        return transcript
    
    def _normalize_number_word(self, transcript: str) -> str:
        """Convert number words to digits for easier parsing."""
        word_to_digit = {
            "one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
            "six": "6", "seven": "7", "eight": "8", "nine": "9"
        }
        return word_to_digit.get(transcript, transcript)
    
    # State-specific parsers
    
    def _parse_idle(self, transcript: str) -> ParseResult:
        """Parse commands in IDLE state."""
        if "hey iris" in transcript:
            return ParseResult(new_state=State.MAIN_MENU)
        
        return ParseResult()
    
    def _parse_main_menu(self, transcript: str) -> ParseResult:
        """Parse commands in MAIN_MENU state."""
        normalized = self._normalize_number_word(transcript)
        
        if normalized in ["todo", "1"] or transcript in ["todo", "one"]:
            return ParseResult(new_state=State.TODO_MENU)
        elif normalized in ["weather", "2"] or transcript in ["weather", "translation", "two"]:
            return ParseResult(new_state=State.TRANSLATION)
        elif normalized in ["connect", "3"] or transcript in ["connect", "three"]:
            return ParseResult(new_state=State.DEVICE_LIST)
        elif transcript == "back":
            return ParseResult(new_state=State.IDLE)
        
        return ParseResult()
    
    def _parse_todo_menu(self, transcript: str) -> ParseResult:
        """Parse commands in TODO_MENU state."""
        normalized = self._normalize_number_word(transcript)
        
        if normalized in ["list", "1"] or transcript in ["list", "one"]:
            return ParseResult(new_state=State.TODO_LIST)
        elif normalized in ["add", "2"] or transcript in ["add", "two"]:
            return ParseResult(new_state=State.TODO_ADD)
        elif normalized in ["instructions", "3"] or transcript in ["instructions", "three"]:
            return ParseResult(new_state=State.TODO_INSTRUCTIONS)
        
        return ParseResult()
    
    def _parse_todo_instructions(self, transcript: str) -> ParseResult:
        """Parse commands in TODO_INSTRUCTIONS state."""
        if transcript == "back":
            return ParseResult(new_state=State.TODO_MENU)
        
        return ParseResult()
    
    def _parse_todo_list(self, transcript: str) -> ParseResult:
        """Parse commands in TODO_LIST state."""
        if transcript == "up":
            return ParseResult(action="scroll_up")
        elif transcript == "down":
            return ParseResult(action="scroll_down")
        elif transcript == "cross":
            return ParseResult(action="mark_done")
        elif transcript == "uncross":
            return ParseResult(action="mark_undone")
        elif transcript == "add":
            return ParseResult(new_state=State.TODO_ADD)
        elif transcript == "back":
            return ParseResult(new_state=State.TODO_MENU)
        
        return ParseResult()
    
    def _parse_todo_add(self, transcript: str) -> ParseResult:
        """Parse commands in TODO_ADD state."""
        if transcript == "confirm":
            # Get captured text from state data
            todo_text = self.get_state_data("captured_text", "")
            if todo_text:
                return ParseResult(
                    new_state=State.TODO_LIST,
                    action="add_todo",
                    data={"text": todo_text}
                )
        elif transcript == "cancel":
            return ParseResult(new_state=State.TODO_LIST)
        else:
            # Capture the text as todo item
            self.set_state_data("captured_text", transcript)
            return ParseResult(action="capture_todo_text", data={"text": transcript})
        
        return ParseResult()
    
    def _parse_translation(self, transcript: str) -> ParseResult:
        """Parse commands in TRANSLATION state."""
        if "iris end" in transcript or transcript == "end":
            return ParseResult(new_state=State.MAIN_MENU)
        else:
            # All other audio is passed through for translation
            return ParseResult(action="translate", data={"text": transcript})
    
    def _parse_device_list(self, transcript: str) -> ParseResult:
        """Parse commands in DEVICE_LIST state."""
        if transcript == "up":
            return ParseResult(action="scroll_up")
        elif transcript == "down":
            return ParseResult(action="scroll_down")
        elif transcript == "connect":
            # Connect to highlighted device
            return ParseResult(action="connect_current")
        elif transcript.startswith("connect "):
            # Connect to named device
            device_name = transcript[8:]  # Remove "connect "
            return ParseResult(action="connect_named", data={"name": device_name})
        elif transcript in ["1", "2", "3", "4", "5", "6", "7", "8", "9"] or self._normalize_number_word(transcript) in ["1", "2", "3", "4", "5", "6", "7", "8", "9"]:
            # Connect to numbered device (1-based) - supports both digits and words
            normalized = self._normalize_number_word(transcript)
            if normalized in ["1", "2", "3", "4", "5", "6", "7", "8", "9"]:
                device_number = int(normalized) - 1  # Convert to 0-based index
                return ParseResult(action="connect_numbered", data={"index": device_number})
        elif transcript == "back":
            return ParseResult(new_state=State.MAIN_MENU)
        
        return ParseResult()
    
    def _parse_connected_light(self, transcript: str) -> ParseResult:
        """Parse commands in CONNECTED_LIGHT state."""
        if transcript == "on":
            return ParseResult(action="light_on")
        elif transcript == "off":
            return ParseResult(action="light_off")
        elif transcript == "back":
            return ParseResult(new_state=State.DEVICE_LIST)
        
        return ParseResult()
    
    def _parse_connected_fan(self, transcript: str) -> ParseResult:
        """Parse commands in CONNECTED_FAN state."""
        if transcript == "on":
            return ParseResult(action="fan_on")
        elif transcript == "off":
            return ParseResult(action="fan_off")
        elif transcript == "low":
            return ParseResult(action="fan_low")
        elif transcript == "high":
            return ParseResult(action="fan_high")
        elif transcript == "back":
            return ParseResult(new_state=State.DEVICE_LIST)
        
        return ParseResult()
    
    def _parse_connected_motion(self, transcript: str) -> ParseResult:
        """Parse commands in CONNECTED_MOTION state."""
        if transcript == "on":
            return ParseResult(action="motion_on")
        elif transcript == "off":
            return ParseResult(action="motion_off")
        elif transcript == "back":
            return ParseResult(new_state=State.DEVICE_LIST)
        
        return ParseResult()
    
    def _parse_connected_distance(self, transcript: str) -> ParseResult:
        """Parse commands in CONNECTED_DISTANCE state."""
        if transcript == "back":
            return ParseResult(new_state=State.DEVICE_LIST)
        
        # No other commands - just live stream
        return ParseResult()
    
    def _parse_connected_glasses(self, transcript: str) -> ParseResult:
        """Parse commands in CONNECTED_GLASSES state."""
        if transcript.startswith("send "):
            message = transcript[5:]  # Remove "send "
            return ParseResult(action="send_message", data={"message": message})
        elif transcript == "back":
            return ParseResult(new_state=State.DEVICE_LIST)
        
        return ParseResult()
    
    # Helper methods for state transitions based on device connections
    
    def connect_to_device(self, device_type: str) -> State:
        """
        Get the connected state for a device type.
        
        Args:
            device_type: Type of device ("light", "fan", etc.)
            
        Returns:
            Appropriate CONNECTED_* state
        """
        state_mapping = {
            "light": State.CONNECTED_LIGHT,
            "fan": State.CONNECTED_FAN,
            "motion": State.CONNECTED_MOTION,
            "distance": State.CONNECTED_DISTANCE,
            "glasses": State.CONNECTED_GLASSES
        }
        
        return state_mapping.get(device_type, State.DEVICE_LIST)
    
    def get_device_name_mapping(self) -> Dict[str, str]:
        """Get mapping of spoken device names to device types."""
        return {
            "light": "light",
            "smart light": "light",
            "fan": "fan", 
            "smart fan": "fan",
            "motion": "motion",
            "motion sensor": "motion",
            "distance": "distance",
            "distance sensor": "distance",
            "glasses": "glasses",
            "glasses 2": "glasses",
            "glasses two": "glasses"
        }


if __name__ == "__main__":
    # Test state machine
    import sys
    from .discovery import create_registry
    
    logging.basicConfig(level=logging.INFO)
    
    # Create mock registry for testing
    registry = create_registry(mock=True)
    parser = CommandParser(registry, timeout_seconds=5.0)
    
    print("Testing state machine...")
    print("Current state:", parser.get_current_state().value)
    
    # Test command sequences
    test_commands = [
        "hey iris",           # IDLE → MAIN_MENU
        "todo",               # MAIN_MENU → TODO_LIST  
        "add",                # TODO_LIST → TODO_ADD
        "buy groceries",      # Capture text
        "confirm",            # Add todo, → TODO_LIST
        "back",               # TODO_LIST → MAIN_MENU
        "connect",            # MAIN_MENU → DEVICE_LIST
        "connect light",      # Connect to light
        "on",                 # Turn light on
        "back",               # CONNECTED_LIGHT → DEVICE_LIST
        "back"                # DEVICE_LIST → MAIN_MENU
    ]
    
    for i, command in enumerate(test_commands):
        print(f"\n--- Command {i+1}: '{command}' ---")
        print(f"Current state: {parser.get_current_state().value}")
        
        result = parser.parse(command)
        
        if result.new_state:
            print(f"→ New state: {result.new_state.value}")
        if result.action:
            print(f"→ Action: {result.action}")
            if result.data:
                print(f"→ Data: {result.data}")
    
    print(f"\nFinal state: {parser.get_current_state().value}")
    
    # Test timeout
    print(f"\n--- Testing timeout (waiting 6 seconds) ---")
    time.sleep(6)
    timeout_state = parser.check_timeout()
    if timeout_state:
        print(f"Timed out to: {timeout_state.value}")
    else:
        print("No timeout")
    
    print("\nState machine test complete")