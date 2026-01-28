"""
Test Todo Feature with Socket Display (No Terminal 1 Needed!) <-- previously, needed ssh terminal to set up display (still need to but less cumbersome)

This test uses SocketDisplayAdapter instead of DisplayManager,
so you don't need to manually run display_server on the Pi.
"""

import sys
import time

# Add project root to path
sys.path.insert(0, '.')

from features.todo import TodoFeature
from socket_display_adapter import SocketDisplayAdapter

# Configuration
PI_HOST = "10.194.126.184"  # ← CHANGE THIS to your Pi's IP
PI_PORT = 5555

class MockAudio:
    """Mock audio manager that prints instead of speaking."""
    def speak(self, text):
        print(f"🔊 AUDIO: {text}")

class MockCamera:
    """Mock camera manager."""
    pass

def main():
    """Test todo feature with socket display."""
    print("="*60)
    print("TODO FEATURE TEST (Socket Display - No Terminal 1 Needed!)")
    print("="*60)
    print()
    
    # Create socket display adapter
    print(f"Connecting to Pi display at {PI_HOST}:{PI_PORT}...")
    display = SocketDisplayAdapter(pi_host=PI_HOST, pi_port=PI_PORT)
    
    # Test connection
    if not display.connect():
        print("❌ Could not connect to Pi display server!")
        print()
        print("Make sure:")
        print(f"  1. Display server is running on Pi: python pi/display_server_socket.py")
        print(f"  2. Pi IP is correct: {PI_HOST}")
        print(f"  3. Port 5555 is open on Pi firewall")
        print()
        print("Or set up systemd service (see documentation)")
        return 1
    
    print("✅ Connected to display server!\n")
    
    # Create todo feature with socket display
    config = {'todo_data_file': 'test_todos.json'}
    audio = MockAudio()
    camera = MockCamera()
    
    todo = TodoFeature(display, audio, camera, config)
    
    print("🎉 Testing TODO feature on OLED!\n")
    
    try:
        # Test sequence
        input("Press Enter to activate todo feature...")
        todo.activate()
        time.sleep(1)
        
        input("Press Enter to add 'buy groceries'...")
        todo.process_voice("add buy groceries")
        time.sleep(1)
        
        input("Press Enter to add 'call mom'...")
        todo.process_voice("add call mom")
        time.sleep(1)
        
        input("Press Enter to add 'send email'...")
        todo.process_voice("add send email to team about the meeting")
        time.sleep(1)
        
        input("Press Enter to navigate to next item...")
        todo.process_voice("next")
        time.sleep(1)
        
        input("Press Enter to mark current item done...")
        todo.process_voice("done")
        time.sleep(1)
        
        input("Press Enter to navigate next again...")
        todo.process_voice("next")
        time.sleep(1)
        
        input("Press Enter to delete current item...")
        todo.process_voice("delete")
        time.sleep(1)
        
        input("Press Enter to add one more item...")
        todo.process_voice("add fix bug in code")
        time.sleep(1)
        
        input("Press Enter to clear completed items...")
        todo.process_voice("clear done")
        time.sleep(1)
        
        input("Press Enter to deactivate...")
        todo.deactivate()
        
        print("\n✅ Test complete! Your todo feature works perfectly! 🎉")
        print("No Terminal 1 needed - display server runs independently!")
        
    except KeyboardInterrupt:
        print("\n\nTest interrupted")
        todo.deactivate()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())