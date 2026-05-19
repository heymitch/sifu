from sifu.compiler.macro import build_macro

def _rows():
    return [
        {"type": "click", "app": "Google Chrome", "position_x": 840, "position_y": 312,
         "display_id": 1, "display_bounds": "[0,0,1920,1080]",
         "window_rect": "[120,80,1280,800]", "backing_scale": 2.0,
         "url": "https://app.stripe.com/cart", "screenshot_path": "/s/4.jpg",
         "text_content": None, "shortcut": None, "window": "Cart"},
        {"type": "text_input", "app": "Google Chrome", "position_x": None, "position_y": None,
         "display_id": None, "display_bounds": None, "window_rect": None, "backing_scale": None,
         "url": "https://app.stripe.com/checkout", "screenshot_path": None,
         "text_content": "gift", "shortcut": None, "window": "Checkout"},
    ]

def test_macro_shape_and_contract():
    m = build_macro("wf-x", _rows())
    assert m["schema_version"] == 1
    assert m["workflow_id"] == "wf-x"
    s0 = m["steps"][0]
    assert s0["action"] == "click"
    assert s0["coords"] == {"x": 840, "y": 312, "rel_to": "window"}
    assert s0["frame"]["window_rect"] == [120, 80, 1280, 800]
    assert s0["frame"]["backing_scale"] == 2.0
    assert s0["url"] == "https://app.stripe.com/cart"
    assert s0["screenshot"] == "screenshots/000.jpg"
    assert s0["expected"] == {"kind": "url", "value": "https://app.stripe.com/checkout"}

def test_macro_degrades_when_frame_null():
    m = build_macro("wf-y", [{"type": "click", "app": "Notes", "position_x": 10,
        "position_y": 20, "display_id": None, "display_bounds": None,
        "window_rect": None, "backing_scale": None, "url": None,
        "screenshot_path": None, "text_content": None, "shortcut": None, "window": "Notes"}])
    s = m["steps"][0]
    assert s["coords"] == {"x": 10, "y": 20, "rel_to": "screen"}
    assert s["frame"] is None
    assert s["expected"] is None
