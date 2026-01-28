# test_socket_display.py
import socket
import time

PI_HOST = "10.194.126.184"  # ← Put your actual Pi IP
PORT = 5555

def send_display(text):
    """Send text to display server."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((PI_HOST, PORT))
        sock.send(text.encode('utf-8'))
        sock.close()
        return True
    except Exception as e:
        print(f"Error: {e}")
        return False

def clear_display():
    """Clear the OLED display."""
    send_display("|||")
    print("✅ Display cleared!")

# Interactive mode
print("Interactive OLED Display Control")
print("Commands:")
print("  clear - Clear the display")
print("  test - Send test lines")
print("  todo - Show todo example")
print("  [text] - Display custom text (use | for line breaks)")
print("  quit - Exit")
print()

while True:
    command = input("> ").strip()
    
    if command == "quit":
        break
    
    elif command == "clear":
        clear_display()
    
    elif command == "test":
        print("Sending test lines...")
        send_display("Line 1|Line 2|Line 3|Line 4")
    
    elif command == "todo":
        print("Sending todo example...")
        send_display("> O Buy groceries|  V Call mom|  O Send email|")
    
    elif command:
        # Send custom text
        send_display(command)
        print("✅ Sent!")
    
    time.sleep(0.1)

print("Goodbye!")