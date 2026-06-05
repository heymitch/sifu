"""Annotate captured screenshots for human SOPs — a numbered marker at each
click point. Deterministic (PIL), no LLM. The make-human-sop differentiator.
"""

from pathlib import Path

from PIL import Image, ImageDraw

from sifu import library

_MARKER = (255, 59, 48)          # red
_WHITE = (255, 255, 255)
_RADIUS = 16


def annotate_screenshot(src, coords, label, dst):
    """Draw a click marker + step badge onto `src`, save to `dst`. Returns dst."""
    img = Image.open(src).convert("RGBA")
    draw = ImageDraw.Draw(img)
    w, h = img.size

    if coords and coords.get("x") is not None and coords.get("y") is not None:
        x, y = int(coords["x"]), int(coords["y"])
        if 0 <= x < w and 0 <= y < h:
            draw.ellipse(
                [x - _RADIUS, y - _RADIUS, x + _RADIUS, y + _RADIUS],
                fill=_MARKER, outline=_WHITE, width=3,
            )

    # Corner step badge — labels every annotated shot, even without coords.
    draw.rectangle([0, 0, 40, 26], fill=_MARKER)
    draw.text((8, 6), str(label), fill=_WHITE)

    img.convert("RGB").save(dst)
    return Path(dst)


def annotate_workflow(wid):
    """Annotate every screenshot in a library unit; write to its `annotated/` dir.

    Returns the list of annotated image paths.
    """
    u = library.read_unit(wid)
    if u is None:
        return []
    d = library.unit_dir(wid)
    out_dir = d / "annotated"
    out_dir.mkdir(exist_ok=True)
    results = []
    for step in u.get("macro", {}).get("steps", []):
        shot = step.get("screenshot")
        if not shot:
            continue
        src = d / shot
        if not src.exists():
            continue
        dst = out_dir / Path(shot).name
        annotate_screenshot(src, step.get("coords"), step["index"] + 1, dst)
        results.append(dst)
    return results
