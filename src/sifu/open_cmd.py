"""`sifu open` — open the library dashboard.

Without --last: the list view ('/'). With --last: the workflow you just
compiled ('/workflow/{id}'). Ensures the UI server is running first.
"""

import shutil
import socket
import subprocess
import sys
import time
import webbrowser

from sifu import library

DEFAULT_PORT = 8765


def _is_server_up(port):
    """True if something is already listening on the dashboard port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0


def _start_server(port):
    """Spawn `sifu ui --no-open` detached, then wait for the port to answer."""
    sifu = shutil.which("sifu") or sys.argv[0]
    subprocess.Popen(
        [sifu, "ui", "--no-open", "--port", str(port)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    for _ in range(50):  # up to ~5s for uvicorn to bind
        if _is_server_up(port):
            return
        time.sleep(0.1)


def open_dashboard(last=False, *, port=DEFAULT_PORT, latest_unit=library.latest_unit,
                   is_server_up=_is_server_up, start_server=_start_server,
                   open_url=webbrowser.open):
    """Open the dashboard, starting the UI server if it isn't already up.

    last=True targets the most recently compiled workflow; otherwise the list.
    Returns the opened URL, or None if there was nothing to open.
    """
    if last:
        wid = latest_unit()
        if wid is None:
            return None
        path = f"/workflow/{wid}"
    else:
        path = "/"
    if not is_server_up(port):
        start_server(port)
    url = f"http://localhost:{port}{path}"
    open_url(url)
    return url
