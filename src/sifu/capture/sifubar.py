"""macOS capture backend: SifuBar.app (Swift, extras/SifuBar)."""

import subprocess
import time
from pathlib import Path

from sifu.capture import LOG_FILE, SIFU_DIR, CaptureBackend

REPO = Path(__file__).resolve().parents[3]


def _launch() -> bool:
    app_paths = [
        Path("/Applications/SifuBar.app"),
        Path.home() / "Applications" / "SifuBar.app",
        REPO / "extras" / "SifuBar" / ".build" / "release" / "SifuBar",
    ]
    for app_path in app_paths:
        if app_path.exists():
            if app_path.suffix == ".app":
                subprocess.Popen(["open", str(app_path)])
            else:
                subprocess.Popen(
                    [str(app_path)],
                    stdout=open(LOG_FILE, "a"),
                    stderr=open(LOG_FILE, "a"),
                    start_new_session=True,
                )
            time.sleep(2)
            return True
    return False


SIFUBAR = CaptureBackend(
    name="SifuBar",
    pid_file=SIFU_DIR / "sifubar.pid",
    launch=_launch,
    install_hint=(
        "SifuBar not found. Install SifuBar.app or build from extras/SifuBar.\n"
        "  cd extras/SifuBar && swift build -c release"
    ),
)
