"""Read-only aggregation over the library for the browser."""

from datetime import datetime

from sifu import library


def _title(md: str, fallback: str) -> str:
    for line in md.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def pretty_stamp(iso) -> str:
    """ISO timestamp -> friendly 'Jun 5, 2:23 PM' for the list view."""
    try:
        return datetime.fromisoformat(iso).strftime("%b %-d, %-I:%M %p")
    except (ValueError, TypeError):
        return ""


def timeline() -> list[dict]:
    rows = []
    for wid in library.list_units():
        u = library.read_unit(wid)
        captured = u["meta"].get("captured_at")
        rows.append({
            "id": wid,
            "title": _title(u["workflow_md"], wid),
            "captured_at": captured,
            "captured_pretty": pretty_stamp(captured),
            "step_count": u["meta"].get("step_count", len(u["macro"].get("steps", []))),
            "app_set": u["meta"].get("app_set", []),
        })
    return sorted(rows, key=lambda r: r["captured_at"] or "", reverse=True)
