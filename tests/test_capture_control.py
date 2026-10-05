"""How `sifu start/stop/pause/resume/sensitive/status` drive the capture process.

Each case runs the real CLI in a subprocess with sys.platform forced (darwin
unless noted) and HOME pointing at a scratch dir, so nothing here needs macOS.
SifuBar is "running" when ~/.sifu/sifubar.pid holds a live pid (this test
process), which means no case launches anything.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

CLI = "import sys; sys.platform = {!r}; from sifu.cli import main; main()"


@pytest.fixture
def home(tmp_path):
    (tmp_path / ".sifu").mkdir()
    return tmp_path


def _state(home: Path, **state):
    (home / ".sifu" / "daemon.state").write_text(json.dumps(state))


def _sifubar_running(home: Path):
    (home / ".sifu" / "sifubar.pid").write_text(str(os.getpid()))


def _sifu(home: Path, *args: str, platform: str = "darwin") -> str:
    env = {**os.environ, "HOME": str(home)}
    result = subprocess.run(
        [sys.executable, "-c", CLI.format(platform), *args],
        env=env, capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


def _sent(home: Path):
    path = home / ".sifu" / "command.json"
    return json.loads(path.read_text())["command"] if path.exists() else None


def test_start_sends_start_to_a_running_sifubar(home):
    _sifubar_running(home)
    _state(home, status="stopped")
    assert _sifu(home, "start") == "Sifu starting (via SifuBar).\n"
    assert _sent(home) == "start"


def test_start_when_already_recording_sends_nothing(home):
    _state(home, status="recording")
    assert _sifu(home, "start") == "Sifu is already running.\n"
    assert _sent(home) is None


def test_start_without_sifubar_explains_how_to_install(home):
    assert _sifu(home, "start") == (
        "SifuBar not found. Install SifuBar.app or build from extras/SifuBar.\n"
        "  cd extras/SifuBar && swift build -c release\n"
    )
    assert _sent(home) is None


def test_stop_sends_stop_then_analyzes(home):
    _sifubar_running(home)
    _state(home, status="recording")
    out = _sifu(home, "stop")
    assert _sent(home) == "stop"
    assert out.startswith("Sifu stopped.\n\nAnalyzing session...\n")
    assert "Compiling SOPs..." in out
    assert "Launching coach (background)..." in out


def test_stop_when_not_running(home):
    _state(home, status="stopped")
    assert _sifu(home, "stop") == "Sifu is not running.\n"
    assert _sent(home) is None


@pytest.mark.parametrize("command, status, said, sent", [
    ("pause", "recording", "Sifu paused.\n", "pause"),
    ("pause", "paused", "Sifu is not recording.\n", None),
    ("resume", "paused", "Sifu resumed.\n", "resume"),
    ("resume", "recording", "Sifu is not paused.\n", None),
    ("sensitive", "recording", "Purged last 5 minutes. Use 'sifu resume' to continue.\n", "sensitive"),
    ("sensitive", "stopped", "Sifu is not running.\n", None),
])
def test_pause_resume_sensitive(home, command, status, said, sent):
    _state(home, status=status)
    assert _sifu(home, command) == said
    assert _sent(home) == sent


def test_status_json_reads_state_and_pid(home):
    _sifubar_running(home)
    _state(home, status="recording", session_id="session-1", start_time="2026-10-03T10:00:00",
           events=7, pid=4242)
    info = json.loads(_sifu(home, "status", "--json"))
    info.pop("duration_min")
    assert info == {
        "running": True, "pid": 4242, "status": "recording", "session_id": "session-1",
        "start_time": "2026-10-03T10:00:00", "steps": 7,
    }


def test_status_when_stopped(home):
    assert _sifu(home, "status") == "  Sifu is not running.\n"


def test_start_on_a_platform_without_a_backend(home):
    _sifubar_running(home)
    assert _sifu(home, "start", platform="linux") == "No capture backend for linux yet.\n"
    assert _sent(home) is None


def test_status_on_a_platform_without_a_backend(home):
    _sifubar_running(home)
    _state(home, status="recording", pid=4242)
    assert json.loads(_sifu(home, "status", "--json", platform="linux"))["running"] is False
