"""Screenshot disk storage with FIFO eviction."""

import os
from pathlib import Path
from datetime import datetime

from sifu.config import load_config

SIFU_DIR = Path.home() / ".sifu"
SCREENSHOTS_DIR = SIFU_DIR / "screenshots"


def get_screenshot_path() -> Path:
    """Generate a timestamped path for a new screenshot."""
    now = datetime.now()
    day_dir = SCREENSHOTS_DIR / now.strftime("%Y-%m-%d")
    day_dir.mkdir(parents=True, exist_ok=True)
    filename = now.strftime("%H-%M-%S") + f"-{now.microsecond // 1000:03d}.jpg"
    return day_dir / filename


def get_disk_usage_mb() -> float:
    """Get total screenshot disk usage in MB."""
    total = 0
    if not SCREENSHOTS_DIR.exists():
        return 0.0
    for root, _dirs, files in os.walk(SCREENSHOTS_DIR):
        for f in files:
            total += os.path.getsize(os.path.join(root, f))
    return total / (1024 * 1024)


def evict_oldest():
    """Delete oldest screenshots until under budget."""
    config = load_config()
    budget_mb = config.get("screenshot_budget_mb", 1024)

    while get_disk_usage_mb() > budget_mb:
        oldest = None
        oldest_time = None
        for root, _dirs, files in os.walk(SCREENSHOTS_DIR):
            for f in files:
                fpath = os.path.join(root, f)
                mtime = os.path.getmtime(fpath)
                if oldest_time is None or mtime < oldest_time:
                    oldest = fpath
                    oldest_time = mtime
        if oldest:
            os.remove(oldest)
            parent = os.path.dirname(oldest)
            if not os.listdir(parent):
                os.rmdir(parent)
        else:
            break


def delete_screenshot(path: str):
    """Delete a specific screenshot file."""
    if path and os.path.exists(path):
        os.remove(path)
