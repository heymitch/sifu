"""Idempotent local setup the agent runs during install."""

from sifu import library


def run() -> dict:
    library.LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
    return {
        "library": str(library.LIBRARY_DIR),
        "next": "Run `sifu start` to begin capture, then `sifu context <task>`.",
    }
