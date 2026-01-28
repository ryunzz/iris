# test_todo_real_final.py
import socket
import time
from features.todo import TodoFeature

PI_HOST = "10.194.126.184"  # ← Put your real Pi IP here!
PORT = 5555

class SocketDisplay:
    """Display that sends to socket server."""
    
    def __init__(self, host, port):
        self.host = host
        self.port = port
    
    def show_lines(self, lines):
        """Send lines to socket display."""
        try:
            # Join with pipe delimiter
            text = "|".join(lines[:4])  # Max 4 lines
            
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((self.host, self.port))
            sock.send(text.encode('utf-8'))
            sock.close()
            return True
        except Exception as e:
            print(f"Display error: {e}")
            return False

class MockAudio:
    def speak(self, text):
        print(f"🔊 {text}")

class MockCamera:
    pass

# Create feature with socket display
config = {'todo_data_file': 'test_todos.json'}
display = SocketDisplay(PI_HOST, PORT)
audio = MockAudio()
camera = MockCamera()

todo = TodoFeature(display, audio, camera, config)

print("🎉 Testing TODO on real OLED!\n")

input("Press Enter to activate...")
todo.activate()

input("Press Enter to add 'buy groceries'...")
todo.process_voice("add buy groceries")

input("Press Enter to add 'call mom'...")
todo.process_voice("add call mom")

input("Press Enter to add 'send email'...")
todo.process_voice("add send email to team")

input("Press Enter to navigate next...")
todo.process_voice("next")

input("Press Enter to mark done...")
todo.process_voice("done")

input("Press Enter to navigate next...")
todo.process_voice("next")

print("\n✅ Test complete! Your todo feature works on the OLED! 🎉")