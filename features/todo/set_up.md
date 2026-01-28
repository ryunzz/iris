# Todo Feature Setup

Quick setup guide for adding the todo feature to your Iris smart glasses.

## Installation

1. **Copy the todo folder to your features directory:**
   ```bash
   cp -r todo /path/to/iris/features/
   ```

2. **Verify the structure:**
   ```
   iris/
   ├── core/
   │   ├── __init__.py
   │   ├── display.py
   │   ├── audio.py
   │   └── voice_trigger.py
   └── features/
       ├── directions/
       ├── translation/
       ├── weather/
       └── todo/          ← New!
           ├── __init__.py
           ├── todo.py
           ├── README.md
           ├── test_todo.py
           └── example_integration.py
   ```

3. **Test the feature:**
   ```bash
   cd features/todo
   python test_todo.py
   ```
   You should see: `ALL TESTS PASSED! ✓`

## Integration

### Option 1: Add to existing feature list

In your main application file (e.g., `main.py` or wherever you initialize features):

```python
from features.todo import TodoFeature

# Initialize with your display
todo = TodoFeature(display=display)

# Add to your features list
features = [
    todo,
    directions,
    translation,
    weather,
]
```

### Option 2: Add to voice handler

```python
from features.todo import TodoFeature

class VoiceHandler:
    def __init__(self, display, audio):
        self.display = display
        self.audio = audio
        self.todo = TodoFeature(display=display)
        # ... other features
    
    def on_voice_command(self, command):
        # Try todo feature
        feedback = self.todo.process_voice_command(command)
        if feedback:
            self.audio.speak(feedback)
            return
        
        # Try other features...
```

### Option 3: Feature Manager Pattern

```python
from features.todo import TodoFeature

class FeatureManager:
    def __init__(self, display):
        self.features = {}
        
        # Register features
        self.features['todo'] = TodoFeature(display=display)
        # self.features['weather'] = WeatherFeature(display=display)
        # ...
    
    def process_command(self, command):
        for name, feature in self.features.items():
            feedback = feature.process_voice_command(command)
            if feedback:
                return feedback
        return None
```

## Voice Commands

Once integrated, users can say:

- **"Hey Iris, activate todo"** - Start the todo list
- **"Add buy groceries"** - Add a new item
- **"Next"** - Move to next item
- **"Done"** - Mark current item complete
- **"Previous"** - Move to previous item
- **"Delete"** - Remove current item
- **"Clear done"** - Remove all completed items

## Display Integration

The feature automatically updates the display when commands are processed. It expects your display to have one of these methods:

- `display.show_text(text)` - Show text on display
- `display.show_lines(lines)` - Show list of lines

If your display uses a different API, modify the `update_display()` method in `todo.py`:

```python
def update_display(self) -> None:
    """Update the display with current todo list."""
    if self.display and self.active:
        lines = self.get_display_lines(max_lines=4)
        
        # Modify this to match your display API:
        self.display.your_method_here(lines)
```

## Customization

### Change Activation Phrase

Edit `todo.py`:
```python
ACTIVATION_PHRASE = "start todos"  # Line 29
```

### Change Display Symbols

Edit `todo.py`:
```python
CURSOR_SYMBOL = "→"      # Line 24
INCOMPLETE_SYMBOL = "☐"  # Line 25
COMPLETE_SYMBOL = "☑"    # Line 26
```

### Change Number of Display Lines

```python
lines = todo.get_display_lines(max_lines=6)  # Show 6 instead of 4
```

### Change Data File Location

```python
todo = TodoFeature(display=display, data_file="/path/to/todos.json")
```

## Troubleshooting

**Issue:** Module not found
```
Solution: Make sure __init__.py exists in the todo folder
```

**Issue:** Display not updating
```
Solution: Check that your display object is passed to TodoFeature(display=display)
```

**Issue:** Commands not recognized
```
Solution: Make sure feature is activated first with "activate todo"
```

**Issue:** Data not persisting
```
Solution: Check file permissions for todos.json in working directory
```

## Next Steps

1. ✅ Copy todo folder to features/
2. ✅ Run test: `python test_todo.py`
3. ✅ Add integration code to your main app
4. ✅ Test voice commands
5. 🚀 Deploy to glasses!

## Need Help?

Check the following files for more info:
- `README.md` - Feature documentation
- `example_integration.py` - Integration examples
- `test_todo.py` - Working test code