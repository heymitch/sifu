"""Library browser. No claude -p. The compiled collection is STAGED and editable
in-site; the user's own agent turns it into a skill."""

from pathlib import Path
from fastapi import FastAPI, Request, Form
from fastapi.responses import (HTMLResponse, StreamingResponse, RedirectResponse,
                               PlainTextResponse)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sifu_ui.watcher import event_stream

from sifu import library
from sifu_ui import reader

_BASE = Path(__file__).parent
app = FastAPI(title="Sifu")
app.mount("/static", StaticFiles(directory=_BASE / "static"), name="static")
templates = Jinja2Templates(directory=str(_BASE / "templates"))


@app.get("/", response_class=HTMLResponse)
def timeline(request: Request):
    return templates.TemplateResponse(
        request, "timeline.html", {"rows": reader.timeline()})


@app.get("/workflow/{workflow_id}", response_class=HTMLResponse)
def workflow(request: Request, workflow_id: str):
    u = library.read_unit(workflow_id)
    if u is None:
        return HTMLResponse("Not found", status_code=404)
    return templates.TemplateResponse(
        request, "doc.html", {"u": u, "wid": workflow_id})


@app.get("/workflow/{workflow_id}/payload", response_class=PlainTextResponse)
def workflow_payload(workflow_id: str):
    """The agent-ready briefing for one workflow (what click-to-copy copies)."""
    from sifu.context_cmd import render_unit
    p = render_unit(workflow_id)
    if p is None:
        return PlainTextResponse("Not found", status_code=404)
    return PlainTextResponse(p)


@app.post("/workflow/{workflow_id}/edit")
def edit_workflow(workflow_id: str, workflow_md: str = Form(...)):
    library.update_workflow_md(workflow_id, workflow_md)
    return RedirectResponse(f"/workflow/{workflow_id}", status_code=303)


@app.get("/api/events")
async def events():
    return StreamingResponse(event_stream(), media_type="text/event-stream")
