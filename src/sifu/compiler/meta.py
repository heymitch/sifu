"""meta.json emitter — workflow metadata. Pure, deterministic."""

from datetime import datetime


def _parse(ts: str):
    try:
        return datetime.fromisoformat(ts)
    except (ValueError, TypeError):
        return None


def build_meta(workflow_id: str, rows: list) -> dict:
    rows = [dict(r) for r in rows]
    apps = sorted({r["app"] for r in rows if r.get("app")})
    times = [t for t in (_parse(r.get("timestamp")) for r in rows) if t]
    duration = int((max(times) - min(times)).total_seconds()) if len(times) >= 2 else 0
    sessions = [r.get("session_id") for r in rows if r.get("session_id")]
    return {
        "id": workflow_id,
        "captured_at": rows[0]["timestamp"] if rows and rows[0].get("timestamp") else None,
        "step_count": len(rows),
        "app_set": apps,
        "duration_seconds": duration,
        "source_session": sessions[0] if sessions else None,
    }
