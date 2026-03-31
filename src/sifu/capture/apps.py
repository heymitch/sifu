"""AppTracker — Layer 0 application and window switch monitoring.

Uses NSWorkspace notifications for app switches and polls the Accessibility
API every second for window title changes.  No LLM calls.  No network.
"""

from __future__ import annotations

import threading
import time
from typing import Optional

from AppKit import NSWorkspace
from Foundation import NSObject
import ApplicationServices as AS
import objc

from sifu.events import Event, EventType
from sifu.storage.db import insert_event


class _AppObserver(NSObject):
    """NSObject subclass that acts as the NSWorkspace notification observer."""

    def initWithTracker_(self, tracker: "AppTracker") -> Optional["_AppObserver"]:
        self = objc.super(_AppObserver, self).init()
        if self is None:
            return None
        self.tracker = tracker
        return self

    def appDidActivate_(self, notification) -> None:
        """Fired by NSWorkspaceDidActivateApplicationNotification."""
        try:
            user_info = notification.userInfo()
            if user_info is None:
                return
            app_key = "NSWorkspaceApplicationKey"
            running_app = user_info.get(app_key)
            if running_app is None:
                return
            new_app = running_app.localizedName()
            self.tracker._on_app_switch(new_app)
        except Exception:
            # Never let an observer callback crash the run loop.
            pass


class AppTracker:
    """Monitors application and window switches using macOS APIs.

    Attributes:
        paused: When True, events are detected but not written to the DB.
        current_app: Name of the currently active application.
        current_window: Title of the currently focused window.
    """

    paused: bool = False
    current_app: Optional[str] = None
    current_window: Optional[str] = None

    def __init__(self, conn, session_id: str, config: dict) -> None:
        self._conn = conn
        self._session_id = session_id
        self._config = config
        self._ignore_apps: set[str] = set(config.get("ignore_apps", []))

        self._observer: Optional[_AppObserver] = None
        self._poll_timer: Optional[threading.Timer] = None
        self._stop_event = threading.Event()

    # ── Public API ───────────────────────────────────────────────────────────

    def start(self) -> None:
        """Start app-switch notifications and window-title polling."""
        # Snapshot initial state so first events are diffs, not surprises.
        ws = NSWorkspace.sharedWorkspace()
        front = ws.frontmostApplication()
        if front is not None:
            self.current_app = front.localizedName()
        self.current_window = self._get_window_title()

        # Register NSWorkspace notification observer.
        self._observer = _AppObserver.alloc().initWithTracker_(self)
        ws.notificationCenter().addObserver_selector_name_object_(
            self._observer,
            "appDidActivate:",
            "NSWorkspaceDidActivateApplicationNotification",
            None,
        )

        # Start window-title polling loop.
        self._stop_event.clear()
        self._schedule_poll()

    def stop(self) -> None:
        """Stop all capture and unregister the notification observer."""
        self._stop_event.set()

        if self._poll_timer is not None:
            self._poll_timer.cancel()
            self._poll_timer = None

        if self._observer is not None:
            NSWorkspace.sharedWorkspace().notificationCenter().removeObserver_(
                self._observer
            )
            self._observer = None

    # ── App-switch callback (called from NSWorkspace notification) ────────────

    def _on_app_switch(self, new_app: str) -> None:
        """Handle an application activation notification."""
        if self.paused:
            return
        if new_app == self.current_app:
            return
        if new_app in self._ignore_apps:
            self.current_app = new_app
            return

        prev_app = self.current_app or "unknown"
        description = f"Switched from {prev_app} to {new_app}"
        self.current_app = new_app

        event = Event(
            type=EventType.APP_SWITCH,
            app=new_app,
            window=self.current_window,
            description=description,
            session_id=self._session_id,
        )
        try:
            insert_event(self._conn, event)
        except Exception:
            pass

    # ── Window-title polling ─────────────────────────────────────────────────

    def _schedule_poll(self) -> None:
        """Schedule the next window-title poll, unless stop() was called."""
        if self._stop_event.is_set():
            return
        self._poll_timer = threading.Timer(3.0, self._poll_window_title)
        self._poll_timer.daemon = True
        self._poll_timer.start()

    def _poll_window_title(self) -> None:
        """Check the active window title; log if it changed."""
        try:
            title = self._get_window_title()
            if title is not None and title != self.current_window:
                self._on_window_switch(title)
            # Even if title is None, update to avoid stale state.
            if title is not None:
                self.current_window = title
        except Exception:
            pass
        finally:
            self._schedule_poll()

    def _on_window_switch(self, new_title: str) -> None:
        """Persist a WINDOW_SWITCH event."""
        if self.paused:
            return
        if self.current_app in self._ignore_apps:
            return

        event = Event(
            type=EventType.WINDOW_SWITCH,
            app=self.current_app,
            window=new_title,
            description=f"Window: {new_title}",
            session_id=self._session_id,
        )
        try:
            insert_event(self._conn, event)
        except Exception:
            pass

    # ── Accessibility helper ─────────────────────────────────────────────────

    def _get_window_title(self) -> Optional[str]:
        """Return the title of the currently focused window via AX API."""
        app = NSWorkspace.sharedWorkspace().frontmostApplication()
        if app is None:
            return None
        pid = app.processIdentifier()
        ax_app = AS.AXUIElementCreateApplication(pid)
        err, window = AS.AXUIElementCopyAttributeValue(
            ax_app, "AXFocusedWindow", None
        )
        if err == 0 and window:
            err, title = AS.AXUIElementCopyAttributeValue(window, "AXTitle", None)
            if err == 0 and title:
                return str(title)
        return None
