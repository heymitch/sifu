"""Mouse capture for Sifu — Layer 0.

Installs a CGEventTap that records left and right mouse clicks, enriches each
event with accessibility context (app name, window title, element label), and
stores the result in SQLite.  A 300 ms timer fires the screenshot callback
*after* the click so the UI has had time to react.
"""

import json
import sqlite3
import threading
from pathlib import Path
from typing import Optional, Callable

from Quartz import (
    CGEventTapCreate,
    CGEventTapEnable,
    CGEventMaskBit,
    kCGSessionEventTap,
    kCGHeadInsertEventTap,
    kCGEventTapOptionListenOnly,
    kCGEventLeftMouseDown,
    kCGEventRightMouseDown,
    CGEventGetLocation,
    CFMachPortCreateRunLoopSource,
    CFRunLoopGetCurrent,
    CFRunLoopAddSource,
    kCFRunLoopCommonModes,
)
from AppKit import NSWorkspace

import ApplicationServices as AS

from sifu.events import Event, EventType
from sifu.storage.db import insert_event

SIFU_DIR = Path.home() / ".sifu"
STATE_FILE = SIFU_DIR / "daemon.state"

_MASK = CGEventMaskBit(kCGEventLeftMouseDown) | CGEventMaskBit(kCGEventRightMouseDown)


class MouseCapture:
    """Captures mouse click events via a macOS CGEventTap."""

    paused: bool = False

    def __init__(self, conn: sqlite3.Connection, session_id: str, config: dict):
        self._conn = conn
        self._session_id = session_id
        self._config = config
        self._ignore_apps: set[str] = set(config.get("ignore_apps", []))
        self._tap = None
        self._run_loop_source = None

    # ── Public API ──────────────────────────────────────────────────────────

    def start(self, screenshot_callback: Optional[Callable] = None):
        """Install the CGEventTap and add its source to the current run loop."""
        self._screenshot_callback = screenshot_callback

        self._tap = CGEventTapCreate(
            kCGSessionEventTap,
            kCGHeadInsertEventTap,
            kCGEventTapOptionListenOnly,
            _MASK,
            self._handle_event,
            None,
        )
        if self._tap is None:
            # Accessibility permission not granted — daemon will still run, but
            # mouse events won't be captured.
            import sys
            print(
                "[sifu] WARNING: CGEventTap creation failed.  "
                "Grant Accessibility permission in System Settings → Privacy → Accessibility.",
                file=sys.stderr,
            )
            return

        self._run_loop_source = CFMachPortCreateRunLoopSource(None, self._tap, 0)
        CFRunLoopAddSource(CFRunLoopGetCurrent(), self._run_loop_source, kCFRunLoopCommonModes)
        CGEventTapEnable(self._tap, True)

    def stop(self):
        """Disable the event tap."""
        if self._tap is not None:
            CGEventTapEnable(self._tap, False)
            self._tap = None

    # ── CGEventTap callback ─────────────────────────────────────────────────

    def _handle_event(self, proxy, event_type, cg_event, refcon):
        """Called by macOS for every matched event.  Must return the event."""
        try:
            if self.paused:
                return cg_event

            if event_type == kCGEventLeftMouseDown:
                ev_type = EventType.CLICK
            elif event_type == kCGEventRightMouseDown:
                ev_type = EventType.RIGHT_CLICK
            else:
                return cg_event

            loc = CGEventGetLocation(cg_event)
            x, y = int(loc.x), int(loc.y)

            app_name = self._get_frontmost_app()

            if app_name and app_name in self._ignore_apps:
                return cg_event

            window_title = self._get_window_title()
            element_label = self._get_element_at_position(x, y)

            if element_label:
                description = f"Clicked '{element_label}' in {app_name or 'unknown'}"
            else:
                description = f"Clicked at ({x}, {y}) in {app_name or 'unknown'}"

            event = Event(
                type=ev_type,
                app=app_name,
                window=window_title,
                description=description,
                element=element_label,
                position_x=x,
                position_y=y,
                session_id=self._session_id,
            )

            event_id = insert_event(self._conn, event)
            event.id = event_id

            self._increment_state_event_count()

            if self._screenshot_callback is not None:
                t = threading.Timer(0.3, self._screenshot_callback, args=(event,))
                t.daemon = True
                t.start()

        except Exception:
            # Never crash the run loop
            pass

        return cg_event

    # ── Accessibility helpers ────────────────────────────────────────────────

    def _get_frontmost_app(self) -> Optional[str]:
        """Return the localized name of the frontmost application."""
        ws = NSWorkspace.sharedWorkspace()
        app = ws.frontmostApplication()
        if app:
            return app.localizedName()
        return None

    def _get_element_at_position(self, x: float, y: float) -> Optional[str]:
        """Return the accessibility element label (description or title) at (x, y)."""
        err, element = AS.AXUIElementCopyElementAtPosition(
            AS.AXUIElementCreateSystemWide(), x, y
        )
        if err != 0 or not element:
            return None

        # Skip password fields — privacy rule
        err_role, role = AS.AXUIElementCopyAttributeValue(element, "AXRole", None)
        if err_role == 0 and role == "AXSecureTextField":
            return None

        # Prefer AXDescription (descriptive label)
        err_desc, label = AS.AXUIElementCopyAttributeValue(element, "AXDescription", None)
        if err_desc == 0 and label:
            return str(label)

        # Fall back to AXTitle (button labels, window titles)
        err_title, title = AS.AXUIElementCopyAttributeValue(element, "AXTitle", None)
        if err_title == 0 and title:
            return str(title)

        return None

    def _get_window_title(self) -> Optional[str]:
        """Return the title of the focused window via the Accessibility API."""
        app = NSWorkspace.sharedWorkspace().frontmostApplication()
        if not app:
            return None

        pid = app.processIdentifier()
        ax_app = AS.AXUIElementCreateApplication(pid)

        err, window = AS.AXUIElementCopyAttributeValue(ax_app, "AXFocusedWindow", None)
        if err != 0 or not window:
            return None

        err, title = AS.AXUIElementCopyAttributeValue(window, "AXTitle", None)
        if err == 0 and title:
            return str(title)

        return None

    # ── State file helpers ───────────────────────────────────────────────────

    def _increment_state_event_count(self):
        """Read daemon.state, increment event counter, write it back."""
        try:
            if STATE_FILE.exists():
                with open(STATE_FILE) as f:
                    state = json.load(f)
            else:
                state = {}

            state["events"] = state.get("events", 0) + 1

            SIFU_DIR.mkdir(parents=True, exist_ok=True)
            with open(STATE_FILE, "w") as f:
                json.dump(state, f)
        except Exception:
            # State file update is best-effort; never crash the capture loop
            pass
