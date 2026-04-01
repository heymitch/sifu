"""Tests for sifu.classifier.spec."""

import yaml
import pytest

from sifu.classifier.spec import (
    METHOD_TIERS,
    Step,
    WorkflowSpec,
    save_spec,
    load_spec,
)


# ---------------------------------------------------------------------------
# METHOD_TIERS
# ---------------------------------------------------------------------------

def test_method_tiers_count():
    assert len(METHOD_TIERS) == 8


def test_method_tiers_order():
    expected = [
        "eliminate",
        "wait_for",
        "poll",
        "api",
        "cli",
        "browser",
        "macro",
        "manual",
    ]
    assert METHOD_TIERS == expected


# ---------------------------------------------------------------------------
# Step
# ---------------------------------------------------------------------------

def _make_step(**kwargs) -> Step:
    defaults = dict(
        id=1,
        description="Download the report",
        original="Go to the reports page and download the CSV",
        method="browser",
        confidence=0.9,
    )
    defaults.update(kwargs)
    return Step(**defaults)


def test_step_defaults():
    step = _make_step()
    assert step.tool is None
    assert step.capability is None
    assert step.alternatives == []


def test_step_to_dict_omits_none_fields():
    step = _make_step()
    d = step.to_dict()
    # Required fields present
    assert d["id"] == 1
    assert d["method"] == "browser"
    assert d["confidence"] == 0.9
    # None fields omitted
    for optional in ("tool", "capability", "action", "command", "params",
                     "condition", "reason", "output", "note"):
        assert optional not in d


def test_step_to_dict_includes_set_optionals():
    step = _make_step(tool="playwright", reason="Needs login session", params={"url": "https://example.com"})
    d = step.to_dict()
    assert d["tool"] == "playwright"
    assert d["reason"] == "Needs login session"
    assert d["params"] == {"url": "https://example.com"}


def test_step_to_dict_omits_empty_alternatives():
    step = _make_step()
    d = step.to_dict()
    assert "alternatives" not in d


def test_step_to_dict_includes_nonempty_alternatives():
    alts = [{"method": "api", "confidence": 0.6}]
    step = _make_step(alternatives=alts)
    d = step.to_dict()
    assert d["alternatives"] == alts


def test_step_from_dict_roundtrip():
    original = _make_step(
        tool="curl",
        capability="http-client",
        action="GET",
        command="curl https://api.example.com/data",
        params={"timeout": 30},
        reason="Simpler than browser",
        output="JSON response",
        note="Requires API key in env",
        alternatives=[{"method": "browser", "confidence": 0.5}],
    )
    d = original.to_dict()
    restored = Step.from_dict(d)

    assert restored.id == original.id
    assert restored.description == original.description
    assert restored.original == original.original
    assert restored.method == original.method
    assert restored.confidence == original.confidence
    assert restored.tool == original.tool
    assert restored.capability == original.capability
    assert restored.action == original.action
    assert restored.command == original.command
    assert restored.params == original.params
    assert restored.reason == original.reason
    assert restored.output == original.output
    assert restored.note == original.note
    assert restored.alternatives == original.alternatives


def test_step_from_dict_minimal():
    d = {
        "id": 5,
        "description": "Wait for email",
        "original": "Wait for confirmation email",
        "method": "wait_for",
        "confidence": 0.75,
    }
    step = Step.from_dict(d)
    assert step.id == 5
    assert step.tool is None
    assert step.alternatives == []


# ---------------------------------------------------------------------------
# WorkflowSpec.comparison()
# ---------------------------------------------------------------------------

def _make_spec(steps=None, **kwargs) -> WorkflowSpec:
    if steps is None:
        steps = [
            _make_step(id=1, method="eliminate"),
            _make_step(id=2, method="api"),
            _make_step(id=3, method="api"),
            _make_step(id=4, method="browser"),
        ]
    defaults = dict(
        id="wf-001",
        source_workflow="upload-report.sop.md",
        steps=steps,
        human_time="45m",
        human_steps=10,
        human_apps=3,
    )
    defaults.update(kwargs)
    return WorkflowSpec(**defaults)


def test_comparison_compiled_steps_excludes_eliminates():
    spec = _make_spec()
    cmp = spec.comparison()
    # 1 eliminate, 3 non-eliminate
    assert cmp["compiled_steps"] == 3


def test_comparison_compiled_methods_counts():
    spec = _make_spec()
    cmp = spec.comparison()
    methods = cmp["compiled_methods"]
    assert methods["eliminate"] == 1
    assert methods["api"] == 2
    assert methods["browser"] == 1


def test_comparison_human_fields_passthrough():
    spec = _make_spec()
    cmp = spec.comparison()
    assert cmp["human_time"] == "45m"
    assert cmp["human_steps"] == 10
    assert cmp["human_apps"] == 3


def test_comparison_all_eliminate():
    steps = [_make_step(id=i, method="eliminate") for i in range(3)]
    spec = _make_spec(steps=steps)
    cmp = spec.comparison()
    assert cmp["compiled_steps"] == 0
    assert cmp["compiled_methods"] == {"eliminate": 3}


def test_comparison_no_eliminate():
    steps = [
        _make_step(id=1, method="api"),
        _make_step(id=2, method="cli"),
        _make_step(id=3, method="cli"),
    ]
    spec = _make_spec(steps=steps)
    cmp = spec.comparison()
    assert cmp["compiled_steps"] == 3
    assert "eliminate" not in cmp["compiled_methods"]
    assert cmp["compiled_methods"]["cli"] == 2


# ---------------------------------------------------------------------------
# save_spec / load_spec roundtrip
# ---------------------------------------------------------------------------

def _full_spec() -> WorkflowSpec:
    steps = [
        Step(
            id=1,
            description="Eliminate duplicate check",
            original="Check if report already exists",
            method="eliminate",
            confidence=0.95,
        ),
        Step(
            id=2,
            description="Fetch report via API",
            original="Download monthly CSV from reports page",
            method="api",
            confidence=0.85,
            tool="requests",
            capability="http-client",
            action="GET",
            command="GET /reports/monthly.csv",
            params={"format": "csv"},
            reason="API endpoint exists",
            output="monthly.csv",
        ),
        Step(
            id=3,
            description="Upload to Sheets",
            original="Paste data into Google Sheets",
            method="browser",
            confidence=0.6,
            tool="playwright",
            alternatives=[{"method": "api", "confidence": 0.8, "note": "Sheets API preferred"}],
        ),
    ]
    return WorkflowSpec(
        id="wf-test-roundtrip",
        source_workflow="monthly-report.sop.md",
        source_sop="monthly-report.sop.md",
        steps=steps,
        classified_at="2026-04-01T12:00:00",
        classifier_version="0.1.0",
        capabilities_snapshot=["http-client", "playwright"],
        human_time="30m",
        human_steps=8,
        human_apps=2,
    )


def test_save_spec_creates_file(tmp_path):
    spec = _full_spec()
    path = save_spec(spec, output_dir=tmp_path)
    assert path.exists()
    assert path.name == "wf-test-roundtrip.workflow.yaml"


def test_load_spec_roundtrip(tmp_path):
    spec = _full_spec()
    path = save_spec(spec, output_dir=tmp_path)
    loaded = load_spec(path)

    assert loaded.id == spec.id
    assert loaded.source_workflow == spec.source_workflow
    assert loaded.source_sop == spec.source_sop
    assert loaded.classified_at == spec.classified_at
    assert loaded.classifier_version == spec.classifier_version
    assert loaded.capabilities_snapshot == spec.capabilities_snapshot
    assert loaded.human_time == spec.human_time
    assert loaded.human_steps == spec.human_steps
    assert loaded.human_apps == spec.human_apps
    assert len(loaded.steps) == len(spec.steps)


def test_load_spec_steps_roundtrip(tmp_path):
    spec = _full_spec()
    path = save_spec(spec, output_dir=tmp_path)
    loaded = load_spec(path)

    for orig, restored in zip(spec.steps, loaded.steps):
        assert restored.id == orig.id
        assert restored.method == orig.method
        assert restored.confidence == orig.confidence
        assert restored.tool == orig.tool
        assert restored.capability == orig.capability
        assert restored.params == orig.params
        assert restored.alternatives == orig.alternatives


def test_load_spec_none_fields_preserved(tmp_path):
    """Optional Step fields that were None stay None after roundtrip."""
    spec = _full_spec()
    path = save_spec(spec, output_dir=tmp_path)
    loaded = load_spec(path)

    step1 = loaded.steps[0]  # eliminate step with minimal fields
    assert step1.tool is None
    assert step1.capability is None
    assert step1.params is None
    assert step1.alternatives == []


# ---------------------------------------------------------------------------
# YAML output is human-readable (block style, no inline dicts)
# ---------------------------------------------------------------------------

def test_yaml_block_style_steps(tmp_path):
    """No inline dict literals (flow style) in the steps section of the output."""
    spec = _full_spec()
    path = save_spec(spec, output_dir=tmp_path)
    text = path.read_text()

    # Flow-style dicts look like {key: val} — should not appear anywhere
    assert "{" not in text, f"Found inline dict in YAML output:\n{text}"
    assert "}" not in text, f"Found inline dict in YAML output:\n{text}"


def test_yaml_is_valid_and_has_meta_and_steps(tmp_path):
    spec = _full_spec()
    path = save_spec(spec, output_dir=tmp_path)
    text = path.read_text()

    doc = yaml.safe_load(text)
    assert "meta" in doc
    assert "steps" in doc
    assert isinstance(doc["steps"], list)
    assert len(doc["steps"]) == 3


def test_yaml_steps_are_block_mappings(tmp_path):
    """Each step in the YAML file starts with '- id:' (block sequence item)."""
    spec = _full_spec()
    path = save_spec(spec, output_dir=tmp_path)
    text = path.read_text()

    assert "- id:" in text
