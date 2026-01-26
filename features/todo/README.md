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