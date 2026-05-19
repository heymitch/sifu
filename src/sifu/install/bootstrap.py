"""Idempotent local setup the agent runs during install."""

from sifu import library


def run() -> dict:
    library.LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
    return {
        "library": str(library.LIBRARY_DIR),
        "next": "Open the SifuBar menu to start capture, then use `sifu context <query>` to hand a recorded workflow to your agent.",
    }
