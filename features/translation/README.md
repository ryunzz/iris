# Translation Feature

Live text translation using camera OCR.

## Activation

"Hey Iris, activate translation"

## Voice Commands (while active)

- "translate" — Capture image and translate visible text
- "translate to [language]" — Set target language
- "read it" — Speak the translation via phone speaker

## Display Format

```
"Où est la gare?"

Where is the
train station?
```

- Original text in quotes on line 1
- Translation below

## Implementation Notes

- Uses camera snapshot for OCR
- OCR via Tesseract or Google Vision API
- Translation via DeepL or Google Translate
- Requires DEEPL_API_KEY in .env
- "read it" sends TTS audio to phone speaker via 2-way audio