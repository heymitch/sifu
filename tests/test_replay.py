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

def test_dry_run_no_expected_anywhere():
    macro = {"schema_version":1,"workflow_id":"wf-n","steps":[
        {"index":0,"action":"click","app":"X","frame":None,"coords":None,
         "url":None,"screenshot":None,"text":None,"key":None,"expected":None},
        {"index":1,"action":"click","app":"X","frame":None,"coords":None,
         "url":None,"screenshot":None,"text":None,"key":None,"expected":None},
    ]}
    r = dry_run(macro, observed=[None, None])
    assert r["ok"] is True
    assert r["failed_step"] is None

def test_dry_run_short_observed_does_not_crash():
    # observed shorter than steps: missing entries treat as None and trigger expected mismatch
    r = dry_run(MACRO, observed=[])  # step 0 has expected url but observed is empty
    assert r["ok"] is False
    assert r["failed_step"] == 0
