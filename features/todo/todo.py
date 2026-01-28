"""
Todo Feature for Iris Smart Glasses

Voice-controlled todo list displayed on OLED.
"""

import json
import os
from typing import List, Dict
from dataclasses import dataclass, asdict
import logging

from core.feature_base import FeatureBase

logger = logging.getLogger(__name__)


@dataclass
class TodoItem:
    """Represents a single todo item."""
    text: str
    completed: bool = False


class TodoFeature(FeatureBase):
    """
    Todo list feature for smart glasses.
    
    Voice Commands:
    - "hey iris activate todo" - Activate the feature
    - "add [item]" - Add a new todo
    - "done" / "complete" - Mark current item complete
    - "next" - Move cursor down
    - "previous" / "back" - Move cursor up
    - "delete" - Remove current item
    - "clear done" - Remove all completed items
    """
    
    # Feature name for voice activation
    name = "todo"
    
    # Display symbols
    CURSOR_SYMBOL = ">"
    INCOMPLETE_SYMBOL = "o"
    COMPLETE_SYMBOL = "x"
    
    def __init__(self, display, audio, camera, config):
        """
        Initialize todo feature.
        
        Args:
            display: DisplayManager instance
            audio: AudioManager instance
            camera: CameraManager instance
            config: Configuration dictionary
        """
        super().__init__(display, audio, camera, config)
        
        # Todo data
        self.data_file = config.get('todo_data_file', 'todos.json')
        self.todos: List[TodoItem] = []
        self.cursor_index: int = 0
        
        # Load existing todos
        self.load_todos()
        
        logger.info("Todo feature initialized")
    
    # ==================== FeatureBase Implementation ====================
    
    def activate(self) -> None:
        """Activate the todo feature and show initial display."""
        self.is_active = True
        logger.info("Todo feature activated")
        
        # Show initial display
        self.render()
        
        # Provide audio feedback
        stats = self.get_stats()
        if stats['total'] > 0:
            self.speak_feedback(f"Todo list activated. {stats['remaining']} remaining out of {stats['total']} todos")
        else:
            self.speak_feedback("Todo list activated")
    
    def deactivate(self) -> None:
        """Deactivate the todo feature."""
        self.is_active = False
        logger.info("Todo feature deactivated")
        
        # Save before deactivating
        self.save_todos()
        
        # Provide audio feedback
        self.speak_feedback("Todo list deactivated")
    
    def process_voice(self, transcript: str) -> None:
        """
        Handle voice commands for todo feature.
        
        Args:
            transcript: Voice command text (wake word already removed)
        """
        if not transcript:
            return
        
        command = transcript.lower().strip()
        logger.info(f"Processing todo command: '{command}'")
        
        try:
            # Add command
            if command.startswith("add "):
                item_text = command[4:].strip()
                self._handle_add(item_text)
            
            # Done/Complete
            elif command in ["done", "complete"]:
                self._handle_done()
            
            # Navigation
            elif command == "next":
                self._handle_next()
            
            elif command in ["previous", "back"]:
                self._handle_previous()
            
            # Delete
            elif command == "delete":
                self._handle_delete()
            
            # Clear done
            elif command == "clear done":
                self._handle_clear_done()
            
            # Unknown command
            else:
                logger.warning(f"Unknown todo command: '{command}'")
                self.speak_feedback("Command not recognized")
                
        except Exception as e:
            self.handle_error(e, f"process_voice: {command}")
    
    def render(self) -> None:
        """Update the OLED display with current todo list."""
        try:
            lines = self._get_display_lines()
            self.display.show_lines(lines)
            logger.debug(f"Rendered {len(lines)} lines to display")
        except Exception as e:
            self.handle_error(e, "render")
    
    def get_help_text(self) -> str:
        """Get help text for todo feature commands."""
        return (
            "Todo commands:\n"
            "- add [item] - Add todo\n"
            "- done - Complete item\n"
            "- next/previous - Navigate\n"
            "- delete - Remove item\n"
            "- clear done - Remove completed"
        )
    
    # ==================== Command Handlers ====================
    
    def _handle_add(self, text: str) -> None:
        """Handle 'add [item]' command."""
        if not text.strip():
            self.speak_feedback("Cannot add empty todo")
            return
        
        new_todo = TodoItem(text=text.strip())
        self.todos.append(new_todo)
        
        # Move cursor to new item if this is the first item
        if len(self.todos) == 1:
            self.cursor_index = 0
        
        self.save_todos()
        self.render()
        self.speak_feedback(f"Added: {text.strip()}")
        logger.info(f"Added todo: {text.strip()}")
    
    def _handle_done(self) -> None:
        """Handle 'done' or 'complete' command."""
        if not self.todos:
            self.speak_feedback("No items to complete")
            return
        
        self.todos[self.cursor_index].completed = True
        self.save_todos()
        self.render()
        self.speak_feedback("Marked complete")
        logger.info(f"Marked complete: {self.todos[self.cursor_index].text}")
    
    def _handle_next(self) -> None:
        """Handle 'next' command."""
        if not self.todos:
            self.speak_feedback("No items")
            return
        
        self.cursor_index = (self.cursor_index + 1) % len(self.todos)
        self.render()
        
        # Announce current item
        current = self.todos[self.cursor_index]
        status = "completed" if current.completed else "incomplete"
        self.speak_feedback(f"{current.text}, {status}")
        logger.debug(f"Moved to item {self.cursor_index}")
    
    def _handle_previous(self) -> None:
        """Handle 'previous' or 'back' command."""
        if not self.todos:
            self.speak_feedback("No items")
            return
        
        self.cursor_index = (self.cursor_index - 1) % len(self.todos)
        self.render()
        
        # Announce current item
        current = self.todos[self.cursor_index]
        status = "completed" if current.completed else "incomplete"
        self.speak_feedback(f"{current.text}, {status}")
        logger.debug(f"Moved to item {self.cursor_index}")
    
    def _handle_delete(self) -> None:
        """Handle 'delete' command."""
        if not self.todos:
            self.speak_feedback("No items to delete")
            return
        
        deleted_text = self.todos[self.cursor_index].text
        self.todos.pop(self.cursor_index)
        
        # Adjust cursor
        if self.todos:
            self.cursor_index = min(self.cursor_index, len(self.todos) - 1)
        else:
            self.cursor_index = 0
        
        self.save_todos()
        self.render()
        self.speak_feedback(f"Deleted: {deleted_text}")
        logger.info(f"Deleted todo: {deleted_text}")
    
    def _handle_clear_done(self) -> None:
        """Handle 'clear done' command."""
        original_count = len(self.todos)
        self.todos = [todo for todo in self.todos if not todo.completed]
        removed_count = original_count - len(self.todos)
        
        # Adjust cursor
        if self.todos:
            self.cursor_index = min(self.cursor_index, len(self.todos) - 1)
        else:
            self.cursor_index = 0
        
        if removed_count > 0:
            self.save_todos()
            self.render()
            self.speak_feedback(f"Cleared {removed_count} completed item{'s' if removed_count != 1 else ''}")
            logger.info(f"Cleared {removed_count} completed items")
        else:
            self.speak_feedback("No completed items to clear")
    
    # ==================== Data Management ====================
    
    def load_todos(self) -> None:
        """Load todos from JSON file."""
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r') as f:
                    data = json.load(f)
                    self.todos = [TodoItem(**item) for item in data]
                logger.info(f"Loaded {len(self.todos)} todos from {self.data_file}")
            except (json.JSONDecodeError, TypeError) as e:
                logger.error(f"Failed to load todos: {e}")
                self.todos = []
        else:
            self.todos = []
            logger.info("No existing todo file found")
        
        # Ensure cursor is valid
        if self.todos:
            self.cursor_index = min(self.cursor_index, len(self.todos) - 1)
        else:
            self.cursor_index = 0
    
    def save_todos(self) -> None:
        """Save todos to JSON file."""
        try:
            data = [asdict(todo) for todo in self.todos]
            with open(self.data_file, 'w') as f:
                json.dump(data, f, indent=2)
            logger.debug(f"Saved {len(self.todos)} todos to {self.data_file}")
        except Exception as e:
            logger.error(f"Failed to save todos: {e}")
    
    # ==================== Display Rendering ====================
    
    def _get_display_lines(self) -> List[str]:
        """
        Get formatted lines for display.
        
        Returns:
            List of up to 4 formatted strings for OLED display
        """
        if not self.todos:
            return [
                "  No todos!",
                "  Say 'add [item]'",
                "  to create one",
                ""
            ]
        
        # Get items to display (max 4 lines)
        display_items = self._get_display_window(max_items=4)
        
        # Format each line (21 chars max per line)
        lines = []
        for item in display_items:
            cursor = self.CURSOR_SYMBOL if item['has_cursor'] else " "
            status = self.COMPLETE_SYMBOL if item['completed'] else self.INCOMPLETE_SYMBOL
            text = item['text']
            
            # Truncate text to fit display (21 chars total)
            # Format: "> ○ text..." (cursor + space + symbol + space + text)
            max_text_width = 21 - 4  # 4 chars for "> ○ "
            if len(text) > max_text_width:
                text = text[:max_text_width - 1] + "…"
            
            lines.append(f"{cursor} {status} {text}")
        
        # Pad with empty lines if needed
        while len(lines) < 4:
            lines.append("")
        
        return lines
    
    def _get_display_window(self, max_items: int) -> List[Dict]:
        """
        Get items for display window centered around cursor.
        
        Args:
            max_items: Maximum items to show (4 for OLED)
            
        Returns:
            List of item dicts with display info
        """
        total_items = len(self.todos)
        
        # Show all if we have fewer than max
        if total_items <= max_items:
            return [
                {
                    'text': self.todos[i].text,
                    'completed': self.todos[i].completed,
                    'has_cursor': i == self.cursor_index
                }
                for i in range(total_items)
            ]
        
        # Calculate window around cursor
        half_window = max_items // 2
        start_idx = max(0, self.cursor_index - half_window)
        end_idx = min(total_items, start_idx + max_items)
        
        # Adjust if at end
        if end_idx - start_idx < max_items:
            start_idx = max(0, end_idx - max_items)
        
        return [
            {
                'text': self.todos[i].text,
                'completed': self.todos[i].completed,
                'has_cursor': i == self.cursor_index
            }
            for i in range(start_idx, end_idx)
        ]
    
    # ==================== Stats ====================
    
    def get_stats(self) -> Dict[str, int]:
        """
        Get todo statistics.
        
        Returns:
            Dict with 'total', 'completed', 'remaining'
        """
        total = len(self.todos)
        completed = sum(1 for todo in self.todos if todo.completed)
        return {
            'total': total,
            'completed': completed,
            'remaining': total - completed
        }