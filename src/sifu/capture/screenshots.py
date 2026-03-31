"""Smart screenshot capture with deduplication for Sifu Layer 0."""

import logging
import time
import threading
from typing import Optional

from sifu.events import Event, EventType

logger = logging.getLogger(__name__)


class ScreenshotCapture:
    """Captures screenshots on significant events, skipping duplicates.

    Thread-safe: capture() may be called concurrently from the mouse
    and keyboard tap callbacks.
    """

    def __init__(self, config: dict) -> None:
        self._config = config
        self._min_interval: float = config.get("screenshot_min_interval_s", 2.0)

        # Dedup state — guarded by _lock
        self._last_app: Optional[str] = None
        self._last_window: Optional[str] = None
        self._last_time: float = 0.0

        # Periodic disk-budget counter — guarded by _lock
        self._capture_count: int = 0

        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def capture(self, event: Event) -> Optional[str]:
        """Conditionally capture a screenshot for the given event.

        Returns the saved file path, or None if the screenshot was skipped.
        The caller is responsible for storing the returned path on
        event.screenshot_path before persisting the event.
        """
        with self._lock:
            if not self._should_capture(event):
                return None

            path = self._take_screenshot()

            if path:
                self._last_app = event.app
                self._last_window = event.window
                self._last_time = time.time()

        return path

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _should_capture(self, event: Event) -> bool:
        """Return True if a screenshot should be taken for this event.

        Must be called with self._lock held.
        """
        # Skip mid-typing text events; we screenshot only on text flush.
        if event.type == EventType.TEXT_INPUT:
            return False

        # Skip if the context hasn't changed and it's too soon.
        if (
            self._last_app == event.app
            and self._last_window == event.window
            and time.time() - self._last_time < self._min_interval
        ):
            return False

        return True

    def _take_screenshot(self) -> Optional[str]:
        """Capture the full screen and save it as a JPEG.

        Returns the absolute file path on success, None on failure.
        Must be called with self._lock held (counter update is serialised).
        """
        try:
            from Quartz import (
                CGWindowListCreateImage,
                CGRectInfinite,
                kCGWindowListOptionOnScreenOnly,
                kCGNullWindowID,
            )
            from AppKit import NSBitmapImageRep, NSJPEGFileType, NSImageCompressionFactor
        except ImportError:
            logger.error(
                "Quartz/AppKit not available — screenshot capture requires macOS "
                "with pyobjc installed."
            )
            return None

        try:
            image = CGWindowListCreateImage(
                CGRectInfinite,
                kCGWindowListOptionOnScreenOnly,
                kCGNullWindowID,
                0,  # kCGWindowImageDefault
            )
        except Exception:
            logger.exception("CGWindowListCreateImage failed")
            return None

        if image is None:
            logger.warning("CGWindowListCreateImage returned None")
            return None

        try:
            bitmap = NSBitmapImageRep.alloc().initWithCGImage_(image)
            quality = self._config.get("screenshot_quality", 80) / 100.0
            data = bitmap.representationUsingType_properties_(
                NSJPEGFileType,
                {NSImageCompressionFactor: quality},
            )

            if data is None:
                logger.warning("JPEG representation returned None")
                return None

            from sifu.storage.disk import get_screenshot_path, evict_oldest

            path = get_screenshot_path()
            success = data.writeToFile_atomically_(str(path), True)

            if not success:
                logger.warning("Failed to write screenshot to %s", path)
                return None

            # Periodic disk-budget enforcement (every 100 screenshots).
            self._capture_count += 1
            if self._capture_count % 100 == 0:
                try:
                    evict_oldest()
                except Exception:
                    logger.exception("evict_oldest() failed")

            return str(path)

        except Exception:
            logger.exception("Unexpected error during screenshot capture")
            return None
