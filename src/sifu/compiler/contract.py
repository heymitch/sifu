"""Validate a macro dict against the Battleship contract (schema_version 1)."""

SCHEMA_VERSION = 1
_ACTIONS = {"click", "key", "type", "app_switch"}
_REL = {"window", "screen"}
_EXPECTED_KINDS = {"url", "window_title"}


class ContractError(ValueError):
    pass


def validate_macro(m: dict) -> None:
    if m.get("schema_version") != SCHEMA_VERSION:
        raise ContractError(f"schema_version must be {SCHEMA_VERSION}, got {m.get('schema_version')}")
    if not m.get("workflow_id"):
        raise ContractError("workflow_id is required")
    if not isinstance(m.get("steps"), list):
        raise ContractError("steps must be a list")
    for i, s in enumerate(m["steps"]):
        if s.get("action") not in _ACTIONS:
            raise ContractError(f"step {i}: action {s.get('action')!r} not in {_ACTIONS}")
        c = s.get("coords")
        if c is not None:
            if not {"x", "y", "rel_to"} <= set(c):
                raise ContractError(f"step {i}: coords needs x,y,rel_to")
            if c["rel_to"] not in _REL:
                raise ContractError(f"step {i}: rel_to {c['rel_to']!r} not in {_REL}")
        e = s.get("expected")
        if e is not None and e.get("kind") not in _EXPECTED_KINDS:
            raise ContractError(f"step {i}: expected.kind {e.get('kind')!r} invalid")
