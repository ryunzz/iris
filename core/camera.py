"""
Iris Smart Glasses - Camera Manager

This module runs on the LT and captures video/images from the phone camera 
via IP Webcam.
"""

import requests
import cv2
import numpy as np
import logging
from typing import Optional
from urllib.parse import urljoin

logger = logging.getLogger(__name__)


class CameraManager:
    """Manages video/image capture from phone camera via IP Webcam."""
    
    def __init__(self, config: dict):
        """
        Initialize camera manager.
        
        Args:
            config: Configuration dict with IP Webcam settings
        """
        self.base_url = config.get('ip_webcam_url', 'http://192.168.43.1:8080')
        self.snapshot_path = config.get('snapshot_path', '/shot.jpg')
        self.video_path = config.get('video_path', '/video')
        
        # Request session for connection reuse
        self.session = requests.Session()
        
        logger.info(f"Initialized camera manager for {self.base_url}")
    
    def _get_snapshot_url(self) -> str:
        """Get the full URL for snapshot capture from IP Webcam."""
        return urljoin(self.base_url, self.snapshot_path)
    
    def _get_video_url(self) -> str:
        """Get the full URL for video stream from IP Webcam."""
        return urljoin(self.base_url, self.video_path)
    
    def get_snapshot(self) -> Optional[bytes]:
        """
        Capture a single JPEG snapshot from the phone camera.
        
        Returns:
            JPEG image data as bytes if successful, None otherwise
        """
        try:
            logger.debug("Capturing snapshot from phone camera...")
            
            snapshot_url = self._get_snapshot_url()
            
            response = self.session.get(snapshot_url, timeout=10)
            response.raise_for_status()
            
            # Verify we got image data
            if response.headers.get('content-type', '').startswith('image/'):
                logger.debug(f"Captured snapshot: {len(response.content)} bytes")
                return response.content
            else:
                logger.error(f"Unexpected content type: {response.headers.get('content-type')}")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to capture snapshot: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error capturing snapshot: {e}")
            return None
    
    def get_frame_cv2(self) -> Optional[np.ndarray]:
        """
        Get a snapshot as an OpenCV array for image processing.
        
        Returns:
            OpenCV image array (BGR format) if successful, None otherwise
        """
        try:
            # Get snapshot as bytes
            image_data = self.get_snapshot()
            if image_data is None:
                return None
            
            # Convert bytes to numpy array
            image_array = np.frombuffer(image_data, dtype=np.uint8)
            
            # Decode JPEG to OpenCV image
            image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
            
            if image is not None:
                logger.debug(f"Converted snapshot to OpenCV array: {image.shape}")
                return image
            else:
                logger.error("Failed to decode JPEG image")
                return None
                
        except Exception as e:
            logger.error(f"Error converting snapshot to OpenCV array: {e}")
            return None
    
    def save_snapshot(self, filename: str) -> bool:
        """
        Save a snapshot to a file.
        
        Args:
            filename: Path where to save the image
            
        Returns:
            True if saved successfully, False otherwise
        """
        try:
            image_data = self.get_snapshot()
            if image_data is None:
                logger.error("No image data to save")
                return False
            
            with open(filename, 'wb') as f:
                f.write(image_data)
            
            logger.info(f"Saved snapshot to {filename}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save snapshot to {filename}: {e}")
            return False
    
    def test_connection(self) -> bool:
        """
        Test connection to IP Webcam camera endpoint.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            snapshot_url = self._get_snapshot_url()
            response = self.session.get(snapshot_url, timeout=5)
            
            if response.status_code == 200 and response.headers.get('content-type', '').startswith('image/'):
                logger.info("IP Webcam camera connection test successful")
                return True
            else:
                logger.warning(f"IP Webcam camera test failed: status={response.status_code}, "
                             f"content-type={response.headers.get('content-type')}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"IP Webcam camera connection test failed: {e}")
            return False
    
    def get_camera_info(self) -> dict:
        """
        Get camera information and settings from IP Webcam.
        
        Returns:
            Dictionary with camera information
        """
        info = {
            'connected': False,
            'resolution': 'unknown',
            'format': 'unknown'
        }
        
        try:
            # Test basic connection
            if self.test_connection():
                info['connected'] = True
                
                # Try to get a snapshot to determine format
                snapshot = self.get_snapshot()
                if snapshot:
                    info['format'] = 'JPEG'
                    
                    # Try to get image dimensions
                    frame = self.get_frame_cv2()
                    if frame is not None:
                        height, width = frame.shape[:2]
                        info['resolution'] = f"{width}x{height}"
            
        except Exception as e:
            logger.error(f"Error getting camera info: {e}")
        
        return info
    
    def __del__(self):
        """Cleanup when object is destroyed."""
        try:
            if hasattr(self, 'session'):
                self.session.close()
        except Exception:
            pass  # Ignore errors during cleanup