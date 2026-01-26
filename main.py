#!/usr/bin/env python3
"""
Iris Smart Glasses - Main Application

Entry point that runs on the laptop. This is the "brain" that:
- Connects to Pi Zero W for display
- Connects to phone for camera/audio
- Manages voice commands and features
"""

import os
import sys
import logging
import yaml
import time
from typing import Dict, Optional
from dotenv import load_dotenv

# Import core modules
from core.display import DisplayManager
from core.audio import AudioManager
from core.camera import CameraManager
from core.voice_trigger import VoiceTrigger
from core.feature_base import FeatureBase

# Feature imports - add these when features are implemented
# from features.todo.feature import TodoFeature
# from features.directions.feature import DirectionsFeature
# from features.translation.feature import TranslationFeature


def setup_logging() -> None:
    """Configure logging for the application."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('iris.log')
        ]
    )


def load_config() -> dict:
    """
    Load configuration from config.yaml and environment variables.
    
    Returns:
        Configuration dictionary
    """
    logger = logging.getLogger(__name__)
    
    # Load environment variables
    load_dotenv()
    
    # Load YAML config
    try:
        with open('config.yaml', 'r') as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        logger.error("config.yaml not found - please copy from config.yaml.example")
        sys.exit(1)
    except yaml.YAMLError as e:
        logger.error(f"Error parsing config.yaml: {e}")
        sys.exit(1)
    
    # Override with environment variables
    config['ip_webcam_url'] = os.getenv('IP_WEBCAM_URL', 'http://192.168.43.1:8080')
    config['pi_host'] = os.getenv('PI_HOST', config['pi']['host'])
    
    # API keys
    config['google_maps_api_key'] = os.getenv('GOOGLE_MAPS_API_KEY')
    config['deepl_api_key'] = os.getenv('DEEPL_API_KEY')
    config['openai_api_key'] = os.getenv('OPENAI_API_KEY')
    
    logger.info("Configuration loaded successfully")
    return config


def init_managers(config: dict) -> tuple:
    """
    Initialize core managers.
    
    Args:
        config: Configuration dictionary
        
    Returns:
        Tuple of (display, audio, camera, voice_trigger) managers
    """
    logger = logging.getLogger(__name__)
    
    # Initialize display manager
    display = DisplayManager(
        pi_host=config['pi_host'],
        pi_user=config['pi']['user'],
        display_server_path=config['pi']['display_server_path']
    )
    
    # Initialize audio manager
    audio_config = {
        'ip_webcam_url': config['ip_webcam_url'],
        'audio_path': config['ip_webcam']['audio_path'],
        'tts_path': config['ip_webcam']['tts_path']
    }
    audio = AudioManager(audio_config)
    
    # Initialize camera manager  
    camera_config = {
        'ip_webcam_url': config['ip_webcam_url'],
        'snapshot_path': config['ip_webcam']['snapshot_path'],
        'video_path': config['ip_webcam']['video_path']
    }
    camera = CameraManager(camera_config)
    
    # Initialize voice trigger
    voice_trigger = VoiceTrigger(
        audio_manager=audio,
        wake_word=config['voice']['wake_word']
    )
    
    logger.info("Core managers initialized")
    return display, audio, camera, voice_trigger


def register_features(display, audio, camera, config) -> Dict[str, FeatureBase]:
    """
    Register available features.
    
    Args:
        display: DisplayManager instance
        audio: AudioManager instance
        camera: CameraManager instance
        config: Configuration dictionary
        
    Returns:
        Dictionary mapping feature names to feature instances
    """
    features = {}
    
    # TODO: Register features when they are implemented
    # Example:
    # features["todo"] = TodoFeature(display, audio, camera, config)
    # features["directions"] = DirectionsFeature(display, audio, camera, config)
    # features["translation"] = TranslationFeature(display, audio, camera, config)
    
    logger = logging.getLogger(__name__)
    logger.info(f"Registered {len(features)} features: {list(features.keys())}")
    
    return features


def test_connections(display, audio, camera) -> bool:
    """
    Test connections to all hardware components.
    
    Args:
        display: DisplayManager instance
        audio: AudioManager instance
        camera: CameraManager instance
        
    Returns:
        True if all connections successful, False otherwise
    """
    logger = logging.getLogger(__name__)
    logger.info("Testing hardware connections...")
    
    success = True
    
    # Test display connection (Pi)
    if not display.connect():
        logger.error("Failed to connect to Pi display")
        success = False
    else:
        logger.info("✓ Pi display connection successful")
    
    # Test audio connection (phone)
    if not audio.test_connection():
        logger.error("Failed to connect to phone audio")
        success = False
    else:
        logger.info("✓ Phone audio connection successful")
    
    # Test camera connection (phone)
    if not camera.test_connection():
        logger.error("Failed to connect to phone camera")  
        success = False
    else:
        logger.info("✓ Phone camera connection successful")
    
    return success


def main_loop(display, audio, camera, voice_trigger, features) -> None:
    """
    Main application loop.
    
    Args:
        display: DisplayManager instance
        audio: AudioManager instance
        camera: CameraManager instance
        voice_trigger: VoiceTrigger instance
        features: Dictionary of available features
    """
    logger = logging.getLogger(__name__)
    logger.info("Starting main loop...")
    
    current_feature = None
    
    try:
        while True:
            # Show idle screen if no feature is active
            if current_feature is None:
                display.show_idle_screen()
            
            # Listen for voice commands
            try:
                logger.debug("Listening for voice command...")
                command = voice_trigger.listen_for_command(timeout=5)
                
                if command:
                    # Parse the command
                    parsed = voice_trigger.parse_command(command)
                    action = parsed["action"]
                    target = parsed["target"]
                    text = parsed["text"]
                    
                    logger.info(f"Command: action={action}, target={target}, text={text}")
                    
                    if action == "activate":
                        # Activate a feature
                        if target in features:
                            # Deactivate current feature if any
                            if current_feature:
                                current_feature.deactivate()
                            
                            # Activate new feature
                            current_feature = features[target]
                            current_feature.activate()
                            
                            logger.info(f"Activated feature: {target}")
                        else:
                            logger.warning(f"Unknown feature: {target}")
                            audio.speak(f"Unknown feature: {target}")
                            display.show_text(f"Unknown feature: {target}")
                            time.sleep(2)
                    
                    elif action == "stop":
                        # Deactivate current feature
                        if current_feature:
                            current_feature.deactivate()
                            current_feature = None
                            logger.info("Deactivated current feature")
                            audio.speak("Feature stopped")
                        else:
                            logger.info("No feature active to stop")
                    
                    elif action == "passthrough":
                        # Send command to active feature
                        if current_feature and text:
                            current_feature.process_voice(text)
                        else:
                            logger.warning("No active feature for passthrough command")
                            audio.speak("No active feature")
                    
                    else:
                        logger.warning(f"Unknown command action: {action}")
                
                # Update active feature if any
                if current_feature and current_feature.is_active:
                    try:
                        # Optionally grab camera frame for features that need it
                        frame = None
                        # Uncomment to provide camera frames to features:
                        # frame = camera.get_snapshot()
                        
                        # Process frame
                        current_feature.process_frame(frame)
                        
                        # Update display
                        current_feature.render()
                        
                    except Exception as e:
                        logger.error(f"Error updating active feature {current_feature.name}: {e}")
                        current_feature.handle_error(e, "main_loop_update")
                
            except KeyboardInterrupt:
                raise  # Re-raise to exit gracefully
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                # Continue running despite errors
                time.sleep(1)
    
    except KeyboardInterrupt:
        logger.info("Received interrupt signal, shutting down...")
    finally:
        # Cleanup
        if current_feature:
            current_feature.deactivate()
        display.disconnect()
        logger.info("Shutdown complete")


def main():
    """Main entry point."""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    logger.info("="*50)
    logger.info("Iris Smart Glasses - Starting Up")
    logger.info("="*50)
    
    try:
        # Load configuration
        config = load_config()
        
        # Initialize core managers
        display, audio, camera, voice_trigger = init_managers(config)
        
        # Register features
        features = register_features(display, audio, camera, config)
        
        # Test hardware connections
        if not test_connections(display, audio, camera):
            logger.warning("Some hardware connections failed - check configuration")
            # Continue anyway for development/testing
        
        # Show startup message
        audio.speak("Iris Smart Glasses ready")
        
        # Start main loop
        main_loop(display, audio, camera, voice_trigger, features)
        
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()