"""Checks that only mean something on a real Mac. Skipped elsewhere."""

import subprocess
import sys

import pytest

from sifu import context_cmd, library

pytestmark = pytest.mark.skipif(sys.platform != "darwin", reason="needs macOS (pbcopy/pbpaste)")


def _paste() -> str:
    return subprocess.run(["pbpaste"], capture_output=True, text=True, check=True).stdout


@pytest.fixture
def clipboard():
    """Restores the user's clipboard text afterwards. Non-text contents (an image) are not kept."""
    saved = _paste()
    yield
    subprocess.run(["pbcopy"], input=saved, text=True, check=True)


def test_copy_last_puts_the_briefing_on_the_clipboard(tmp_path, monkeypatch, clipboard):
    monkeypatch.setattr(library, "LIBRARY_DIR", tmp_path / "library")
    library.write_unit(
        "wf-clip-001", "# Clipboard round trip\nPaste me.",
        {"schema_version": 1, "workflow_id": "wf-clip-001", "steps": []},
        {"id": "wf-clip-001", "app_set": ["Terminal"]},
        [],
    )
    context_cmd.copy_last()
    pasted = _paste()
    assert pasted == context_cmd.render_latest()
    assert "Clipboard round trip" in pasted
