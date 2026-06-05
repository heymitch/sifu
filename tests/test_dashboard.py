"""Dashboard support: pretty list timestamps + in-site editing write-back."""

from sifu import library
from sifu_ui.reader import pretty_stamp


def test_pretty_stamp_formats_iso_to_friendly():
    assert pretty_stamp("2026-06-05T14:23:01") == "Jun 5, 2:23 PM"


def test_pretty_stamp_handles_missing():
    assert pretty_stamp(None) == ""
    assert pretty_stamp("") == ""


def test_update_workflow_md_overwrites_the_unit(tmp_path, monkeypatch):
    monkeypatch.setattr(library, "LIBRARY_DIR", tmp_path / "library")
    library.write_unit("wf-x", workflow_md="# old", macro={"steps": []},
                       meta={}, screenshots=[])

    assert library.update_workflow_md("wf-x", "# edited by the user") is True
    assert library.read_unit("wf-x")["workflow_md"] == "# edited by the user"


def test_update_workflow_md_missing_unit_returns_false(tmp_path, monkeypatch):
    monkeypatch.setattr(library, "LIBRARY_DIR", tmp_path / "library")
    assert library.update_workflow_md("nope", "x") is False
