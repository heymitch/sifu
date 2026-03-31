"""Event types, schema, and serialization for Sifu."""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional
import json
import time


class EventType(str, Enum):
    """Types of events captured by the daemon."""

    CLICK = "click"
    RIGHT_CLICK = "right_click"
    SHORTCUT = "shortcut"
    TEXT_INPUT = "text_input"
    COMMAND = "command"
    APP_SWITCH = "app_switch"
    WINDOW_SWITCH = "window_switch"


# Apps where keystroke logging is always skipped
IGNORE_APPS_DEFAULT = frozenset([
    "1Password",
    "Bitwarden",
    "KeyChain Access",
    "loginwindow",
    "ScreenSaverEngine",
])

# Terminal apps where Enter = command execution
TERMINAL_APPS = frozenset([
    "Terminal",
    "iTerm2",
    "Ghostty",
    "Alacritty",
    "kitty",
    "Warp",
    "Hyper",
])


@dataclass
class Event:
    """A single captured user action."""

    type: EventType
    timestamp: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%S"))
    app: Optional[str] = None
    window: Optional[str] = None
    description: Optional[str] = None
    element: Optional[str] = None
    position_x: Optional[int] = None
    position_y: Optional[int] = None
    text_content: Optional[str] = None
    shortcut: Optional[str] = None
    screenshot_path: Optional[str] = None
    session_id: Optional[str] = None
    workflow_id: Optional[str] = None
    id: Optional[int] = None

    def to_dict(self) -> dict:
        """Serialize to dict for SQLite insertion."""
        d = asdict(self)
        d["type"] = self.type.value
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: dict) -> "Event":
        data = data.copy()
        data["type"] = EventType(data["type"])
        return cls(**data)

    @classmethod
    def from_row(cls, row) -> "Event":
        """Create from a sqlite3.Row."""
        return cls.from_dict(dict(row))
