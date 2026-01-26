"""
Iris Smart Glasses - Audio Manager

This module runs on the laptop and handles audio I/O with the phone:
- Captures audio from phone microphone via IP Webcam
- Converts speech to text
- Sends TTS audio back to phone speaker via IP Webcam 2-way audio
"""

import requests
import speech_recognition as sr
import pyttsx3
import io
import logging
from typing import Optional
from urllib.parse import urljoin
import tempfile
import os

logger = logging.getLogger(__name__)


class AudioManager:
    """Manages audio capture from phone and TTS output to phone."""
    
    def __init__(self, config: dict):
        """
        Initialize audio manager.
        
        Args:
            config: Configuration dict with IP Webcam settings
        """
        self.base_url = config.get('ip_webcam_url', 'http://192.168.43.1:8080')
        self.audio_path = config.get('audio_path', '/audio.wav')
        self.tts_path = config.get('tts_path', '/audio.wav')
        
        # Initialize speech recognition
        self.recognizer = sr.Recognizer()
        
        # Initialize TTS engine
        self.tts_engine = pyttsx3.init()
        self.tts_engine.setProperty('rate', 150)  # Speaking rate
        self.tts_engine.setProperty('volume', 0.9)  # Volume level
        
        logger.info(f"Initialized audio manager for {self.base_url}")
    
    def _get_audio_url(self) -> str:
        """Get the full URL for audio capture from IP Webcam."""
        return urljoin(self.base_url, self.audio_path)
    
    def _get_tts_url(self) -> str:
        """Get the full URL for TTS audio upload to IP Webcam."""
        # TODO: Verify exact endpoint for 2-way audio in Thyoni Tech IP Webcam app
        # This is a placeholder - needs to be tested with the actual app
        return urljoin(self.base_url, self.tts_path)
    
    def listen(self, timeout: int = 5) -> Optional[str]:
        """
        Capture audio from phone microphone and convert to text.
        
        Args:
            timeout: Maximum time to wait for audio (seconds)
            
        Returns:
            Transcript string if successful, None otherwise
        """
        try:
            logger.debug("Capturing audio from phone...")
            
            # Get audio stream from IP Webcam
            audio_url = self._get_audio_url()
            
            response = requests.get(audio_url, timeout=timeout)
            response.raise_for_status()
            
            # Create audio data from response
            audio_data = io.BytesIO(response.content)
            
            # Use speech recognition to convert to text
            with sr.AudioFile(audio_data) as source:
                # Adjust for ambient noise
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                
                # Record the audio
                audio = self.recognizer.record(source)
                
                logger.debug("Converting speech to text...")
                
                # Recognize speech using Google Web Speech API
                transcript = self.recognizer.recognize_google(audio)
                
                logger.info(f"Recognized speech: '{transcript}'")
                return transcript.strip().lower()
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to capture audio from phone: {e}")
            return None
        except sr.UnknownValueError:
            logger.debug("Could not understand audio")
            return None
        except sr.RequestError as e:
            logger.error(f"Speech recognition error: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in audio capture: {e}")
            return None
    
    def speak(self, text: str) -> bool:
        """
        Convert text to speech and send to phone speaker.
        
        Args:
            text: Text to speak
            
        Returns:
            True if successful, False otherwise
        """
        if not text.strip():
            logger.warning("No text to speak")
            return False
        
        try:
            logger.info(f"Speaking text: '{text}'")
            
            # Create temporary file for TTS audio
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                temp_path = temp_file.name
            
            try:
                # Generate TTS audio to file
                self.tts_engine.save_to_file(text, temp_path)
                self.tts_engine.runAndWait()
                
                # Read the generated audio file
                with open(temp_path, 'rb') as audio_file:
                    audio_data = audio_file.read()
                
                # Send audio to phone via IP Webcam 2-way audio
                tts_url = self._get_tts_url()
                
                # TODO: Verify the correct HTTP method and headers for 2-way audio upload
                # This may need to be a POST with multipart/form-data or specific headers
                response = requests.post(
                    tts_url,
                    files={'audio': ('tts.wav', audio_data, 'audio/wav')},
                    timeout=10
                )
                
                if response.status_code == 200:
                    logger.info("Successfully sent TTS audio to phone")
                    return True
                else:
                    logger.warning(f"TTS upload returned status {response.status_code}")
                    # Fallback: play locally for testing
                    logger.info("Fallback: Playing TTS locally")
                    self._play_locally(text)
                    return True
                    
            finally:
                # Clean up temporary file
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                    
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send TTS audio to phone: {e}")
            # Fallback: play locally
            self._play_locally(text)
            return False
        except Exception as e:
            logger.error(f"TTS error: {e}")
            return False
    
    def _play_locally(self, text: str) -> None:
        """
        Fallback method to play TTS locally on laptop.
        
        Args:
            text: Text to speak
        """
        try:
            logger.info("Playing TTS audio locally as fallback")
            self.tts_engine.say(text)
            self.tts_engine.runAndWait()
        except Exception as e:
            logger.error(f"Local TTS playback failed: {e}")
    
    def test_connection(self) -> bool:
        """
        Test connection to IP Webcam audio endpoint.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            audio_url = self._get_audio_url()
            response = requests.get(audio_url, timeout=5)
            
            if response.status_code == 200:
                logger.info("IP Webcam audio connection test successful")
                return True
            else:
                logger.warning(f"IP Webcam returned status {response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"IP Webcam connection test failed: {e}")
            return False