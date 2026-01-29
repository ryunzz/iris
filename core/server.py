#!/usr/bin/env python3
"""
Flask server for Iris Smart Glasses.

Receives motion alerts and other interrupts from ESP32 devices.
Handles interrupts in thread-safe manner using event queue.
"""

import logging
import threading
import queue
from datetime import datetime
from enum import Enum
from dataclasses import dataclass
from typing import Dict, Any, Optional, Callable

from flask import Flask, request, jsonify


logger = logging.getLogger(__name__)


class InterruptType(Enum):
    """Types of interrupts that can be received."""
    MOTION = "motion"
    DEVICE_OFFLINE = "device_offline"
    DEVICE_ONLINE = "device_online"
    SYSTEM_ERROR = "system_error"


@dataclass
class Interrupt:
    """Represents an interrupt event."""
    type: InterruptType
    data: Dict[str, Any]
    timestamp: datetime
    source_ip: str = ""


class InterruptManager:
    """Thread-safe interrupt handling with event queue."""
    
    def __init__(self, max_queue_size: int = 100):
        self._queue = queue.Queue(maxsize=max_queue_size)
        self._handlers: Dict[InterruptType, Callable[[Interrupt], None]] = {}
        self._running = True
        
        logger.info("Interrupt manager initialized")
    
    def push(self, interrupt: Interrupt) -> bool:
        """
        Push an interrupt to the queue (called from Flask thread).
        
        Args:
            interrupt: Interrupt event to queue
            
        Returns:
            True if queued successfully, False if queue full
        """
        if not self._running:
            return False
        
        try:
            self._queue.put_nowait(interrupt)
            logger.info(f"Queued interrupt: {interrupt.type.value} from {interrupt.source_ip}")
            return True
        except queue.Full:
            logger.error(f"Interrupt queue full, dropping {interrupt.type.value}")
            return False
    
    def poll(self) -> Optional[Interrupt]:
        """
        Poll for next interrupt (called from main loop - non-blocking).
        
        Returns:
            Next interrupt or None if queue empty
        """
        if not self._running:
            return None
        
        try:
            return self._queue.get_nowait()
        except queue.Empty:
            return None
    
    def wait_for_interrupt(self, timeout: float = None) -> Optional[Interrupt]:
        """
        Wait for next interrupt (blocking with timeout).
        
        Args:
            timeout: Maximum time to wait in seconds
            
        Returns:
            Next interrupt or None if timeout
        """
        if not self._running:
            return None
        
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None
    
    def register_handler(self, interrupt_type: InterruptType, 
                        handler: Callable[[Interrupt], None]) -> None:
        """
        Register handler for specific interrupt type.
        
        Args:
            interrupt_type: Type of interrupt to handle
            handler: Function to call when interrupt occurs
        """
        self._handlers[interrupt_type] = handler
        logger.info(f"Registered handler for {interrupt_type.value}")
    
    def process_interrupt(self, interrupt: Interrupt) -> None:
        """
        Process an interrupt by calling registered handler.
        
        Args:
            interrupt: Interrupt to process
        """
        handler = self._handlers.get(interrupt.type)
        if handler:
            try:
                handler(interrupt)
            except Exception as e:
                logger.error(f"Error in interrupt handler for {interrupt.type.value}: {e}")
        else:
            logger.debug(f"No handler for interrupt type {interrupt.type.value}")
    
    def get_queue_size(self) -> int:
        """Get current queue size."""
        return self._queue.qsize()
    
    def clear_queue(self) -> int:
        """
        Clear all pending interrupts.
        
        Returns:
            Number of interrupts cleared
        """
        count = 0
        while True:
            try:
                self._queue.get_nowait()
                count += 1
            except queue.Empty:
                break
        
        logger.info(f"Cleared {count} pending interrupts")
        return count
    
    def stop(self) -> None:
        """Stop the interrupt manager."""
        self._running = False
        logger.info("Interrupt manager stopped")


# Global interrupt manager instance
interrupt_manager: Optional[InterruptManager] = None


def create_app(manager: InterruptManager) -> Flask:
    """
    Create Flask application with interrupt endpoints.
    
    Args:
        manager: InterruptManager instance
        
    Returns:
        Configured Flask app
    """
    app = Flask(__name__)
    
    # Disable Flask logging for cleaner output
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    
    @app.route('/motion', methods=['POST'])
    def motion_alert():
        """Receive motion alert from ESP32."""
        try:
            # Get client IP
            client_ip = request.remote_addr
            
            # Get JSON data (may be empty)
            data = request.get_json() or {}
            
            # Create interrupt
            interrupt = Interrupt(
                type=InterruptType.MOTION,
                data=data,
                timestamp=datetime.now(),
                source_ip=client_ip
            )
            
            # Queue interrupt
            if manager.push(interrupt):
                logger.info(f"Motion alert from {client_ip}")
                return jsonify({"received": True, "status": "queued"})
            else:
                logger.error(f"Failed to queue motion alert from {client_ip}")
                return jsonify({"received": False, "status": "queue_full"}), 503
                
        except Exception as e:
            logger.error(f"Error processing motion alert: {e}")
            return jsonify({"received": False, "error": str(e)}), 500
    
    @app.route('/device_status', methods=['POST'])
    def device_status():
        """Receive device status updates."""
        try:
            client_ip = request.remote_addr
            data = request.get_json() or {}
            
            device_type = data.get('type', 'unknown')
            status = data.get('status', 'unknown')
            
            # Determine interrupt type
            if status == 'online':
                interrupt_type = InterruptType.DEVICE_ONLINE
            elif status == 'offline':
                interrupt_type = InterruptType.DEVICE_OFFLINE
            else:
                logger.warning(f"Unknown device status: {status}")
                return jsonify({"received": False, "error": "unknown status"}), 400
            
            interrupt = Interrupt(
                type=interrupt_type,
                data=data,
                timestamp=datetime.now(),
                source_ip=client_ip
            )
            
            if manager.push(interrupt):
                logger.info(f"Device status from {client_ip}: {device_type} {status}")
                return jsonify({"received": True})
            else:
                return jsonify({"received": False, "status": "queue_full"}), 503
                
        except Exception as e:
            logger.error(f"Error processing device status: {e}")
            return jsonify({"received": False, "error": str(e)}), 500
    
    @app.route('/health', methods=['GET'])
    def health():
        """Health check endpoint."""
        return jsonify({
            "status": "ok",
            "service": "iris-glasses-server",
            "timestamp": datetime.now().isoformat(),
            "queue_size": manager.get_queue_size()
        })
    
    @app.route('/interrupt/clear', methods=['POST'])
    def clear_interrupts():
        """Clear interrupt queue (for debugging)."""
        count = manager.clear_queue()
        return jsonify({"cleared": count})
    
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({"error": "endpoint not found"}), 404
    
    @app.errorhandler(500)
    def server_error(error):
        return jsonify({"error": "server error"}), 500
    
    return app


def start_server(manager: InterruptManager, host: str = '0.0.0.0', port: int = 5000) -> threading.Thread:
    """
    Start Flask server in background thread.
    
    Args:
        manager: InterruptManager instance
        host: Server host (default: all interfaces)
        port: Server port
        
    Returns:
        Thread object running the server
    """
    global interrupt_manager
    interrupt_manager = manager
    
    app = create_app(manager)
    
    def run_server():
        try:
            logger.info(f"Starting Flask server on {host}:{port}")
            app.run(host=host, port=port, debug=False, threaded=True)
        except Exception as e:
            logger.error(f"Flask server error: {e}")
    
    server_thread = threading.Thread(
        target=run_server,
        daemon=True,
        name="FlaskServer"
    )
    
    server_thread.start()
    logger.info(f"Flask server started in background thread")
    
    return server_thread


if __name__ == "__main__":
    # Test server functionality
    import time
    import requests
    import sys
    
    logging.basicConfig(level=logging.INFO)
    
    print("Testing Flask server with interrupt handling...")
    
    # Create interrupt manager
    manager = InterruptManager()
    
    # Register test handlers
    def handle_motion(interrupt: Interrupt):
        print(f"🚨 Motion detected from {interrupt.source_ip} at {interrupt.timestamp}")
    
    def handle_device_status(interrupt: Interrupt):
        status = interrupt.data.get('status', 'unknown')
        device = interrupt.data.get('type', 'unknown')
        print(f"📱 Device {device} is {status}")
    
    manager.register_handler(InterruptType.MOTION, handle_motion)
    manager.register_handler(InterruptType.DEVICE_ONLINE, handle_device_status)
    manager.register_handler(InterruptType.DEVICE_OFFLINE, handle_device_status)
    
    # Start server
    server_thread = start_server(manager, port=5001)  # Use different port for testing
    
    # Give server time to start
    time.sleep(2)
    
    print("\n--- Testing endpoints ---")
    
    try:
        # Test health endpoint
        response = requests.get('http://localhost:5001/health')
        print(f"Health check: {response.json()}")
        
        # Test motion alert
        response = requests.post('http://localhost:5001/motion', json={})
        print(f"Motion alert response: {response.json()}")
        
        # Test device status
        response = requests.post('http://localhost:5001/device_status', json={
            'type': 'light',
            'status': 'online'
        })
        print(f"Device status response: {response.json()}")
        
        # Process interrupts
        print("\n--- Processing interrupts ---")
        for _ in range(10):  # Try for up to 1 second
            interrupt = manager.poll()
            if interrupt:
                manager.process_interrupt(interrupt)
            else:
                time.sleep(0.1)
        
        # Test queue clearing
        response = requests.post('http://localhost:5001/interrupt/clear')
        print(f"Clear queue response: {response.json()}")
        
    except requests.ConnectionError:
        print("❌ Could not connect to server")
    except Exception as e:
        print(f"❌ Test error: {e}")
    
    print("\nServer test complete. Server is still running in background.")
    print("Press Ctrl+C to exit")
    
    try:
        # Keep main thread alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")
        manager.stop()