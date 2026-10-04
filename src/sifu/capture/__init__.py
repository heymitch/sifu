"""Talking to the capture process.

Capture runs in its own process (SifuBar.app on macOS). The core reads
~/.sifu/daemon.state and sends commands through ~/.sifu/command.json; see
docs/capture-contract.md. A backend only knows how to find and launch its
process.
"""

import json
import os
import sys
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable, Optional

SIFU_DIR = Path.home() / ".sifu"
STATE_FILE = SIFU_DIR / "daemon.state"
COMMAND_FILE = SIFU_DIR / "command.json"
LOG_FILE = SIFU_DIR / "daemon.log"


class Command(str, Enum):
    START = "start"
    STOP = "stop"
    PAUSE = "pause"
    RESUME = "resume"
    SENSITIVE = "sensitive"


@dataclass(frozen=True)
class CaptureBackend:
    name: str
    pid_file: Path
    launch: Callable[[], bool]  # start the capture process; False when it is not installed
    install_hint: str


def read_state() -> dict:
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def send(command: Command) -> None:
    SIFU_DIR.mkdir(parents=True, exist_ok=True)
    with open(COMMAND_FILE, "w") as f:
        json.dump({"command": command.value, "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S")}, f)


def is_running(backend: CaptureBackend) -> bool:
    try:
        os.kill(int(backend.pid_file.read_text().strip()), 0)
        return True
    except (OSError, ValueError):
        return False


def current_backend() -> Optional[CaptureBackend]:
    from sifu.capture.sifubar import SIFUBAR

    return {"darwin": SIFUBAR}.get(sys.platform)
