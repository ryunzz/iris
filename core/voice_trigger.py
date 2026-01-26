"""
Iris Smart Glasses - Voice Trigger Manager

This module runs on the LT and handles:
- Wake word detection ("Hey Iris")
- Voice command parsing
- Command routing to appropriate handlers
"""

import logging
from typing import Optional, Dict, Any
import re

logger = logging.getLogger(__name__)


class VoiceTrigger:
    """Manages wake word detection and voice command parsing."""
    
    def __init__(self, audio_manager, wake_word: str = "hey iris"):
        """
        Initialize voice trigger manager.
        
        Args:
            audio_manager: AudioManager instance for speech capture
            wake_word: Wake word phrase to listen for
        """
        self.audio_manager = audio_manager
        self.wake_word = wake_word.lower().strip()
        self.listen_timeout = 10  # Seconds to listen for command after wake word
        
        logger.info(f"Initialized voice trigger with wake word: '{self.wake_word}'")
    
    def listen_for_command(self, timeout: int = 10) -> Optional[str]:
        """
        Listen for voice input and check for wake word + command.
        
        Args:
            timeout: Maximum time to wait for audio (seconds)
            
        Returns:
            Full command string if wake word detected, None otherwise
        """
        try:
            # Listen for audio
            transcript = self.audio_manager.listen(timeout)
            
            if transcript is None:
                logger.debug("No speech detected")
                return None
            
            # Check for wake word
            if self._has_wake_word(transcript):
                logger.info(f"Wake word detected in: '{transcript}'")
                return transcript
            else:
                logger.debug(f"No wake word in: '{transcript}'")
                return None
                
        except Exception as e:
            logger.error(f"Error listening for command: {e}")
            return None
    
    def _has_wake_word(self, transcript: str) -> bool:
        """
        Check if transcript contains the wake word.
        
        Args:
            transcript: Speech transcript to check
            
        Returns:
            True if wake word detected, False otherwise
        """
        if not transcript:
            return False
        
        # Normalize transcript
        normalized = transcript.lower().strip()
        
        # Simple substring search for wake word
        return self.wake_word in normalized
    
    def parse_command(self, raw_transcript: str) -> Dict[str, Any]:
        """
        Parse voice command into structured format.
        
        Args:
            raw_transcript: Raw transcript containing wake word and command
            
        Returns:
            Dictionary with parsed command structure:
            - action: "activate", "stop", or "passthrough"
            - target: Feature name (for activate) or None
            - text: Raw command text (for passthrough) or None
        """
        if not raw_transcript:
            return {"action": "unknown", "target": None, "text": None}
        
        # Normalize input
        text = raw_transcript.lower().strip()
        
        # Remove wake word from the beginning
        if text.startswith(self.wake_word):
            command_part = text[len(self.wake_word):].strip()
        else:
            # Look for wake word anywhere in the text and extract what follows
            wake_index = text.find(self.wake_word)
            if wake_index >= 0:
                command_part = text[wake_index + len(self.wake_word):].strip()
            else:
                # No wake word found - shouldn't happen if called correctly
                command_part = text
        
        logger.debug(f"Extracted command part: '{command_part}'")
        
        # Parse different command types
        if not command_part:
            return {"action": "unknown", "target": None, "text": None}
        
        # Check for "activate" commands
        activate_match = re.match(r'^activate\s+(\w+)', command_part)
        if activate_match:
            feature_name = activate_match.group(1)
            logger.info(f"Parsed activate command for feature: {feature_name}")
            return {
                "action": "activate",
                "target": feature_name,
                "text": None
            }
        
        # Check for "stop" command
        if command_part in ['stop', 'exit', 'quit', 'deactivate']:
            logger.info("Parsed stop command")
            return {
                "action": "stop", 
                "target": None,
                "text": None
            }
        
        # Everything else is a passthrough command for the active feature
        logger.info(f"Parsed passthrough command: '{command_part}'")
        return {
            "action": "passthrough",
            "target": None,
            "text": command_part
        }
    
    def wait_for_activation_command(self, timeout: int = 30) -> Optional[str]:
        """
        Listen specifically for feature activation commands.
        
        Args:
            timeout: Maximum time to wait (seconds)
            
        Returns:
            Feature name if activation command detected, None otherwise
        """
        start_time = 0
        while start_time < timeout:
            try:
                command = self.listen_for_command(5)  # Short listen intervals
                
                if command:
                    parsed = self.parse_command(command)
                    if parsed["action"] == "activate" and parsed["target"]:
                        return parsed["target"]
                
                start_time += 5  # Approximate time increment
                
            except Exception as e:
                logger.error(f"Error waiting for activation command: {e}")
                break
        
        return None
    
    def get_supported_commands(self) -> Dict[str, str]:
        """
        Get dictionary of supported voice commands and their descriptions.
        
        Returns:
            Dictionary mapping command patterns to descriptions
        """
        return {
            f"{self.wake_word} activate <feature>": "Activate a specific feature (todo, directions, translation)",
            f"{self.wake_word} stop": "Stop current feature and return to idle",
            f"{self.wake_word} <command>": "Send command to active feature"
        }
    
    def set_wake_word(self, new_wake_word: str) -> None:
        """
        Change the wake word.
        
        Args:
            new_wake_word: New wake word phrase
        """
        old_wake_word = self.wake_word
        self.wake_word = new_wake_word.lower().strip()
        logger.info(f"Changed wake word from '{old_wake_word}' to '{self.wake_word}'")