"""Checks that only mean something on a real Mac.

They touch real system state (the clipboard), so they are opt-in:
    SIFU_MAC_TESTS=1 pytest tests/test_macos.py
Anything on the clipboard, including images, is replaced and not restored.
"""

import os
import subprocess
import sys

import pytest

from sifu import context_cmd, library

pytestmark = [
    pytest.mark.skipif(sys.platform != "darwin", reason="needs macOS (pbcopy/pbpaste)"),
    pytest.mark.skipif(os.environ.get("SIFU_MAC_TESTS") != "1",
                       reason="overwrites the clipboard; set SIFU_MAC_TESTS=1 to run"),
]


def test_copy_last_puts_the_briefing_on_the_clipboard(tmp_path, monkeypatch):
    monkeypatch.setattr(library, "LIBRARY_DIR", tmp_path / "library")
    library.write_unit(
        "wf-clip-001", "# Clipboard round trip\nPaste me.",
        {"schema_version": 1, "workflow_id": "wf-clip-001", "steps": []},
        {"id": "wf-clip-001", "app_set": ["Terminal"]},
        [],
    )
    context_cmd.copy_last()
    pasted = subprocess.run(["pbpaste"], capture_output=True, text=True, check=True).stdout
    assert pasted == context_cmd.render_latest()
    assert "Clipboard round trip" in pasted
