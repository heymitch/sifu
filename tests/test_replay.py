from sifu.replay import dry_run

MACRO = {"schema_version":1,"workflow_id":"wf-x","steps":[
  {"index":0,"action":"click","app":"Chrome","frame":None,
   "coords":{"x":1,"y":2,"rel_to":"screen"},"url":"https://a.test",
   "screenshot":None,"text":None,"key":None,
   "expected":{"kind":"url","value":"https://b.test"}},
  {"index":1,"action":"click","app":"Chrome","frame":None,
   "coords":{"x":3,"y":4,"rel_to":"screen"},"url":"https://b.test",
   "screenshot":None,"text":None,"key":None,"expected":None}]}

def test_dry_run_all_ok():
    report = dry_run(MACRO, observed=["https://b.test", None])
    assert report["ok"] is True
    assert report["failed_step"] is None

def test_dry_run_detects_expected_mismatch():
    report = dry_run(MACRO, observed=["https://WRONG.test", None])
    assert report["ok"] is False
    assert report["failed_step"] == 0
    assert report["reason"].startswith("expected url")
