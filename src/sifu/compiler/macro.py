"""macro.json emitter — the Battleship/NavMacro contract (schema_version 1).

Pure and deterministic: rows in, dict out. No I/O, no LLM.
"""

import json
from typing import Optional

SCHEMA_VERSION = 1
_ACTION = {  # event type -> macro action
    "click": "click", "right_click": "click", "shortcut": "key",
    "text_input": "type", "command": "type",
    "app_switch": "app_switch", "window_switch": "app_switch",
}


def _arr(v) -> Optional[list]:
    if v is None or v == "":
        return None
    try:
        return json.loads(v) if isinstance(v, str) else list(v)
    except (ValueError, TypeError):
        return None


def _frame(row) -> Optional[dict]:
    wr = _arr(row.get("window_rect"))
    if wr is None:
        return None
    return {
        "display_id": row.get("display_id"),
        "display_bounds": _arr(row.get("display_bounds")),
        "window_rect": wr,
        "backing_scale": row.get("backing_scale"),
    }


def _expected(next_row) -> Optional[dict]:
    """Infer a post-condition from the NEXT step: prefer a url delta."""
    if next_row is None:
        return None
    url = next_row.get("url")
    if url:
        return {"kind": "url", "value": url}
    win = next_row.get("window")
    if win:
        return {"kind": "window_title", "value": win}
    return None


def build_macro(workflow_id: str, rows: list) -> dict:
    steps = []
    for i, row in enumerate(rows):
        row = dict(row)  # accept sqlite3.Row or dict
        frame = _frame(row)
        px, py = row.get("position_x"), row.get("position_y")
        coords = None
        if px is not None and py is not None:
            coords = {"x": px, "y": py,
                      "rel_to": "window" if frame else "screen"}
        nxt = dict(rows[i + 1]) if i + 1 < len(rows) else None
        steps.append({
            "index": i,
            "action": _ACTION.get(row.get("type"), "click"),
            "app": row.get("app"),
            "frame": frame,
            "coords": coords,
            "url": row.get("url"),
            "screenshot": f"screenshots/{i:03d}.jpg" if row.get("screenshot_path") else None,
            "text": row.get("text_content"),
            "key": row.get("shortcut"),
            "expected": _expected(nxt),
        })
    return {"schema_version": SCHEMA_VERSION, "workflow_id": workflow_id, "steps": steps}
