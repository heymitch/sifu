"""Keyboard capture for Sifu — Layer 0.

Monitors keystrokes via CGEventTap and logs them as:
  - EventType.SHORTCUT   when modifier keys accompany a regular key
  - EventType.TEXT_INPUT when plain text is typed (buffered, flushed on Enter or 2s idle)
  - EventType.COMMAND    when Enter is pressed inside a terminal app

Password fields (AXSecureTextField) are silently skipped.
Events are discarded when self.paused is True or the active app is on the ignore list.
"""

import json
import logging
import threading
import time
from pathlib import Path
from typing import Optional

import ApplicationServices as AS
from AppKit import NSWorkspace
from Quartz import (
    CFMachPortCreateRunLoopSource,
    CFRunLoopAddSource,
    CFRunLoopGetCurrent,
    CGEventGetFlags,
    CGEventGetIntegerValueField,
    CGEventMaskBit,
    CGEventTapCreate,
    CGEventTapEnable,
    kCFRunLoopCommonModes,
    kCGEventKeyDown,
    kCGEventTapOptionListenOnly,
    kCGHeadInsertEventTap,
    kCGKeyboardEventKeycode,
    kCGSessionEventTap,
)

from sifu.events import Event, EventType, TERMINAL_APPS
from sifu.storage.db import insert_event

logger = logging.getLogger(__name__)

# ── Keycode table ────────────────────────────────────────────────────────────

KEYCODES_PATH = Path(__file__).parent.parent.parent.parent / "data" / "keycodes.json"

try:
    with open(KEYCODES_PATH) as _f:
        KEYCODES: dict[str, str] = json.load(_f)
except FileNotFoundError:
    logger.warning("keycodes.json not found at %s — keycode mapping disabled", KEYCODES_PATH)
    KEYCODES = {}

# Keycode 36 = Return / Enter
_KEYCODE_RETURN = 36

# Modifier-only keycodes — these alone don't produce a shortcut event
_MODIFIER_KEYCODES = frozenset([
    55,   # Command
    56,   # Shift
    57,   # CapsLock
    58,   # Option
    59,   # Control
    60,   # RightShift
    61,   # RightOption
    62,   # RightControl
    63,   # Function
])

# ── Modifier flag constants ──────────────────────────────────────────────────

kCGEventFlagMaskCommand = 0x100000
kCGEventFlagMaskShift = 0x20000
kCGEventFlagMaskAlternate = 0x80000
kCGEventFlagMaskControl = 0x40000

# ── State file ───────────────────────────────────────────────────────────────

STATE_FILE = Path.home() / ".sifu" / "daemon.state"


# ── Helpers ──────────────────────────────────────────────────────────────────


def _get_app_name() -> Optional[str]:
    """Return the localized name of the frontmost application."""
    app = NSWorkspace.sharedWorkspace().frontmostApplication()
    return app.localizedName() if app else None


def _get_window_title() -> Optional[str]:
    """Return the AXTitle of the focused window via Accessibility API."""
    app = NSWorkspace.sharedWorkspace().frontmostApplication()
    if not app:
        return None
    pid = app.processIdentifier()
    ax_app = AS.AXUIElementCreateApplication(pid)
    err, focused_win = AS.AXUIElementCopyAttributeValue(
        ax_app, "AXFocusedWindow", None
    )
    if err != 0 or not focused_win:
        return None
    err, title = AS.AXUIElementCopyAttributeValue(focused_win, "AXTitle", None)
    if err == 0 and title:
        return str(title)
    return None


def _is_password_field() -> bool:
    """Return True if the focused element has role AXSecureTextField."""
    app = NSWorkspace.sharedWorkspace().frontmostApplication()
    if not app:
        return False
    pid = app.processIdentifier()
    ax_app = AS.AXUIElementCreateApplication(pid)
    err, focused = AS.AXUIElementCopyAttributeValue(
        ax_app, "AXFocusedUIElement", None
    )
    if err == 0 and focused:
        err, role = AS.AXUIElementCopyAttributeValue(focused, "AXRole", None)
        if err == 0 and role == "AXSecureTextField":
            return True
    return False


def _build_modifier_string(flags: int, key_name: str) -> Optional[str]:
    """Return a shortcut string like 'Cmd+C' or None if no actionable modifiers."""
    parts: list[str] = []
    if flags & kCGEventFlagMaskCommand:
        parts.append("Cmd")
    if flags & kCGEventFlagMaskShift:
        parts.append("Shift")
    if flags & kCGEventFlagMaskAlternate:
        parts.append("Opt")
    if flags & kCGEventFlagMaskControl:
        parts.append("Ctrl")

    if not parts:
        return None  # No actionable modifiers — plain keystroke

    return "+".join(parts) + "+" + key_name


# ── Main class ───────────────────────────────────────────────────────────────


class KeyboardCapture:
    """Monitor keyboard events via CGEventTap and log them to SQLite."""

    paused: bool = False

    def __init__(self, conn, session_id: str, config: dict) -> None:
        self._conn = conn
        self._session_id = session_id
        self._config = config
        self._ignore_apps: set[str] = set(config.get("ignore_apps", []))

        self._text_buffer: list[str] = []
        self._flush_timer: Optional[threading.Timer] = None
        self._flush_lock = threading.Lock()

        self._screenshot_callback = None
        self._tap = None
        self._run_loop_source = None

    # ── Public interface ─────────────────────────────────────────────────────

    def start(self, screenshot_callback=None) -> None:
        """Create the CGEventTap and attach it to the current run loop."""
        self._screenshot_callback = screenshot_callback

        event_mask = CGEventMaskBit(kCGEventKeyDown)

        self._tap = CGEventTapCreate(
            kCGSessionEventTap,
            kCGHeadInsertEventTap,
            kCGEventTapOptionListenOnly,
            event_mask,
            self._event_callback,
            None,
        )

        if not self._tap:
            logger.error(
                "Failed to create keyboard CGEventTap. "
                "Grant Accessibility access in System Settings → Privacy → Accessibility."
            )
            return

        self._run_loop_source = CFMachPortCreateRunLoopSource(None, self._tap, 0)
        CFRunLoopAddSource(CFRunLoopGetCurrent(), self._run_loop_source, kCFRunLoopCommonModes)
        CGEventTapEnable(self._tap, True)
        logger.debug("KeyboardCapture started.")

    def stop(self) -> None:
        """Flush pending text and disable the event tap."""
        self._cancel_flush_timer()
        self._flush_buffer()
        if self._tap:
            CGEventTapEnable(self._tap, False)
            logger.debug("KeyboardCapture stopped.")

    # ── CGEventTap callback ──────────────────────────────────────────────────

    def _event_callback(self, proxy, event_type, event, refcon):
        """Called by CGEventTap for every kCGEventKeyDown event."""
        try:
            self._handle_event(event)
        except Exception:
            logger.exception("Unhandled exception in keyboard event callback")
        # Listen-only tap: must return the event proxy unmodified.
        return event

    def _handle_event(self, event) -> None:
        if self.paused:
            return

        # Resolve frontmost app before any guard so a single AX call is made.
        app_name = _get_app_name()

        if app_name and app_name in self._ignore_apps:
            return

        keycode = int(CGEventGetIntegerValueField(event, kCGKeyboardEventKeycode))
        flags = int(CGEventGetFlags(event))

        # Strip CapsLock and other non-modifier bits from flags for comparison.
        # We only care about Cmd, Shift, Opt, Ctrl.
        actionable_flags = flags & (
            kCGEventFlagMaskCommand
            | kCGEventFlagMaskShift
            | kCGEventFlagMaskAlternate
            | kCGEventFlagMaskControl
        )

        key_name = KEYCODES.get(str(keycode), f"key{keycode}")

        # ── Bare modifier key press — ignore ────────────────────────────────
        if keycode in _MODIFIER_KEYCODES:
            return

        # ── Shortcut: any actionable modifier held down ──────────────────────
        # Shift alone with a regular key is not a shortcut (it just capitalises).
        # Cmd, Ctrl, or Opt + any key → always a shortcut.
        has_cmd_ctrl_opt = bool(
            actionable_flags & (
                kCGEventFlagMaskCommand
                | kCGEventFlagMaskAlternate
                | kCGEventFlagMaskControl
            )
        )

        if has_cmd_ctrl_opt:
            self._handle_shortcut(event, keycode, key_name, flags, app_name)
            return

        # ── Plain keystroke ──────────────────────────────────────────────────

        # Skip password fields for ALL plain keystrokes
        if _is_password_field():
            return

        # Enter key — flush buffer (as command or text) then done
        if keycode == _KEYCODE_RETURN:
            self._handle_enter(app_name)
            return

        # Accumulate character into text buffer
        char = self._keycode_to_char(keycode, actionable_flags)
        if char:
            self._accumulate(char, app_name)

    # ── Shortcut handling ────────────────────────────────────────────────────

    def _handle_shortcut(
        self, event, keycode: int, key_name: str, flags: int, app_name: Optional[str]
    ) -> None:
        if _is_password_field():
            return

        shortcut = _build_modifier_string(flags, key_name)
        if not shortcut:
            return

        window = _get_window_title()
        ev = Event(
            type=EventType.SHORTCUT,
            app=app_name,
            window=window,
            shortcut=shortcut,
            description=f"Shortcut: {shortcut}",
            session_id=self._session_id,
        )
        insert_event(self._conn, ev)
        self._increment_event_count()

        if self._screenshot_callback:
            try:
                path = self._screenshot_callback(ev)
                if path:
                    self._conn.execute(
                        "UPDATE events SET screenshot_path = ? WHERE id = (SELECT MAX(id) FROM events)",
                        (path,),
                    )
                    self._conn.commit()
            except Exception:
                logger.exception("Screenshot callback failed for shortcut event")

    # ── Text buffer / flush ──────────────────────────────────────────────────

    def _accumulate(self, char: str, app_name: Optional[str]) -> None:
        """Add a character to the buffer and reset the idle flush timer."""
        with self._flush_lock:
            self._text_buffer.append(char)
        self._reset_flush_timer(app_name)

    def _reset_flush_timer(self, app_name: Optional[str]) -> None:
        """Cancel any existing timer and start a fresh 2-second one."""
        self._cancel_flush_timer()
        self._flush_timer = threading.Timer(
            2.0, self._flush_buffer, kwargs={"app_name": app_name}
        )
        self._flush_timer.daemon = True
        self._flush_timer.start()

    def _cancel_flush_timer(self) -> None:
        if self._flush_timer is not None:
            self._flush_timer.cancel()
            self._flush_timer = None

    def _handle_enter(self, app_name: Optional[str]) -> None:
        """Enter was pressed — flush the buffer as COMMAND or TEXT_INPUT."""
        self._cancel_flush_timer()
        self._flush_buffer(app_name=app_name, enter_pressed=True)

    def _flush_buffer(
        self,
        app_name: Optional[str] = None,
        enter_pressed: bool = False,
    ) -> None:
        """Flush the accumulated text buffer as a single event."""
        with self._flush_lock:
            if not self._text_buffer:
                return
            text = "".join(self._text_buffer)
            self._text_buffer.clear()

        if self.paused:
            return

        # Resolve app name at flush time if not supplied (timer-based flush)
        if app_name is None:
            app_name = _get_app_name()

        if app_name and app_name in self._ignore_apps:
            return

        # Determine event type
        is_terminal = app_name in TERMINAL_APPS if app_name else False
        if enter_pressed and is_terminal:
            event_type = EventType.COMMAND
            description = f"Command: {text}"
        else:
            event_type = EventType.TEXT_INPUT
            description = f"Typed: {text[:60]}{'…' if len(text) > 60 else ''}"

        window = _get_window_title()
        ev = Event(
            type=event_type,
            app=app_name,
            window=window,
            text_content=text,
            description=description,
            session_id=self._session_id,
        )
        insert_event(self._conn, ev)
        self._increment_event_count()

        if self._screenshot_callback:
            try:
                path = self._screenshot_callback(ev)
                if path:
                    self._conn.execute(
                        "UPDATE events SET screenshot_path = ? WHERE id = (SELECT MAX(id) FROM events)",
                        (path,),
                    )
                    self._conn.commit()
            except Exception:
                logger.exception("Screenshot callback failed for text/command flush")

    # ── State file ───────────────────────────────────────────────────────────

    def _increment_event_count(self) -> None:
        """Bump the event counter in daemon.state (best-effort)."""
        try:
            if STATE_FILE.exists():
                with open(STATE_FILE) as f:
                    state = json.load(f)
                state["events"] = state.get("events", 0) + 1
                with open(STATE_FILE, "w") as f:
                    json.dump(state, f)
        except Exception:
            logger.debug("Could not update daemon state file", exc_info=True)

    # ── Keycode → character ──────────────────────────────────────────────────

    def _keycode_to_char(self, keycode: int, flags: int) -> Optional[str]:
        """Map a keycode to a printable character, respecting Shift."""
        name = KEYCODES.get(str(keycode))
        if not name:
            return None

        # Non-printable keys — skip adding them to the text buffer
        non_printable = {
            "Return", "Tab", "Delete", "ForwardDelete", "Escape",
            "Command", "Shift", "CapsLock", "Option", "Control",
            "RightShift", "RightOption", "RightControl", "Function",
            "LeftArrow", "RightArrow", "UpArrow", "DownArrow",
            "Home", "End", "PageUp", "PageDown",
            "F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8",
            "F9", "F10", "F11", "F12", "F13", "F14", "F15",
        }
        if name in non_printable:
            return None

        # Space
        if name == "Space":
            return " "

        # Single character — apply Shift to produce uppercase/symbol
        if len(name) == 1:
            shift_held = bool(flags & kCGEventFlagMaskShift)
            if shift_held:
                return _SHIFT_MAP.get(name, name.upper())
            return name

        return None


# ── Shift key character map ──────────────────────────────────────────────────
# Maps unshifted key names to their shifted equivalents for US keyboard layout.

_SHIFT_MAP: dict[str, str] = {
    "1": "!", "2": "@", "3": "#", "4": "$", "5": "%",
    "6": "^", "7": "&", "8": "*", "9": "(", "0": ")",
    "-": "_", "=": "+", "[": "{", "]": "}", "\\": "|",
    ";": ":", "'": '"', ",": "<", ".": ">", "/": "?", "`": "~",
}
