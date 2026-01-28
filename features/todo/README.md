# Todo Feature

Voice-controlled todo list displayed on OLED.

## Activation

"Hey Iris, activate todo"

## Voice Commands (while active)

- "add [item]" — Add a new todo item
- "done" / "complete" — Mark current item complete
- "next" — Move cursor down
- "previous" / "back" — Move cursor up
- "delete" — Remove current item
- "clear done" — Remove all completed items

## Display Format

```
> ○ Buy groceries
  ✓ Call mom
  ○ Send email
  ○ Fix bug
```

- `>` indicates cursor position
- `○` uncomplete, `✓` complete
- Shows 4 items max, scrolls with cursor

## Implementation Notes

- Store todos in local JSON file
- Cursor wraps around
- New items added at bottom

#===================================================================
#========================  UPDATED readme   ========================
# Todo Feature

Voice-controlled todo list displayed on OLED.

## Activation

```
"Hey Iris, activate todo"
```

## Voice Commands (while active)

- **`add [item]`** — Add a new todo item
- **`done`** / **`complete`** — Mark current item complete
- **`next`** — Move cursor down
- **`previous`** / **`back`** — Move cursor up
- **`delete`** — Remove current item
- **`clear done`** — Remove all completed items

## Display Format

```
> ○ Buy groceries
  ✓ Call mom
  ○ Send email
  ○ Fix bug
```

- `>` indicates cursor position
- `○` uncomplete, `✓` complete
- Shows 4 items max, scrolls with cursor

## Usage

### Import the feature

```python
from features.todo import TodoFeature
```

### Initialize with display

```python
# Assuming you have a display object
todo = TodoFeature(display=display)
```

### Process voice commands

```python
def on_voice_command(command):
    feedback = todo.process_voice_command(command)
    if feedback:
        # Speak the feedback
        audio.speak(feedback)
        # Display updates automatically
```

### Or manually update display

```python
lines = todo.get_display_lines(max_lines=4)
display.show_lines(lines)
```

## Integration Example

```python
# In your main voice handler
from features.todo import TodoFeature

class VoiceHandler:
    def __init__(self, display):
        self.todo = TodoFeature(display=display)
    
    def handle_command(self, command):
        # Try todo feature
        feedback = self.todo.process_voice_command(command)
        
        if feedback:
            self.speak(feedback)
            return True
        
        # Try other features...
        return False
```

## API

### Methods

- `process_voice_command(command: str) -> Optional[str]` - Process command, returns feedback
- `get_display_lines(max_lines: int = 4) -> List[str]` - Get formatted display lines
- `activate() -> str` - Activate feature
- `deactivate() -> str` - Deactivate feature
- `is_active() -> bool` - Check if active
- `get_stats() -> Dict[str, int]` - Get todo statistics

### Properties

- `active: bool` - Whether feature is active
- `todos: List[TodoItem]` - List of todo items
- `cursor_index: int` - Current cursor position

## Data Storage

Todos are stored in `todos.json`:

```json
[
  {
    "text": "Buy groceries",
    "completed": false
  },
  {
    "text": "Call mom",
    "completed": true
  }
]
```

## Customization

### Change symbols

```python
TodoFeature.CURSOR_SYMBOL = "→"
TodoFeature.INCOMPLETE_SYMBOL = "☐"
TodoFeature.COMPLETE_SYMBOL = "☑"
```

### Change activation phrase

```python
TodoFeature.ACTIVATION_PHRASE = "start todos"
```

### Change display size

```python
lines = todo.get_display_lines(max_lines=6)  # Show 6 items
```

## Features

✅ Voice-controlled  
✅ Persistent storage (JSON)  
✅ Cursor navigation with wrapping  
✅ Mark complete/incomplete  
✅ Delete individual or all completed items  
✅ Scrolling display (4 items)  
✅ Audio feedback  
✅ No external dependencies