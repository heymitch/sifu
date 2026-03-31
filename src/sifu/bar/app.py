#!/usr/bin/env python3
"""SifuBar — Native macOS menu bar widget for Sifu.

Uses PyObjC (already installed as a Sifu dependency) instead of SwiftBar.
Works on macOS Tahoe and older versions without Xcode.

Usage:
    python3 -m extras.SifuBar.sifubar     # or just:
    sifubar                                # if installed via entry point
"""

import json
import objc
import os
import subprocess
import threading
from pathlib import Path

from AppKit import (
    NSApplication,
    NSMenu,
    NSMenuItem,
    NSStatusBar,
    NSStatusItem,
    NSTimer,
    NSWorkspace,
    NSVariableStatusItemLength,
    NSObject,
    NSApp,
    NSApplicationActivationPolicyAccessory,
)
from Foundation import NSRunLoop, NSDefaultRunLoopMode, NSDate
from PyObjCTools import AppHelper

SIFU_DIR = Path.home() / ".sifu"
STATE_FILE = SIFU_DIR / "daemon.state"
PID_FILE = SIFU_DIR / "daemon.pid"


class SifuBarDelegate(NSObject):
    statusItem = None
    timer = None

    def applicationDidFinishLaunching_(self, notification):
        # Hide dock icon
        NSApp.setActivationPolicy_(NSApplicationActivationPolicyAccessory)

        self.statusItem = NSStatusBar.systemStatusBar().statusItemWithLength_(
            NSVariableStatusItemLength
        )
        self.updateMenu()

        # Poll every 5 seconds
        self.timer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            5.0, self, "tick:", None, True
        )
        NSRunLoop.currentRunLoop().addTimer_forMode_(self.timer, NSDefaultRunLoopMode)

    def tick_(self, timer):
        self.updateMenu()

    # ── State ───────────────────────────────────────────

    @objc.python_method
    def readState(self):
        if STATE_FILE.exists():
            try:
                with open(STATE_FILE) as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {}

    @objc.python_method
    def isRunning(self):
        if PID_FILE.exists():
            try:
                pid = int(PID_FILE.read_text().strip())
                os.kill(pid, 0)
                return True
            except (OSError, ValueError):
                pass
        return False

    # ── Menu builder ────────────────────────────────────

    def updateMenu(self):
        state = self.readState()
        running = self.isRunning()
        status = state.get("status", "stopped")

        # Title
        if running:
            if status == "paused":
                self.statusItem.setTitle_("\u23F8 Sifu")  # ⏸
            else:
                self.statusItem.setTitle_("\U0001F534 Sifu")  # 🔴
        else:
            self.statusItem.setTitle_("\u26AA Sifu")  # ⚪

        menu = NSMenu.alloc().init()

        if running:
            events = state.get("events", 0)
            session = state.get("session_id", "")
            start_time = state.get("start_time", "")

            if status == "paused":
                header = menu.addItemWithTitle_action_keyEquivalent_(
                    f"Paused \u2014 {events} events", None, ""
                )
            else:
                header = menu.addItemWithTitle_action_keyEquivalent_(
                    f"Recording \u2014 {events} events", None, ""
                )
            header.setEnabled_(False)

            if session:
                s = menu.addItemWithTitle_action_keyEquivalent_(session, None, "")
                s.setEnabled_(False)
            if start_time:
                t = menu.addItemWithTitle_action_keyEquivalent_(
                    f"Since {start_time}", None, ""
                )
                t.setEnabled_(False)

            menu.addItem_(NSMenuItem.separatorItem())

            stop = menu.addItemWithTitle_action_keyEquivalent_(
                "\u23F9 Stop (+ analyze)", "stopSifu:", ""
            )
            stop.setTarget_(self)

            if status == "paused":
                resume = menu.addItemWithTitle_action_keyEquivalent_(
                    "\u25B6 Resume", "resumeSifu:", ""
                )
                resume.setTarget_(self)
            else:
                pause = menu.addItemWithTitle_action_keyEquivalent_(
                    "\u23F8 Pause", "pauseSifu:", ""
                )
                pause.setTarget_(self)

            sensitive = menu.addItemWithTitle_action_keyEquivalent_(
                "\U0001F512 Sensitive (purge 5m)", "sensitiveSifu:", ""
            )
            sensitive.setTarget_(self)
        else:
            header = menu.addItemWithTitle_action_keyEquivalent_(
                "Not recording", None, ""
            )
            header.setEnabled_(False)
            menu.addItem_(NSMenuItem.separatorItem())

            start = menu.addItemWithTitle_action_keyEquivalent_(
                "\u25B6 Start Recording", "startSifu:", ""
            )
            start.setTarget_(self)

        menu.addItem_(NSMenuItem.separatorItem())

        # Quick actions
        for title, sel in [
            ("\U0001F4CB Compile SOPs", "compileSifu:"),
            ("\U0001F3AF Coach Report", "coachSifu:"),
            ("\U0001F4CA Show Patterns", "patternsSifu:"),
            ("\U0001F4DD Show Log", "logSifu:"),
        ]:
            item = menu.addItemWithTitle_action_keyEquivalent_(title, sel, "")
            item.setTarget_(self)

        menu.addItem_(NSMenuItem.separatorItem())

        config = menu.addItemWithTitle_action_keyEquivalent_(
            "\u2699\uFE0F Config", "configSifu:", ""
        )
        config.setTarget_(self)

        openData = menu.addItemWithTitle_action_keyEquivalent_(
            "\U0001F4C2 Open Data", "openData:", ""
        )
        openData.setTarget_(self)

        menu.addItem_(NSMenuItem.separatorItem())

        quit_ = menu.addItemWithTitle_action_keyEquivalent_(
            "Quit SifuBar", "quitApp:", "q"
        )
        quit_.setTarget_(self)

        self.statusItem.setMenu_(menu)

    # ── Actions ─────────────────────────────────────────

    def startSifu_(self, sender):
        self._runInTerminal("start")

    def stopSifu_(self, sender):
        self._runInTerminal("stop")

    def pauseSifu_(self, sender):
        self._runSilent("pause")

    def resumeSifu_(self, sender):
        self._runSilent("resume")

    def sensitiveSifu_(self, sender):
        self._runSilent("sensitive")

    def compileSifu_(self, sender):
        self._runInTerminal("compile")

    def coachSifu_(self, sender):
        self._runInTerminal("coach --today")

    def patternsSifu_(self, sender):
        self._runInTerminal("patterns --today")

    def logSifu_(self, sender):
        self._runInTerminal("log --last 1h")

    def configSifu_(self, sender):
        self._runInTerminal("config")

    def openData_(self, sender):
        NSWorkspace.sharedWorkspace().openURL_(
            __import__("Foundation").NSURL.fileURLWithPath_(str(SIFU_DIR))
        )

    def quitApp_(self, sender):
        NSApp.terminate_(None)

    # ── Helpers ─────────────────────────────────────────

    @objc.python_method
    def _runSilent(self, subcommand):
        def run():
            subprocess.run(
                ["sifu"] + subcommand.split(),
                capture_output=True,
            )
            self.performSelectorOnMainThread_withObject_waitUntilDone_(
                "updateMenu", None, False
            )
        threading.Thread(target=run, daemon=True).start()

    @objc.python_method
    def _runInTerminal(self, subcommand):
        script = f'tell application "Terminal" to do script "sifu {subcommand}"'
        subprocess.Popen(["osascript", "-e", script])


def main():
    app = NSApplication.sharedApplication()
    delegate = SifuBarDelegate.alloc().init()
    app.setDelegate_(delegate)
    AppHelper.runEventLoop()


if __name__ == "__main__":
    main()
