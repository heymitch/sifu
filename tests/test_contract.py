import pytest
from sifu.compiler.contract import validate_macro, ContractError

VALID = {"schema_version": 1, "workflow_id": "wf-x", "steps": [
    {"index": 0, "action": "click", "app": "Chrome", "frame": None,
     "coords": {"x": 1, "y": 2, "rel_to": "screen"}, "url": None,
     "screenshot": None, "text": None, "key": None, "expected": None}]}

def test_valid_macro_passes():
    validate_macro(VALID)  # must not raise

def test_bad_schema_version():
    with pytest.raises(ContractError, match="schema_version"):
        validate_macro({**VALID, "schema_version": 2})

def test_bad_action():
    bad = {"schema_version":1,"workflow_id":"w","steps":[{**VALID["steps"][0],"action":"teleport"}]}
    with pytest.raises(ContractError, match="action"):
        validate_macro(bad)

def test_bad_rel_to():
    bad = {"schema_version":1,"workflow_id":"w","steps":[
        {**VALID["steps"][0],"coords":{"x":1,"y":2,"rel_to":"galaxy"}}]}
    with pytest.raises(ContractError, match="rel_to"):
        validate_macro(bad)

def test_missing_workflow_id():
    with pytest.raises(ContractError, match="workflow_id"):
        validate_macro({**VALID, "workflow_id": ""})

def test_steps_not_a_list():
    with pytest.raises(ContractError, match="steps must be a list"):
        validate_macro({**VALID, "steps": "not-a-list"})

def test_bad_expected_kind():
    bad_step = {**VALID["steps"][0], "expected": {"kind": "sparkle", "value": "x"}}
    with pytest.raises(ContractError, match="expected"):
        validate_macro({"schema_version": 1, "workflow_id": "w", "steps": [bad_step]})

def test_hostile_input_raises_contract_error_not_crash():
    for bad in [None, 42, "x", {"schema_version":1,"workflow_id":"w","steps":[42]},
                {"schema_version":1,"workflow_id":"w","steps":[{**VALID["steps"][0],"coords":7}]},
                {"schema_version":1,"workflow_id":"w","steps":[{**VALID["steps"][0],"expected":"nope"}]}]:
        with pytest.raises(ContractError):
            validate_macro(bad)
