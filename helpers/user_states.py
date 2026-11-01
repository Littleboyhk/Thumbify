from typing import Any, Dict

class StateManager:
    """Simple in-memory user state tracker for interactive conversational flows."""
    def __init__(self):
        self._states: Dict[int, Dict[str, Any]] = {}

    def set_state(self, user_id: int, state: str, data: Dict[str, Any] = None):
        self._states[user_id] = {
            "state": state,
            "data": data or {}
        }

    def get_state(self, user_id: int) -> Dict[str, Any] | None:
        return self._states.get(user_id)

    def clear_state(self, user_id: int):
        self._states.pop(user_id, None)

state_manager = StateManager()

