#!/usr/bin/env python3
"""
Unit tests for feature modules (todo, weather, translation).

Tests core functionality and mock behavior.
"""

import pytest
import json
import tempfile
import os
from unittest.mock import Mock, patch
from datetime import datetime

from features.todo import TodoItem, get_all_todos, add_todo, cross_todo, uncross_todo, get_visible_todos
from features.weather import get_current_weather, get_forecast
from features.translation import translate_text, get_translation_history


class TestTodoFeature:
    """Test suite for todo functionality."""
    
    @pytest.fixture
    def temp_todo_file(self):
        """Create temporary todo file for testing."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            # Start with empty list
            json.dump([], f)
            temp_path = f.name
        
        # Patch the TODO_FILE path
        with patch('features.todo.TODO_FILE', temp_path):
            yield temp_path
        
        # Cleanup
        os.unlink(temp_path)
    
    def test_todo_item_creation(self):
        """Test TodoItem dataclass creation."""
        todo = TodoItem(
            id=1,
            text="Buy groceries", 
            done=False,
            created_at=datetime.now()
        )
        
        assert todo.id == 1
        assert todo.text == "Buy groceries"
        assert not todo.done
        assert todo.created_at is not None
    
    def test_todo_item_to_dict(self):
        """Test TodoItem serialization."""
        now = datetime.now()
        todo = TodoItem(id=1, text="Test", done=True, created_at=now)
        
        todo_dict = todo.to_dict()
        assert todo_dict["id"] == 1
        assert todo_dict["text"] == "Test"
        assert todo_dict["done"] is True
        assert "created_at" in todo_dict
    
    def test_todo_item_from_dict(self):
        """Test TodoItem deserialization."""
        data = {
            "id": 2,
            "text": "Test item",
            "done": False,
            "created_at": datetime.now().isoformat()
        }
        
        todo = TodoItem.from_dict(data)
        assert todo.id == 2
        assert todo.text == "Test item"
        assert not todo.done
        assert isinstance(todo.created_at, datetime)
    
    def test_add_todo(self, temp_todo_file):
        """Test adding todos."""
        # Add first todo
        todo1 = add_todo("Buy milk")
        assert todo1.text == "Buy milk"
        assert not todo1.done
        assert todo1.id == 1
        
        # Add second todo
        todo2 = add_todo("Walk dog")
        assert todo2.text == "Walk dog"
        assert todo2.id == 2
        
        # Check persistence
        todos = get_all_todos()
        assert len(todos) == 2
        assert todos[0].text == "Buy milk"
        assert todos[1].text == "Walk dog"
    
    def test_cross_uncross_todo(self, temp_todo_file):
        """Test marking todos as done/undone."""
        # Add a todo
        todo = add_todo("Test task")
        todo_id = todo.id
        
        # Mark as done
        success = cross_todo(todo_id)
        assert success
        
        todos = get_all_todos()
        assert len(todos) == 1
        assert todos[0].done
        
        # Mark as undone
        success = uncross_todo(todo_id)
        assert success
        
        todos = get_all_todos()
        assert not todos[0].done
        
        # Test invalid ID
        assert not cross_todo(999)
        assert not uncross_todo(999)
    
    def test_get_visible_todos(self, temp_todo_file):
        """Test visible todos with cursor navigation."""
        # Add multiple todos
        for i in range(10):
            add_todo(f"Task {i+1}")
        
        # Test first page
        visible = get_visible_todos(cursor=0, page_size=3)
        assert len(visible) == 3
        assert visible[0].text == "Task 1"
        assert visible[2].text == "Task 3"
        
        # Test second page
        visible = get_visible_todos(cursor=3, page_size=3)
        assert len(visible) == 3
        assert visible[0].text == "Task 4"
        
        # Test cursor beyond end
        visible = get_visible_todos(cursor=15, page_size=3)
        assert len(visible) == 0
    
    def test_empty_todo_list(self, temp_todo_file):
        """Test behavior with empty todo list."""
        todos = get_all_todos()
        assert len(todos) == 0
        
        visible = get_visible_todos(cursor=0, page_size=3)
        assert len(visible) == 0
    
    def test_todo_file_creation(self):
        """Test todo file creation when it doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            nonexistent_file = os.path.join(temp_dir, "nonexistent.json")
            
            with patch('features.todo.TODO_FILE', nonexistent_file):
                # Should create file when accessing todos
                todos = get_all_todos()
                assert len(todos) == 0
                assert os.path.exists(nonexistent_file)


class TestWeatherFeature:
    """Test suite for weather functionality."""
    
    @patch('requests.get')
    def test_real_weather_api_success(self, mock_get):
        """Test successful real weather API call."""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "main": {"temp": 25.5, "humidity": 65},
            "weather": [{"description": "Clear sky"}],
            "name": "College Station"
        }
        mock_get.return_value = mock_response
        
        with patch.dict(os.environ, {'OPENWEATHER_API_KEY': 'test_key'}):
            weather = get_current_weather(mock=False)
            
            assert weather["temperature"] == 25.5
            assert weather["description"] == "Clear sky"
            assert weather["humidity"] == 65
            assert weather["location"] == "College Station"
    
    @patch('requests.get')
    def test_real_weather_api_failure(self, mock_get):
        """Test weather API failure handling."""
        # Mock failed response
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response
        
        with patch.dict(os.environ, {'OPENWEATHER_API_KEY': 'test_key'}):
            weather = get_current_weather(mock=False)
            
            assert "error" in weather
    
    def test_mock_weather(self):
        """Test mock weather functionality."""
        weather = get_current_weather(mock=True)
        
        # Should return mock data
        assert "temperature" in weather
        assert "description" in weather
        assert "humidity" in weather
        assert "location" in weather
        
        # Temperature should be reasonable
        assert 10 <= weather["temperature"] <= 35
        
        # Should have time-based variation
        weather2 = get_current_weather(mock=True)
        # May or may not be different, but should not crash
        assert "temperature" in weather2
    
    @patch('requests.get') 
    def test_forecast_api_success(self, mock_get):
        """Test successful forecast API call."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "list": [
                {
                    "dt_txt": "2024-01-01 12:00:00",
                    "main": {"temp": 20.0},
                    "weather": [{"description": "Sunny"}]
                },
                {
                    "dt_txt": "2024-01-02 12:00:00", 
                    "main": {"temp": 22.0},
                    "weather": [{"description": "Cloudy"}]
                }
            ]
        }
        mock_get.return_value = mock_response
        
        with patch.dict(os.environ, {'OPENWEATHER_API_KEY': 'test_key'}):
            forecast = get_forecast(days=2, mock=False)
            
            assert len(forecast) == 2
            assert forecast[0]["temperature"] == 20.0
            assert forecast[1]["temperature"] == 22.0
    
    def test_mock_forecast(self):
        """Test mock forecast functionality."""
        forecast = get_forecast(days=3, mock=True)
        
        assert len(forecast) == 3
        for day in forecast:
            assert "date" in day
            assert "temperature" in day
            assert "description" in day
    
    def test_weather_no_api_key(self):
        """Test weather with missing API key."""
        with patch.dict(os.environ, {}, clear=True):
            weather = get_current_weather(mock=False)
            # Should fallback to mock or return error
            assert "temperature" in weather or "error" in weather


class TestTranslationFeature:
    """Test suite for translation functionality."""
    
    @patch('deepl.Translator.translate_text')
    def test_real_translation_success(self, mock_translate):
        """Test successful real translation."""
        # Mock successful translation
        mock_result = Mock()
        mock_result.text = "Bonjour le monde"
        mock_translate.return_value = mock_result
        
        with patch.dict(os.environ, {'DEEPL_API_KEY': 'test_key'}):
            result = translate_text("Hello world", target="FR", mock=False)
            
            assert result["success"] is True
            assert result["translated"] == "Bonjour le monde"
            assert result["original"] == "Hello world"
    
    @patch('deepl.Translator.translate_text')
    def test_real_translation_failure(self, mock_translate):
        """Test translation API failure."""
        mock_translate.side_effect = Exception("API Error")
        
        with patch.dict(os.environ, {'DEEPL_API_KEY': 'test_key'}):
            result = translate_text("Hello", target="FR", mock=False)
            
            assert result["success"] is False
            assert "error" in result
    
    def test_mock_translation(self):
        """Test mock translation functionality."""
        result = translate_text("Hello world", target="FR", mock=True)
        
        assert result["success"] is True
        assert result["original"] == "Hello world"
        assert result["translated"].startswith("[FR] Hello world")
    
    def test_translation_history(self):
        """Test translation history tracking."""
        # Clear history
        history = get_translation_history()
        
        # Add some translations
        translate_text("Hello", target="FR", mock=True)
        translate_text("Goodbye", target="ES", mock=True)
        
        history = get_translation_history()
        assert len(history) >= 2
        
        # Check recent translations
        recent = history[-2:]
        texts = [h["original"] for h in recent]
        assert "Hello" in texts
        assert "Goodbye" in texts
    
    def test_translation_different_targets(self):
        """Test translation to different target languages."""
        # French
        result_fr = translate_text("Hello", target="FR", mock=True)
        assert "[FR]" in result_fr["translated"]
        
        # Spanish  
        result_es = translate_text("Hello", target="ES", mock=True)
        assert "[ES]" in result_es["translated"]
        
        # German
        result_de = translate_text("Hello", target="DE", mock=True)
        assert "[DE]" in result_de["translated"]
    
    def test_translation_no_api_key(self):
        """Test translation with missing API key."""
        with patch.dict(os.environ, {}, clear=True):
            result = translate_text("Hello", target="FR", mock=False)
            # Should fallback to mock
            assert result["success"] is True
            assert "[FR]" in result["translated"]
    
    def test_empty_text_translation(self):
        """Test translation of empty text."""
        result = translate_text("", target="FR", mock=True)
        assert result["success"] is True
        assert result["translated"] == "[FR] "
    
    def test_long_text_translation(self):
        """Test translation of long text."""
        long_text = "This is a very long text " * 20
        result = translate_text(long_text, target="FR", mock=True)
        
        assert result["success"] is True
        assert result["original"] == long_text
        assert "[FR]" in result["translated"]


class TestFeatureIntegration:
    """Integration tests across features."""
    
    def test_all_features_mock_mode(self, temp_todo_file):
        """Test that all features work in mock mode."""
        # Todo
        todo = add_todo("Test integration")
        assert todo is not None
        
        # Weather
        weather = get_current_weather(mock=True)
        assert "temperature" in weather
        
        # Translation
        translation = translate_text("Test", target="FR", mock=True)
        assert translation["success"] is True
    
    def test_feature_error_isolation(self):
        """Test that feature errors don't affect others."""
        # Even if one feature fails, others should work
        try:
            weather = get_current_weather(mock=True)
            translation = translate_text("Hello", mock=True)
            
            assert "temperature" in weather
            assert translation["success"] is True
        except Exception as e:
            pytest.fail(f"Features should handle errors gracefully: {e}")


if __name__ == "__main__":
    pytest.main([__file__])