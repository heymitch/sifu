"""
LLM CLI resolution — finds the claude binary dynamically.

Works for any user's install: Homebrew, npm global, .local/bin, nvm, etc.
Caches the result after first lookup.
"""

import os
import shutil
import subprocess
from pathlib import Path

_claude_path: str | None = None


def find_claude() -> str:
    """Find the claude CLI binary. Caches after first call.

    Search order:
    1. CLAUDE_BIN env var (explicit override)
    2. shutil.which (respects current PATH)
    3. Common install locations (for daemon/background processes that lose PATH)
    4. Shell login PATH (ask the user's shell where it is)
    """
    global _claude_path
    if _claude_path is not None:
        return _claude_path

    # 1. Explicit override
    env_bin = os.environ.get("CLAUDE_BIN")
    if env_bin and Path(env_bin).is_file():
        _claude_path = env_bin
        return _claude_path

    # 2. shutil.which (works when PATH is inherited)
    which = shutil.which("claude")
    if which:
        _claude_path = which
        return _claude_path

    # 3. Common install locations
    common_paths = [
        Path.home() / ".local" / "bin" / "claude",
        Path.home() / ".nvm" / "versions" / "node",  # will glob below
        Path("/usr/local/bin/claude"),
        Path("/opt/homebrew/bin/claude"),
        Path.home() / ".npm-global" / "bin" / "claude",
        Path.home() / "node_modules" / ".bin" / "claude",
    ]

    for p in common_paths:
        if p.is_file() and os.access(p, os.X_OK):
            _claude_path = str(p)
            return _claude_path

    # nvm: glob through node versions
    nvm_base = Path.home() / ".nvm" / "versions" / "node"
    if nvm_base.exists():
        for version_dir in sorted(nvm_base.iterdir(), reverse=True):
            candidate = version_dir / "bin" / "claude"
            if candidate.is_file():
                _claude_path = str(candidate)
                return _claude_path

    # 4. Ask the user's login shell
    try:
        shell = os.environ.get("SHELL", "/bin/zsh")
        result = subprocess.run(
            [shell, "-l", "-c", "which claude"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            path = result.stdout.strip()
            if Path(path).is_file():
                _claude_path = path
                return _claude_path
    except (subprocess.TimeoutExpired, OSError):
        pass

    raise FileNotFoundError(
        "Could not find the 'claude' CLI. Install it (https://claude.ai/download) "
        "or set CLAUDE_BIN=/path/to/claude in your environment."
    )


def claude_cmd(*args: str) -> list[str]:
    """Build a claude CLI command list. Use instead of hardcoding ['claude', ...]."""
    return [find_claude(), *args]
