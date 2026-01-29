#!/usr/bin/env python3
"""
Todo list management for Iris Smart Glasses.

Handles todo item storage, persistence, and cursor navigation.
"""

import json
import logging
from dataclasses import dataclass, asdict
from typing import List, Dict, Any
from datetime import datetime


logger = logging.getLogger(__name__)


@dataclass
class TodoItem:
    """Represents a single todo item."""
    text: str
    done: bool = False
    created_at: str = ""
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()


class TodoList:
    """
    Manages todo items with persistence and cursor navigation.
    """
    
    def __init__(self, filename: str = "todos.json"):
        self.filename = filename
        self.todos: List[TodoItem] = []
        self.cursor_index = 0
        
        # Load existing todos
        self.load()
        
        logger.info(f"TodoList initialized with {len(self.todos)} items")
    
    def add(self, text: str) -> bool:
        """
        Add a new todo item.
        
        Args:
            text: Todo text
            
        Returns:
            True if added successfully
        """
        if not text.strip():
            logger.warning("Cannot add empty todo item")
            return False
        
        todo = TodoItem(text=text.strip())
        self.todos.append(todo)
        
        # Move cursor to new item
        self.cursor_index = len(self.todos) - 1
        
        # Save to file
        if self.save():
            logger.info(f"Added todo: '{text}'")
            return True
        else:
            # Remove from memory if save failed
            self.todos.pop()
            return False
    
    def cross(self) -> bool:
        """
        Mark current todo item as done.
        
        Returns:
            True if marked successfully
        """
        if not self._is_valid_cursor():
            return False
        
        todo = self.todos[self.cursor_index]
        if todo.done:
            logger.debug("Todo already marked as done")
            return True
        
        todo.done = True
        
        if self.save():
            logger.info(f"Marked done: '{todo.text}'")
            return True
        else:
            # Revert change if save failed
            todo.done = False
            return False
    
    def uncross(self) -> bool:
        """
        Mark current todo item as not done.
        
        Returns:
            True if unmarked successfully
        """
        if not self._is_valid_cursor():
            return False
        
        todo = self.todos[self.cursor_index]
        if not todo.done:
            logger.debug("Todo already not done")
            return True
        
        todo.done = False
        
        if self.save():
            logger.info(f"Marked not done: '{todo.text}'")
            return True
        else:
            # Revert change if save failed
            todo.done = True
            return False
    
    def scroll_up(self) -> bool:
        """
        Move cursor up in the todo list.
        
        Returns:
            True if cursor moved
        """
        if not self.todos:
            return False
        
        if self.cursor_index > 0:
            self.cursor_index -= 1
            logger.debug(f"Cursor moved up to index {self.cursor_index}")
            return True
        
        return False
    
    def scroll_down(self) -> bool:
        """
        Move cursor down in the todo list.
        
        Returns:
            True if cursor moved
        """
        if not self.todos:
            return False
        
        if self.cursor_index < len(self.todos) - 1:
            self.cursor_index += 1
            logger.debug(f"Cursor moved down to index {self.cursor_index}")
            return True
        
        return False
    
    def get_visible(self, window: int = 3) -> List[Dict[str, Any]]:
        """
        Get todos visible in display window around cursor.
        
        Args:
            window: Maximum number of items to show
            
        Returns:
            List of todo dicts for display
        """
        if not self.todos:
            return []
        
        # Calculate window around cursor
        start_idx = max(0, self.cursor_index - window + 1)
        end_idx = min(len(self.todos), start_idx + window)
        
        # Adjust start if we hit the end
        if end_idx - start_idx < window and start_idx > 0:
            start_idx = max(0, end_idx - window)
        
        visible_todos = []
        for i in range(start_idx, end_idx):
            todo = self.todos[i]
            visible_todos.append({
                'text': todo.text,
                'done': todo.done,
                'is_current': (i == self.cursor_index),
                'index': i
            })
        
        return visible_todos
    
    def get_current_todo(self) -> Optional[TodoItem]:
        """Get the currently selected todo item."""
        if self._is_valid_cursor():
            return self.todos[self.cursor_index]
        return None
    
    def get_all(self) -> List[Dict[str, Any]]:
        """
        Get all todos for display.
        
        Returns:
            List of todo dicts
        """
        return [{
            'text': todo.text,
            'done': todo.done,
            'created_at': todo.created_at,
            'is_current': (i == self.cursor_index)
        } for i, todo in enumerate(self.todos)]
    
    def get_stats(self) -> Dict[str, int]:
        """Get todo statistics."""
        total = len(self.todos)
        done = sum(1 for todo in self.todos if todo.done)
        pending = total - done
        
        return {
            'total': total,
            'done': done,
            'pending': pending
        }
    
    def remove_current(self) -> bool:
        """
        Remove the currently selected todo item.
        
        Returns:
            True if removed successfully
        """
        if not self._is_valid_cursor():
            return False
        
        removed_todo = self.todos.pop(self.cursor_index)
        
        # Adjust cursor position
        if self.cursor_index >= len(self.todos) and len(self.todos) > 0:
            self.cursor_index = len(self.todos) - 1
        elif len(self.todos) == 0:
            self.cursor_index = 0
        
        if self.save():
            logger.info(f"Removed todo: '{removed_todo.text}'")
            return True
        else:
            # Restore todo if save failed
            self.todos.insert(self.cursor_index, removed_todo)
            return False
    
    def clear_completed(self) -> int:
        """
        Remove all completed todo items.
        
        Returns:
            Number of items removed
        """
        initial_count = len(self.todos)
        self.todos = [todo for todo in self.todos if not todo.done]
        removed_count = initial_count - len(self.todos)
        
        # Adjust cursor
        self.cursor_index = min(self.cursor_index, len(self.todos) - 1)
        if self.cursor_index < 0:
            self.cursor_index = 0
        
        if removed_count > 0:
            if self.save():
                logger.info(f"Cleared {removed_count} completed todos")
            else:
                logger.error("Failed to save after clearing completed todos")
        
        return removed_count
    
    def _is_valid_cursor(self) -> bool:
        """Check if cursor index is valid."""
        return 0 <= self.cursor_index < len(self.todos)
    
    def save(self) -> bool:
        """
        Save todos to file.
        
        Returns:
            True if saved successfully
        """
        try:
            data = {
                'todos': [asdict(todo) for todo in self.todos],
                'cursor_index': self.cursor_index,
                'saved_at': datetime.now().isoformat()
            }
            
            with open(self.filename, 'w') as f:
                json.dump(data, f, indent=2)
            
            logger.debug(f"Saved {len(self.todos)} todos to {self.filename}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save todos: {e}")
            return False
    
    def load(self) -> bool:
        """
        Load todos from file.
        
        Returns:
            True if loaded successfully
        """
        try:
            with open(self.filename, 'r') as f:
                data = json.load(f)
            
            # Load todos
            self.todos = [TodoItem(**todo_data) for todo_data in data.get('todos', [])]
            
            # Load cursor position
            self.cursor_index = data.get('cursor_index', 0)
            
            # Validate cursor position
            if self.cursor_index >= len(self.todos):
                self.cursor_index = max(0, len(self.todos) - 1)
            
            logger.info(f"Loaded {len(self.todos)} todos from {self.filename}")
            return True
            
        except FileNotFoundError:
            logger.info(f"No existing todo file found at {self.filename}")
            return True  # Not an error
        except Exception as e:
            logger.error(f"Failed to load todos: {e}")
            return False


# Import fix
from typing import Optional


if __name__ == "__main__":
    # Test todo list functionality
    import tempfile
    import os
    
    logging.basicConfig(level=logging.INFO)
    
    # Use temporary file for testing
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        temp_file = f.name
    
    try:
        print("Testing TodoList functionality...")
        
        # Create todo list
        todos = TodoList(filename=temp_file)
        
        # Add some todos
        print("\n--- Adding todos ---")
        todos.add("Buy groceries")
        todos.add("Call mom")
        todos.add("Fix bug")
        todos.add("Write documentation")
        
        print(f"Stats: {todos.get_stats()}")
        
        # Test cursor navigation
        print("\n--- Testing navigation ---")
        print(f"Current cursor: {todos.cursor_index}")
        print(f"Visible todos: {[t['text'] for t in todos.get_visible()]}")
        
        todos.scroll_down()
        print(f"After scroll down: {todos.cursor_index}")
        
        todos.scroll_down()
        print(f"After scroll down: {todos.cursor_index}")
        
        # Mark some as done
        print("\n--- Marking todos done ---")
        todos.cross()  # Mark current as done
        print(f"Marked done: {todos.get_current_todo().text}")
        
        todos.scroll_up()
        todos.cross()  # Mark another as done
        print(f"Marked done: {todos.get_current_todo().text}")
        
        print(f"Stats: {todos.get_stats()}")
        
        # Show all todos
        print("\n--- All todos ---")
        for todo in todos.get_all():
            status = "✓" if todo['done'] else "○"
            current = "→ " if todo['is_current'] else "  "
            print(f"{current}{status} {todo['text']}")
        
        # Test clearing completed
        print("\n--- Clearing completed ---")
        cleared = todos.clear_completed()
        print(f"Cleared {cleared} completed todos")
        print(f"Remaining: {len(todos.todos)} todos")
        
        print("\nTodoList test complete")
        
    finally:
        # Clean up temp file
        if os.path.exists(temp_file):
            os.remove(temp_file)