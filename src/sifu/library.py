"""Canonical workflow library — one self-contained dir per workflow."""

import json
import shutil
from pathlib import Path
from typing import Optional

LIBRARY_DIR = Path.home() / ".sifu" / "library"


def unit_dir(workflow_id: str) -> Path:
    return LIBRARY_DIR / workflow_id


def write_unit(workflow_id: str, workflow_md: str, macro: dict,
               meta: dict, screenshots: list[Path]) -> Path:
    """Write a complete library unit. Overwrites an existing unit atomically-ish."""
    d = unit_dir(workflow_id)
    d.mkdir(parents=True, exist_ok=True)
    (d / "workflow.md").write_text(workflow_md, encoding="utf-8")
    (d / "macro.json").write_text(json.dumps(macro, indent=2), encoding="utf-8")
    (d / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    shots = d / "screenshots"
    shutil.rmtree(shots, ignore_errors=True)
    shots.mkdir(exist_ok=True)
    for i, src in enumerate(screenshots):
        src = Path(src)
        if src.exists():
            shutil.copy2(src, shots / f"{i:03d}{src.suffix or '.jpg'}")
    try:
        from sifu_ui.watcher import notify
        notify(workflow_id)
    except ImportError:
        pass  # sifu_ui is an optional extra
    return d


def list_units() -> list[str]:
    if not LIBRARY_DIR.exists():
        return []
    return [p.name for p in LIBRARY_DIR.iterdir()
            if p.is_dir() and (p / "macro.json").exists()]


def units_for_session(session_id: str) -> list[str]:
    """Library unit ids whose meta.json `source_session` matches `session_id`."""
    result = []
    for wf_id in list_units():
        meta_path = unit_dir(wf_id) / "meta.json"
        if not meta_path.exists():
            continue
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if meta.get("source_session") == session_id:
            result.append(wf_id)
    return result


def remove_unit(workflow_id: str) -> bool:
    """Delete a library unit directory. Returns True if it existed."""
    d = unit_dir(workflow_id)
    if d.exists() and d.is_dir():
        shutil.rmtree(d)
        return True
    return False


def latest_unit() -> Optional[str]:
    """Most recently COMPILED library unit — what the user just produced.

    Sorted by unit mtime, not capture time: 'Copy Last Workflow' should hand
    back the unit you just compiled, even if it came from an older recording
    than some other unit already in the library.
    """
    def _mtime(wid: str) -> float:
        try:
            return (unit_dir(wid) / "meta.json").stat().st_mtime
        except OSError:
            return 0.0

    units = list_units()
    return max(units, key=lambda w: (_mtime(w), w)) if units else None


def read_unit(workflow_id: str) -> Optional[dict]:
    d = unit_dir(workflow_id)
    if not (d / "macro.json").exists():
        return None
    return {
        "id": workflow_id,
        "dir": str(d),
        "workflow_md": (d / "workflow.md").read_text(encoding="utf-8") if (d / "workflow.md").exists() else "",
        "macro": json.loads((d / "macro.json").read_text(encoding="utf-8")),
        "meta": json.loads((d / "meta.json").read_text(encoding="utf-8")) if (d / "meta.json").exists() else {},
    }
