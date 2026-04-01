"""Workflow spec format — dataclasses for Step and WorkflowSpec, plus YAML I/O."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml

from sifu.config import load_config

METHOD_TIERS = [
    "eliminate",
    "wait_for",
    "poll",
    "api",
    "cli",
    "browser",
    "macro",
    "manual",
]


# ---------------------------------------------------------------------------
# Custom YAML dumper — forces block style for all collections
# ---------------------------------------------------------------------------

class _BlockDumper(yaml.Dumper):
    """YAML dumper that always uses block style (no inline dicts/lists)."""

    def represent_dict(self, data):
        return self.represent_mapping("tag:yaml.org,2002:map", data.items(), flow_style=False)

    def represent_list(self, data):
        return self.represent_sequence("tag:yaml.org,2002:seq", data, flow_style=False)


_BlockDumper.add_representer(dict, _BlockDumper.represent_dict)
_BlockDumper.add_representer(list, _BlockDumper.represent_list)


# ---------------------------------------------------------------------------
# Step
# ---------------------------------------------------------------------------

@dataclass
class Step:
    id: int
    description: str
    original: str
    method: str  # one of METHOD_TIERS
    confidence: float
    tool: Optional[str] = None
    capability: Optional[str] = None
    action: Optional[str] = None
    command: Optional[str] = None
    params: Optional[dict] = None
    condition: Optional[dict] = None
    reason: Optional[str] = None
    output: Optional[str] = None
    note: Optional[str] = None
    alternatives: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dict, omitting None fields for clean YAML."""
        d: dict = {
            "id": self.id,
            "description": self.description,
            "original": self.original,
            "method": self.method,
            "confidence": self.confidence,
        }
        for attr in (
            "tool",
            "capability",
            "action",
            "command",
            "params",
            "condition",
            "reason",
            "output",
            "note",
        ):
            val = getattr(self, attr)
            if val is not None:
                d[attr] = val
        if self.alternatives:
            d["alternatives"] = self.alternatives
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Step":
        """Create a Step from a dict (e.g. loaded from YAML)."""
        return cls(
            id=d["id"],
            description=d["description"],
            original=d["original"],
            method=d["method"],
            confidence=d["confidence"],
            tool=d.get("tool"),
            capability=d.get("capability"),
            action=d.get("action"),
            command=d.get("command"),
            params=d.get("params"),
            condition=d.get("condition"),
            reason=d.get("reason"),
            output=d.get("output"),
            note=d.get("note"),
            alternatives=d.get("alternatives", []),
        )


# ---------------------------------------------------------------------------
# WorkflowSpec
# ---------------------------------------------------------------------------

@dataclass
class WorkflowSpec:
    id: str
    source_workflow: str
    steps: list[Step]
    source_sop: Optional[str] = None
    classified_at: str = field(default_factory=lambda: datetime.now().isoformat())
    classifier_version: str = "0.1.0"
    capabilities_snapshot: list[str] = field(default_factory=list)
    human_time: Optional[str] = None
    human_steps: Optional[int] = None
    human_apps: Optional[int] = None

    def comparison(self) -> dict:
        """Return comparison stats between human effort and compiled spec."""
        method_counts: dict[str, int] = {}
        compiled = 0
        for step in self.steps:
            if step.method != "eliminate":
                compiled += 1
            method_counts[step.method] = method_counts.get(step.method, 0) + 1
        return {
            "human_time": self.human_time,
            "human_steps": self.human_steps,
            "human_apps": self.human_apps,
            "compiled_steps": compiled,
            "compiled_methods": method_counts,
        }


# ---------------------------------------------------------------------------
# YAML I/O
# ---------------------------------------------------------------------------

def save_spec(spec: WorkflowSpec, output_dir: Optional[Path] = None) -> Path:
    """Save a WorkflowSpec to YAML.

    Uses block style throughout (no inline dicts). Output dir defaults to
    config ``workflows_dir``. Filename: ``{spec.id}.workflow.yaml``.
    """
    if output_dir is None:
        cfg = load_config()
        output_dir = Path(cfg["workflows_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)

    doc = {
        "meta": {
            "id": spec.id,
            "source_workflow": spec.source_workflow,
            "source_sop": spec.source_sop,
            "classified_at": spec.classified_at,
            "classifier_version": spec.classifier_version,
            "capabilities_snapshot": spec.capabilities_snapshot,
            "comparison": spec.comparison(),
        },
        "steps": [step.to_dict() for step in spec.steps],
    }

    path = output_dir / f"{spec.id}.workflow.yaml"
    with open(path, "w") as f:
        yaml.dump(doc, f, Dumper=_BlockDumper, default_flow_style=False, allow_unicode=True)

    return path


def load_spec(path: Path) -> WorkflowSpec:
    """Load a WorkflowSpec from a YAML file produced by ``save_spec``."""
    with open(path) as f:
        doc = yaml.safe_load(f)

    meta = doc["meta"]
    steps = [Step.from_dict(s) for s in doc.get("steps", [])]

    return WorkflowSpec(
        id=meta["id"],
        source_workflow=meta["source_workflow"],
        steps=steps,
        source_sop=meta.get("source_sop"),
        classified_at=meta["classified_at"],
        classifier_version=meta.get("classifier_version", "0.1.0"),
        capabilities_snapshot=meta.get("capabilities_snapshot", []),
        human_time=meta.get("comparison", {}).get("human_time"),
        human_steps=meta.get("comparison", {}).get("human_steps"),
        human_apps=meta.get("comparison", {}).get("human_apps"),
    )
