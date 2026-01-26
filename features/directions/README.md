# Directions Feature

Turn-by-turn navigation displayed on OLED.

## Activation

"Hey Iris, activate directions"

## Voice Commands (while active)

- "navigate to [destination]" — Start navigation
- "next" — Show next step
- "repeat" — Repeat current instruction
- "cancel" — Stop navigation

## Display Format

```
↱ Turn right on
  Main Street

  500 ft
```

- Arrow indicates turn direction: ↑ ↓ ← → ↱ ↲ ↰ ↳
- Street name on line 2
- Distance on line 4

## Implementation Notes

- Uses Google Maps Directions API
- Requires GOOGLE_MAPS_API_KEY in .env
- Cache route, step through instructions locally