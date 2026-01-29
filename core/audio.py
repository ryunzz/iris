#!/usr/bin/env python3
"""
Pluggable audio sources for Iris Smart Glasses.

Supports multiple audio input sources:
- MockAudio: Keyboard input for testing
- LaptopMicAudio: Built-in microphone (works everywhere)
- IPWebcamAudio: Android IP Webcam app (Texas team)
"""

import logging
import requests
import io
import time
from abc import ABC, abstractmethod
from typing import Optional

try:
    import speech_recognition as sr
    SPEECH_RECOGNITION_AVAILABLE = True
except ImportError:
    SPEECH_RECOGNITION_AVAILABLE = False
    logging.warning("speech_recognition not available - laptop mic will not work")


logger = logging.getLogger(__name__)


class AudioSource(ABC):
    """Abstract base class for audio input sources."""
    
    @abstractmethod
    def listen(self, timeout: float = 5.0) -> Optional[str]:
        """Listen for speech and return transcript, or None if nothing heard."""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if this audio source is available."""
        pass


class MockAudio(AudioSource):
    """Keyboard input for testing without any microphone."""
    
    def listen(self, timeout: float = 5.0) -> Optional[str]:
        try:
            text = input("Say: ").strip()
            return text if text else None
        except EOFError:
            return None
        except KeyboardInterrupt:
            return None
    
    def is_available(self) -> bool:
        return True  # Always available


class LaptopMicAudio(AudioSource):
    """
    Use laptop's built-in microphone directly.
    Works on Mac, Windows, Linux - no phone needed.
    Good for: iPhone users, quick testing, demos without phone setup.
    """
    
    def __init__(self):
        self.recognizer = None
        self.microphone = None
        
        if not SPEECH_RECOGNITION_AVAILABLE:
            logger.error("speech_recognition not available - cannot use laptop mic")
            return
        
        # Initialize speech recognition
        try:
            self.recognizer = sr.Recognizer()
            self.microphone = sr.Microphone()
            
            # Adjust for ambient noise on init
            with self.microphone as source:
                logger.info("Calibrating microphone for ambient noise...")
                self.recognizer.adjust_for_ambient_noise(source, duration=1)
                logger.info("✅ Laptop microphone ready")
                
        except Exception as e:
            logger.error(f"⚠️ Microphone init failed: {e}")
            self.recognizer = None
            self.microphone = None
    
    def listen(self, timeout: float = 5.0) -> Optional[str]:
        if not self.recognizer or not self.microphone:
            return None
            
        try:
            with self.microphone as source:
                logger.debug("Listening for speech...")
                
                # Listen for speech with timeout
                audio = self.recognizer.listen(source, timeout=timeout, phrase_time_limit=10)
                
                logger.debug("Converting speech to text...")
                
                # Transcribe using Google Speech Recognition (free, no API key)
                transcript = self.recognizer.recognize_google(audio)
                result = transcript.lower().strip()
                
                logger.info(f"Recognized: '{result}'")
                return result
                
        except sr.WaitTimeoutError:
            logger.debug("No speech detected within timeout")
            return None
        except sr.UnknownValueError:
            logger.debug("Speech not understood")
            return None
        except sr.RequestError as e:
            logger.warning(f"Speech recognition error: {e}")
            return None
        except Exception as e:
            logger.warning(f"Audio capture error: {e}")
            return None
    
    def is_available(self) -> bool:
        return self.recognizer is not None and self.microphone is not None


class IPWebcamAudio(AudioSource):
    """
    Stream audio from Android phone running IP Webcam app.
    Used by: Texas team with Samsung phone.
    
    Setup:
    1. Install "IP Webcam" app on Android phone
    2. Connect phone to same WiFi/hotspot as laptop
    3. Start server in app, note the IP address
    4. Pass IP to this class
    """
    
    # IP Webcam audio endpoints in order of preference
    ENDPOINTS = [
        "/audio.wav",      # WAV stream (best quality)
        "/audio.opus",     # Opus (lower bandwidth)
        "/audio.aac",      # AAC
    ]
    
    def __init__(self, phone_ip: str, port: int = 8080):
        self.phone_ip = phone_ip
        self.port = port
        self.base_url = f"http://{phone_ip}:{port}"
        self.working_endpoint = None
        self.recognizer = None
        
        if SPEECH_RECOGNITION_AVAILABLE:
            self.recognizer = sr.Recognizer()
        
        self._find_working_endpoint()
    
    def _find_working_endpoint(self):
        """Test endpoints to find one that works."""        
        for endpoint in self.ENDPOINTS:
            url = f"{self.base_url}{endpoint}"
            try:
                resp = requests.head(url, timeout=2)
                if resp.status_code == 200:
                    self.working_endpoint = endpoint
                    logger.info(f"✅ Using IP Webcam audio: {endpoint}")
                    return
            except Exception as e:
                logger.debug(f"Endpoint {endpoint} failed: {e}")
                continue
        
        logger.warning(f"⚠️ No working audio endpoint found at {self.base_url}")
        logger.warning("   Make sure IP Webcam is running on the phone")
    
    def listen(self, timeout: float = 5.0) -> Optional[str]:
        if not self.recognizer:
            logger.error("speech_recognition not available")
            return None
            
        if not self.working_endpoint:
            # Retry finding endpoint
            self._find_working_endpoint()
            if not self.working_endpoint:
                return None
        
        try:
            # Get audio from IP Webcam
            url = f"{self.base_url}{self.working_endpoint}"
            
            logger.debug(f"Capturing audio from {url}...")
            
            # Method: Capture a chunk of audio and recognize it
            response = requests.get(url, stream=True, timeout=timeout)
            response.raise_for_status()
            
            # Read audio data
            audio_data = io.BytesIO()
            
            # Read audio for specified duration
            start_time = time.time()
            for chunk in response.iter_content(chunk_size=1024):
                audio_data.write(chunk)
                
                # Stop after timeout or reasonable amount of data
                if time.time() - start_time > timeout or audio_data.tell() > 1024 * 1024:  # 1MB max
                    break
            
            response.close()
            audio_data.seek(0)
            
            # Check if we got any data
            if audio_data.tell() == 0:
                logger.debug("No audio data received")
                return None
            
            logger.debug("Converting speech to text...")
            
            # Recognize using speech_recognition
            with sr.AudioFile(audio_data) as source:
                audio = self.recognizer.record(source)
                transcript = self.recognizer.recognize_google(audio)
                result = transcript.lower().strip()
                
                logger.info(f"Recognized: '{result}'")
                return result
                
        except requests.RequestException as e:
            logger.debug(f"HTTP request failed: {e}")
            return None
        except sr.UnknownValueError:
            logger.debug("Speech not understood")
            return None
        except sr.RequestError as e:
            logger.warning(f"Speech recognition error: {e}")
            return None
        except Exception as e:
            logger.debug(f"Audio capture error: {e}")
            return None
    
    def is_available(self) -> bool:
        return (
            SPEECH_RECOGNITION_AVAILABLE and
            self.recognizer is not None and
            self.working_endpoint is not None
        )


def create_audio_source(source_type: str, phone_ip: str = None) -> AudioSource:
    """
    Factory function to create the appropriate audio source.
    
    Args:
        source_type: "mock", "laptop", or "ipwebcam"
        phone_ip: Required if source_type is "ipwebcam"
    
    Returns:
        AudioSource instance
    """
    if source_type == "mock":
        logger.info("Audio source: Keyboard input (mock)")
        return MockAudio()
    
    elif source_type == "laptop":
        logger.info("Audio source: Laptop microphone")
        return LaptopMicAudio()
    
    elif source_type == "ipwebcam":
        if not phone_ip:
            raise ValueError("phone_ip required for ipwebcam audio source")
        logger.info(f"Audio source: IP Webcam at {phone_ip}")
        return IPWebcamAudio(phone_ip)
    
    else:
        raise ValueError(f"Unknown audio source: {source_type}")


if __name__ == "__main__":
    # Test audio sources
    import sys
    import time
    
    logging.basicConfig(level=logging.INFO)
    
    if "--mock" in sys.argv:
        print("Testing mock audio...")
        audio = MockAudio()
    elif "--laptop" in sys.argv:
        print("Testing laptop microphone...")
        audio = LaptopMicAudio()
    elif len(sys.argv) > 1 and sys.argv[1].startswith("192.168."):
        # IP address provided
        print(f"Testing IP Webcam at {sys.argv[1]}...")
        audio = IPWebcamAudio(sys.argv[1])
    else:
        print("Usage:")
        print("  python audio.py --mock          # Test keyboard input")
        print("  python audio.py --laptop        # Test laptop microphone")  
        print("  python audio.py 192.168.43.1    # Test IP Webcam")
        sys.exit(1)
    
    if not audio.is_available():
        print("❌ Audio source not available")
        sys.exit(1)
    
    print("✅ Audio source available")
    print("Listening for speech (5 second timeout)...")
    
    for i in range(3):
        print(f"\nTest {i+1}/3:")
        result = audio.listen(timeout=5.0)
        
        if result:
            print(f"Heard: '{result}'")
        else:
            print("No speech detected")
        
        time.sleep(1)
    
    print("\nAudio test complete")