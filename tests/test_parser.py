#!/usr/bin/env python3
"""
Unit tests for the state machine parser.

Tests state transitions, command parsing, and timeout behavior.
"""

import pytest
import time
from datetime import datetime, timedelta

from core.parser import CommandParser, State, ParseResult
from core.discovery import create_registry


class TestCommandParser:
    """Test suite for CommandParser state machine."""
    
    @pytest.fixture
    def parser(self):
        """Create a parser with mock registry for testing."""
        registry = create_registry(mock=True)
        return CommandParser(registry, timeout_seconds=0.1)  # Short timeout for testing
    
    def test_initial_state(self, parser):
        """Test parser starts in IDLE state."""
        assert parser.get_current_state() == State.IDLE
    
    def test_idle_to_menu(self, parser):
        """Test transition from IDLE to MAIN_MENU."""
        result = parser.parse("hey iris")
        assert result.new_state == State.MAIN_MENU
        assert parser.get_current_state() == State.MAIN_MENU
    
    def test_menu_navigation(self, parser):
        """Test navigation from main menu to features."""
        # Go to main menu first
        parser.parse("hey iris")
        
        # Test todo
        result = parser.parse("todo")
        assert result.new_state == State.TODO_LIST
        
        # Reset to menu
        parser._transition_to(State.MAIN_MENU)
        
        # Test translation
        result = parser.parse("translation")
        assert result.new_state == State.TRANSLATION
        
        # Reset to menu
        parser._transition_to(State.MAIN_MENU)
        
        # Test connect
        result = parser.parse("connect")
        assert result.new_state == State.DEVICE_LIST
    
    def test_todo_commands(self, parser):
        """Test todo list commands."""
        # Navigate to todo list
        parser.parse("hey iris")
        parser.parse("todo")
        assert parser.get_current_state() == State.TODO_LIST
        
        # Test scroll commands
        result = parser.parse("up")
        assert result.action == "scroll_up"
        
        result = parser.parse("down")
        assert result.action == "scroll_down"
        
        # Test mark commands
        result = parser.parse("cross")
        assert result.action == "mark_done"
        
        result = parser.parse("uncross")
        assert result.action == "mark_undone"
        
        # Test add
        result = parser.parse("add")
        assert result.new_state == State.TODO_ADD
    
    def test_todo_add_flow(self, parser):
        """Test todo add workflow."""
        # Navigate to todo add
        parser.parse("hey iris")
        parser.parse("todo")
        parser.parse("add")
        assert parser.get_current_state() == State.TODO_ADD
        
        # Capture text
        result = parser.parse("buy groceries")
        assert result.action == "capture_todo_text"
        assert result.data["text"] == "buy groceries"
        
        # Check state data was stored
        assert parser.get_state_data("captured_text") == "buy groceries"
        
        # Confirm
        result = parser.parse("confirm")
        assert result.new_state == State.TODO_LIST
        assert result.action == "add_todo"
        assert result.data["text"] == "buy groceries"
        
        # Test cancel
        parser._transition_to(State.TODO_ADD)
        result = parser.parse("cancel")
        assert result.new_state == State.TODO_LIST
    
    def test_translation_commands(self, parser):
        """Test translation mode commands."""
        # Navigate to translation
        parser.parse("hey iris")
        parser.parse("translation")
        assert parser.get_current_state() == State.TRANSLATION
        
        # Test translation input
        result = parser.parse("hello world")
        assert result.action == "translate"
        assert result.data["text"] == "hello world"
        
        # Test exit command
        result = parser.parse("iris end")
        assert result.new_state == State.MAIN_MENU
    
    def test_device_commands(self, parser):
        """Test device control commands."""
        # Navigate to device list
        parser.parse("hey iris")
        parser.parse("connect")
        assert parser.get_current_state() == State.DEVICE_LIST
        
        # Test connect commands
        result = parser.parse("connect")
        assert result.action == "connect_current"
        
        result = parser.parse("connect light")
        assert result.action == "connect_named"
        assert result.data["name"] == "light"
    
    def test_connected_light_commands(self, parser):
        """Test connected light commands."""
        # Manually set to connected light state
        parser._transition_to(State.CONNECTED_LIGHT)
        
        result = parser.parse("on")
        assert result.action == "light_on"
        
        result = parser.parse("off")
        assert result.action == "light_off"
        
        result = parser.parse("back")
        assert result.new_state == State.DEVICE_LIST
    
    def test_connected_fan_commands(self, parser):
        """Test connected fan commands."""
        parser._transition_to(State.CONNECTED_FAN)
        
        result = parser.parse("on")
        assert result.action == "fan_on"
        
        result = parser.parse("off")
        assert result.action == "fan_off"
        
        result = parser.parse("low")
        assert result.action == "fan_low"
        
        result = parser.parse("high")
        assert result.action == "fan_high"
    
    def test_back_navigation(self, parser):
        """Test back navigation from various states."""
        # Main menu to idle
        parser.parse("hey iris")
        result = parser.parse("back")
        assert result.new_state == State.IDLE
        
        # Todo list to main menu
        parser.parse("hey iris")
        parser.parse("todo")
        result = parser.parse("back")
        assert result.new_state == State.MAIN_MENU
        
        # Device list to main menu
        parser._transition_to(State.DEVICE_LIST)
        result = parser.parse("back")
        assert result.new_state == State.MAIN_MENU
    
    def test_timeout_behavior(self, parser):
        """Test timeout behavior for different states."""
        # Main menu should timeout to IDLE
        parser.parse("hey iris")
        time.sleep(0.2)  # Wait for timeout
        result = parser.check_timeout()
        assert result == State.IDLE
        
        # Todo list should timeout to IDLE
        parser.parse("hey iris")
        parser.parse("todo")
        time.sleep(0.2)
        result = parser.check_timeout()
        assert result == State.IDLE
        
        # Todo add should timeout to TODO_LIST
        parser.parse("hey iris")
        parser.parse("todo")
        parser.parse("add")
        time.sleep(0.2)
        result = parser.check_timeout()
        assert result == State.TODO_LIST
    
    def test_no_timeout_states(self, parser):
        """Test that certain states don't timeout."""
        # IDLE should never timeout
        time.sleep(0.2)
        result = parser.check_timeout()
        assert result is None
        
        # TRANSLATION should not timeout
        parser.parse("hey iris")
        parser.parse("translation")
        time.sleep(0.2)
        result = parser.check_timeout()
        assert result is None
        
        # Connected device states should not timeout
        parser._transition_to(State.CONNECTED_LIGHT)
        time.sleep(0.2)
        result = parser.check_timeout()
        assert result is None
    
    def test_invalid_commands(self, parser):
        """Test handling of invalid/unrecognized commands."""
        # Invalid command in IDLE
        result = parser.parse("invalid command")
        assert result.new_state is None
        assert result.action is None
        
        # Invalid command in main menu
        parser.parse("hey iris")
        result = parser.parse("invalid")
        assert result.new_state is None
        
        # Empty command
        result = parser.parse("")
        assert result.new_state is None
    
    def test_state_data_persistence(self, parser):
        """Test state data storage and retrieval."""
        parser.set_state_data("test_key", "test_value")
        assert parser.get_state_data("test_key") == "test_value"
        
        # Data should clear on state change
        parser._transition_to(State.MAIN_MENU)
        assert parser.get_state_data("test_key") is None
        
        # Test default values
        assert parser.get_state_data("nonexistent", "default") == "default"
    
    def test_device_name_mapping(self, parser):
        """Test device name to type mapping."""
        mapping = parser.get_device_name_mapping()
        
        assert mapping["light"] == "light"
        assert mapping["smart light"] == "light"
        assert mapping["fan"] == "fan"
        assert mapping["smart fan"] == "fan"
        assert mapping["glasses 2"] == "glasses"
        assert mapping["glasses two"] == "glasses"
    
    def test_connect_device_states(self, parser):
        """Test device type to connected state mapping."""
        assert parser.connect_to_device("light") == State.CONNECTED_LIGHT
        assert parser.connect_to_device("fan") == State.CONNECTED_FAN
        assert parser.connect_to_device("motion") == State.CONNECTED_MOTION
        assert parser.connect_to_device("distance") == State.CONNECTED_DISTANCE
        assert parser.connect_to_device("glasses") == State.CONNECTED_GLASSES
        
        # Unknown device should return device list
        assert parser.connect_to_device("unknown") == State.DEVICE_LIST
    
    def test_case_insensitive_commands(self, parser):
        """Test that commands are case insensitive."""
        result = parser.parse("HEY IRIS")
        assert result.new_state == State.MAIN_MENU
        
        parser.parse("hey iris")
        result = parser.parse("TODO")
        assert result.new_state == State.TODO_LIST
        
        parser._transition_to(State.CONNECTED_LIGHT)
        result = parser.parse("ON")
        assert result.action == "light_on"


if __name__ == "__main__":
    pytest.main([__file__])