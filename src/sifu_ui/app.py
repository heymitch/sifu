"""Read-only library browser. No claude -p, no editors — copy-as-context
replaces in-app editing (spec §7)."""

from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from sifu import library
from sifu_ui import reader

_BASE = Path(__file__).parent
app = FastAPI(title="Sifu")
app.mount("/static", StaticFiles(directory=_BASE / "static"), name="static")
templates = Jinja2Templates(directory=str(_BASE / "templates"))


@app.get("/", response_class=HTMLResponse)
def timeline(request: Request):
    return templates.TemplateResponse(
        "timeline.html", {"request": request, "rows": reader.timeline()})


@app.get("/workflow/{workflow_id}", response_class=HTMLResponse)
def workflow(request: Request, workflow_id: str):
    u = library.read_unit(workflow_id)
    if u is None:
        return HTMLResponse("Not found", status_code=404)
    return templates.TemplateResponse(
        "doc.html", {"request": request, "u": u, "wid": workflow_id})
