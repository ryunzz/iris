"""
Iris Smart Glasses - Feature Base Class

Abstract base class that all features inherit from.
Defines the interface for modular features.
"""

from abc import ABC, abstractmethod
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class FeatureBase(ABC):
    """Abstract base class for all Iris Smart Glasses features."""
    
    # Override this in subclasses - used for voice activation
    name: str = "unnamed"
    
    def __init__(self, display, audio, camera, config):
        """
        Initialize feature with core managers.
        
        Args:
            display: DisplayManager instance
            audio: AudioManager instance  
            camera: CameraManager instance
            config: Configuration dictionary
        """
        self.display = display
        self.audio = audio
        self.camera = camera
        self.config = config
        self.is_active = False
        
        logger.info(f"Initialized feature: {self.name}")
    
    @abstractmethod
    def activate(self) -> None:
        """
        Called when user says 'hey iris activate {name}'.
        
        This method should:
        - Set up any necessary state
        - Display initial UI on OLED
        - Set self.is_active = True
        """
        pass
    
    @abstractmethod
    def deactivate(self) -> None:
        """
        Called when switching features or 'hey iris stop'.
        
        This method should:
        - Clean up any state
        - Clear the display if needed
        - Set self.is_active = False
        """
        pass
    
    @abstractmethod
    def process_voice(self, transcript: str) -> None:
        """
        Handle voice input while this feature is active.
        
        Args:
            transcript: Voice command text (already processed, no wake word)
            
        This method should:
        - Parse the command for this feature
        - Execute the appropriate action
        - Update the display if needed
        - Provide audio feedback if appropriate
        """
        pass
    
    def process_frame(self, frame: Optional[bytes]) -> None:
        """
        Handle camera frame input. Override if feature needs camera input.
        
        Args:
            frame: JPEG image data from phone camera, or None if no frame
            
        Default implementation does nothing.
        Features that need camera input should override this.
        """
        pass
    
    @abstractmethod
    def render(self) -> None:
        """
        Update the OLED display with current feature state.
        
        This method should:
        - Generate current display content based on feature state
        - Call self.display.show_lines() or self.display.show_text()
        - Handle display constraints (4 lines, 21 chars per line)
        """
        pass
    
    def get_help_text(self) -> str:
        """
        Get help text describing this feature's commands.
        
        Returns:
            String describing available voice commands
            
        Default implementation returns basic info.
        Features should override to provide specific command help.
        """
        return f"{self.name} feature - see documentation for commands"
    
    def handle_error(self, error: Exception, context: str = "unknown") -> None:
        """
        Handle errors that occur during feature operation.
        
        Args:
            error: Exception that occurred
            context: Context where error occurred
            
        Default implementation logs error and shows error on display.
        Features can override for custom error handling.
        """
        error_msg = f"Error in {self.name} ({context}): {str(error)}"
        logger.error(error_msg)
        
        # Show error on display
        self.display.show_lines([
            f"{self.name} Error:",
            str(error)[:20],
            "",
            "Try again"
        ])
    
    def speak_feedback(self, text: str) -> None:
        """
        Provide audio feedback via phone speaker.
        
        Args:
            text: Text to speak
            
        Helper method for features to provide audio feedback.
        """
        try:
            self.audio.speak(text)
        except Exception as e:
            logger.error(f"Failed to speak feedback '{text}': {e}")
    
    def __enter__(self):
        """Context manager entry - activate the feature."""
        self.activate()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - deactivate the feature."""
        self.deactivate()
    
    def __str__(self) -> str:
        """String representation of feature."""
        status = "active" if self.is_active else "inactive"
        return f"{self.name} feature ({status})"
    
    def __repr__(self) -> str:
        """Debug representation of feature."""
        return f"<{self.__class__.__name__}: name='{self.name}', active={self.is_active}>"