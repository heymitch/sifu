"""Screenshot paths under ~/.sifu/screenshots/<day>/."""

from datetime import datetime
from pathlib import Path

SIFU_DIR = Path.home() / ".sifu"
SCREENSHOTS_DIR = SIFU_DIR / "screenshots"


def get_screenshot_path() -> Path:
    """Generate a timestamped path for a new screenshot."""
    now = datetime.now()
    day_dir = SCREENSHOTS_DIR / now.strftime("%Y-%m-%d")
    day_dir.mkdir(parents=True, exist_ok=True)
    filename = now.strftime("%H-%M-%S") + f"-{now.microsecond // 1000:03d}.jpg"
    return day_dir / filename
