"""The copy-to-agent payload must teach the decomposition (the moat)."""

from sifu.context_cmd import _PAYLOAD


def test_payload_teaches_automatable_vs_knowledge_decomposition():
    low = _PAYLOAD.lower()
    assert "automatable" in low
    assert "knowledge" in low


def test_payload_points_automatable_steps_at_printing_press():
    assert "Printing Press" in _PAYLOAD


def test_payload_composes_by_stability_and_offers_human_sop():
    low = _PAYLOAD.lower()
    assert "stable" in low or "stability" in low
    assert "human sop" in low
