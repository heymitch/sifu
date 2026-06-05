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
