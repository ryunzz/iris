#!/usr/bin/env python3
"""
Live translation feature for Iris Smart Glasses.

Provides real-time translation using DeepL API with mock mode support.
"""

import logging
import os
from typing import Optional, Dict, Any, List
import time

try:
    import deepl
    DEEPL_AVAILABLE = True
except ImportError:
    DEEPL_AVAILABLE = False
    logging.warning("deepl not available - translation will use mock mode")


logger = logging.getLogger(__name__)


class Translator:
    """
    Live translation service for continuous speech translation.
    """
    
    def __init__(self, mock: bool = False, api_key: str = None, 
                 source_lang: str = "en", target_lang: str = "fr"):
        self.mock = mock
        self.api_key = api_key or os.getenv('DEEPL_API_KEY')
        self.source_lang = source_lang.upper()
        self.target_lang = target_lang.upper()
        
        # DeepL client
        self.deepl_client = None
        
        if not self.mock and DEEPL_AVAILABLE and self.api_key:
            try:
                self.deepl_client = deepl.Translator(self.api_key)
                logger.info(f"DeepL translator initialized ({self.source_lang} → {self.target_lang})")
            except Exception as e:
                logger.error(f"Failed to initialize DeepL client: {e}")
                logger.info("Falling back to mock mode")
                self.mock = True
        else:
            if not self.mock:
                logger.warning("DeepL not available - using mock mode")
                logger.info("Install deepl-python and set DEEPL_API_KEY for live translation")
            self.mock = True
        
        # Translation history for continuous mode
        self.translation_history = []
        self.max_history = 10
        
        logger.info(f"Translator initialized ({'mock' if self.mock else 'live'} mode)")
    
    def translate(self, text: str) -> Optional[str]:
        """
        Translate text to target language.
        
        Args:
            text: Text to translate
            
        Returns:
            Translated text or None if translation failed
        """
        if not text or not text.strip():
            return None
        
        text = text.strip()
        
        if self.mock:
            return self._mock_translate(text)
        
        try:
            result = self.deepl_client.translate_text(
                text, 
                source_lang=self.source_lang,
                target_lang=self.target_lang
            )
            
            translated = result.text
            logger.info(f"Translated: '{text}' → '{translated}'")
            
            return translated
            
        except Exception as e:
            logger.error(f"Translation failed: {e}")
            return self._mock_translate(text)  # Fallback to mock
    
    def _mock_translate(self, text: str) -> str:
        """Mock translation for testing."""
        
        # Simple mock translation based on target language
        if self.target_lang == "FR":
            # French mock - just add "[FR]" prefix and some basic word replacements
            mock_translations = {
                'hello': 'bonjour',
                'goodbye': 'au revoir',
                'thank you': 'merci',
                'please': 's\'il vous plaît',
                'yes': 'oui',
                'no': 'non',
                'how are you': 'comment allez-vous',
                'good morning': 'bonjour',
                'good evening': 'bonsoir',
                'water': 'eau',
                'food': 'nourriture',
                'help': 'aide'
            }
            
            # Try to find simple replacements
            text_lower = text.lower()
            for english, french in mock_translations.items():
                if english in text_lower:
                    return f"[FR] {french}"
            
            return f"[FR] {text}"
            
        elif self.target_lang == "ES":
            # Spanish mock
            return f"[ES] {text}"
        elif self.target_lang == "DE":
            # German mock
            return f"[DE] {text}"
        else:
            # Generic mock
            return f"[{self.target_lang}] {text}"
    
    def translate_continuous(self, text: str) -> Dict[str, str]:
        """
        Translate text and maintain history for continuous translation display.
        
        Args:
            text: New text to translate
            
        Returns:
            Dict with 'original', 'translated' keys
        """
        translated = self.translate(text)
        
        if translated:
            # Add to history
            entry = {
                'original': text,
                'translated': translated,
                'timestamp': time.time()
            }
            
            self.translation_history.append(entry)
            
            # Limit history size
            if len(self.translation_history) > self.max_history:
                self.translation_history.pop(0)
            
            return {
                'original': text,
                'translated': translated
            }
        
        return {'original': text, 'translated': ''}
    
    def get_latest_translation(self) -> Optional[Dict[str, str]]:
        """Get the most recent translation."""
        if self.translation_history:
            latest = self.translation_history[-1]
            return {
                'original': latest['original'],
                'translated': latest['translated']
            }
        return None
    
    def get_translation_history(self, limit: int = 5) -> List[Dict[str, str]]:
        """
        Get recent translation history.
        
        Args:
            limit: Maximum number of entries to return
            
        Returns:
            List of translation dicts
        """
        return [
            {
                'original': entry['original'],
                'translated': entry['translated']
            }
            for entry in self.translation_history[-limit:]
        ]
    
    def clear_history(self) -> None:
        """Clear translation history."""
        self.translation_history.clear()
        logger.info("Translation history cleared")
    
    def set_target_language(self, target_lang: str) -> bool:
        """
        Change target language.
        
        Args:
            target_lang: New target language code (e.g., "fr", "es", "de")
            
        Returns:
            True if language changed successfully
        """
        target_lang = target_lang.upper()
        
        if target_lang == self.target_lang:
            return True
        
        # Validate language code (basic validation)
        valid_languages = ["FR", "ES", "DE", "IT", "PT", "RU", "JA", "ZH", "KO"]
        
        if not self.mock and target_lang not in valid_languages:
            logger.warning(f"Unsupported target language: {target_lang}")
            return False
        
        old_lang = self.target_lang
        self.target_lang = target_lang
        
        # Clear history when changing language
        self.clear_history()
        
        logger.info(f"Target language changed: {old_lang} → {target_lang}")
        return True
    
    def is_available(self) -> bool:
        """Check if translation service is available."""
        if self.mock:
            return True
        
        return self.deepl_client is not None
    
    def get_language_name(self, lang_code: str) -> str:
        """Get human-readable language name."""
        language_names = {
            "EN": "English",
            "FR": "French",
            "ES": "Spanish", 
            "DE": "German",
            "IT": "Italian",
            "PT": "Portuguese",
            "RU": "Russian",
            "JA": "Japanese",
            "ZH": "Chinese",
            "KO": "Korean"
        }
        
        return language_names.get(lang_code.upper(), lang_code)




if __name__ == "__main__":
    # Test translation functionality
    import sys
    
    logging.basicConfig(level=logging.INFO)
    
    mock_mode = "--mock" in sys.argv
    
    print(f"Testing Translation functionality ({'mock' if mock_mode else 'live'} mode)...")
    
    # Test different target languages
    if len(sys.argv) > 1 and not sys.argv[1].startswith("--"):
        target_lang = sys.argv[1]
    else:
        target_lang = "fr"
    
    translator = Translator(mock=mock_mode, target_lang=target_lang)
    
    if not translator.is_available():
        print("❌ Translation service not available")
        print("Install deepl-python and set DEEPL_API_KEY for live translation")
        sys.exit(1)
    
    source_lang = translator.get_language_name(translator.source_lang)
    target_lang_name = translator.get_language_name(translator.target_lang)
    
    print(f"✅ Translator ready: {source_lang} → {target_lang_name}")
    
    # Test phrases
    test_phrases = [
        "Hello, how are you?",
        "Thank you very much",
        "Where is the bathroom?",
        "I need help",
        "Good morning",
        "Can you help me find the train station?"
    ]
    
    print("\n--- Translation Tests ---")
    for phrase in test_phrases:
        result = translator.translate_continuous(phrase)
        print(f"'{result['original']}'")
        print(f"→ '{result['translated']}'")
        print()
    
    # Test continuous mode (show history)
    print("--- Translation History ---")
    history = translator.get_translation_history()
    for i, entry in enumerate(history[-3:], 1):  # Show last 3
        print(f"{i}. {entry['original']} → {entry['translated']}")
    
    # Test display format (as used in TRANSLATION screen)
    print("\n--- Display Format (TRANSLATION screen) ---")
    latest = translator.get_latest_translation()
    if latest:
        original = latest['original']
        translated = latest['translated']
        
        # Format like display shows (truncated to fit 21 chars)
        orig_line1 = f'"{original[:18]}"' if len(original) <= 18 else f'"{original[:17]}"'
        separator = "-" * 16
        trans_line = f'"{translated[:18]}"' if len(translated) <= 18 else f'"{translated[:17]}"'
        
        print("┌─────────────────────┐")
        print(f"│ {orig_line1:<19} │")
        print(f"│ {'':19} │")
        print(f"│ {separator:<19} │") 
        print(f"│ {trans_line:<19} │")
        print("└─────────────────────┘")
    
    print("\nTranslation test complete")