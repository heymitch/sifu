"""Screenshot annotation for human SOPs — draws a marker at the click point."""

from PIL import Image

from sifu.sop_annotate import annotate_screenshot


def test_annotate_draws_a_marker_at_the_click(tmp_path):
    src = tmp_path / "shot.png"
    Image.new("RGB", (100, 100), "white").save(src)
    dst = tmp_path / "out.png"

    annotate_screenshot(src, coords={"x": 50, "y": 50}, label="1", dst=dst)

    assert dst.exists()
    out = Image.open(dst).convert("RGB")
    assert out.getpixel((50, 50)) != (255, 255, 255)  # marker drawn at the click


def test_annotate_without_coords_still_produces_an_image(tmp_path):
    src = tmp_path / "shot.png"
    Image.new("RGB", (100, 100), "white").save(src)
    dst = tmp_path / "out.png"

    annotate_screenshot(src, coords=None, label="2", dst=dst)

    assert dst.exists()


def test_annotate_workflow_writes_an_annotated_dir(tmp_path, monkeypatch):
    from sifu import library
    from sifu.compiler.macro import build_macro
    from sifu.compiler.meta import build_meta
    from sifu.sop_annotate import annotate_workflow

    monkeypatch.setattr(library, "LIBRARY_DIR", tmp_path / "library")
    shot = tmp_path / "000.jpg"
    Image.new("RGB", (80, 80), "white").save(shot)
    rows = [{"app": "Chrome", "type": "click", "position_x": 40, "position_y": 40,
             "screenshot_path": str(shot), "timestamp": "2026-06-05T10:00:00"}]
    library.write_unit("wf-a", workflow_md="# x",
                       macro=build_macro("wf-a", rows),
                       meta=build_meta("wf-a", rows), screenshots=[shot])

    out = annotate_workflow("wf-a")

    assert len(out) == 1
    assert (library.unit_dir("wf-a") / "annotated" / "000.jpg").exists()


def test_annotate_marks_the_recorded_point_for_window_relative_coords(tmp_path, monkeypatch):
    from sifu import library
    from sifu.compiler.macro import build_macro
    from sifu.compiler.meta import build_meta
    from sifu.sop_annotate import annotate_workflow

    monkeypatch.setattr(library, "LIBRARY_DIR", tmp_path / "library")
    shot = tmp_path / "000.jpg"
    Image.new("RGB", (200, 200), "white").save(shot)
    rows = [{"app": "Chrome", "type": "click", "position_x": 150, "position_y": 150,
             "window_rect": "[100, 100, 100, 100]", "screenshot_path": str(shot),
             "timestamp": "2026-06-05T10:00:00"}]
    library.write_unit("wf-w", workflow_md="# x", macro=build_macro("wf-w", rows),
                       meta=build_meta("wf-w", rows), screenshots=[shot])

    (out,) = annotate_workflow("wf-w")

    img = Image.open(out).convert("RGB")
    assert img.getpixel((150, 150))[1] < 120, "marker at the recorded click"
    assert img.getpixel((50, 50))[1] > 240, "nothing at the window-relative point"


def test_annotate_treats_macros_from_before_coords_version_2_as_global(tmp_path, monkeypatch):
    from sifu import library
    from sifu.sop_annotate import annotate_workflow

    monkeypatch.setattr(library, "LIBRARY_DIR", tmp_path / "library")
    shot = tmp_path / "000.jpg"
    Image.new("RGB", (300, 300), "white").save(shot)
    old_macro = {"schema_version": 1, "workflow_id": "wf-old", "steps": [{
        "index": 0, "action": "click", "app": "Chrome", "screenshot": "screenshots/000.jpg",
        "frame": {"display_id": 1, "display_bounds": None, "window_rect": [100, 100, 100, 100],
                  "backing_scale": 2.0},
        "coords": {"x": 150, "y": 150, "rel_to": "window"},
    }]}
    library.write_unit("wf-old", workflow_md="# x", macro=old_macro, meta={"id": "wf-old"},
                       screenshots=[shot])

    (out,) = annotate_workflow("wf-old")

    img = Image.open(out).convert("RGB")
    assert img.getpixel((150, 150))[1] < 120, "old macros stored the global point"
    assert img.getpixel((250, 250))[1] > 240
