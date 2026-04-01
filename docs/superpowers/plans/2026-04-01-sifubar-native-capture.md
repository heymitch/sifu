# SifuBar Native Capture Engine — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move all macOS capture (CGEventTap, screenshots, app tracking) from the Python daemon into the native Swift SifuBar.app so permissions are bound to a stable app bundle identity and persist across reboots.

**Architecture:** SifuBar.app (Swift) becomes the capture engine — it creates CGEventTaps, captures screenshots, tracks app/window switches, and writes directly to SQLite. The Python CLI becomes a thin client that sends commands to SifuBar via a command file. Python stays as the analysis engine (Layers 1-4) reading from the same SQLite database.

**Tech Stack:** Swift 6.0, Swift Package Manager, macOS 13+, SQLite3 C API, CGEventTap, Accessibility API, NSWorkspace, SMAppService

**Spec:** `docs/superpowers/specs/2026-04-01-sifubar-native-capture-design.md`

---

## File Layout

### New Swift Files (under `extras/SifuBar/SifuBar/`)

| File | Responsibility |
|------|---------------|
| `PermissionManager.swift` | Check + request Accessibility & Screen Recording; poll until granted |
| `Config.swift` | Read `~/.sifu/config.json`, provide typed defaults |
| `CaptureEngine/EventTapManager.swift` | CGEventTap for mouse clicks + keyboard events |
| `CaptureEngine/TextAggregator.swift` | Buffer keystrokes, flush on pause/enter/app-switch |
| `CaptureEngine/AppTracker.swift` | NSWorkspace notifications + AX window title polling |
| `CaptureEngine/ScreenshotCapture.swift` | CGWindowListCreateImage, JPEG encoding, disk budget |
| `Storage/EventStore.swift` | SQLite writer (events + sessions tables, matching Python schema) |
| `Storage/SessionManager.swift` | Create/end sessions, update daemon.state file |
| `Bridge/CLIBridge.swift` | Watch `~/.sifu/command.json` for CLI commands |
| `Bridge/LoginItemManager.swift` | SMAppService Login Item registration |
| `Info.plist` | Bundle ID, usage descriptions, LSUIElement |

### Modified Files

| File | Changes |
|------|---------|
| `extras/SifuBar/Package.swift` | No external deps needed (all frameworks are system) |
| `extras/SifuBar/SifuBar/SifuBarApp.swift` | Rewrite: wire up capture engine, permissions, CLI bridge |
| `src/sifu/daemon.py` | Replace spawn logic with command-file writes to SifuBar |

### Removed Files (Task 11)

| File | Replaced By |
|------|------------|
| `src/sifu/capture/mouse.py` | `EventTapManager.swift` |
| `src/sifu/capture/keyboard.py` | `EventTapManager.swift` + `TextAggregator.swift` |
| `src/sifu/capture/apps.py` | `AppTracker.swift` |
| `src/sifu/capture/screenshots.py` | `ScreenshotCapture.swift` |
| `src/sifu/bar/app.py` | `SifuBarApp.swift` |

---

## Task 1: Info.plist and Package.swift

**Files:**
- Create: `extras/SifuBar/SifuBar/Info.plist`
- Modify: `extras/SifuBar/Package.swift`

- [ ] **Step 1: Create Info.plist**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleIdentifier</key>
    <string>com.sifu.SifuBar</string>
    <key>CFBundleName</key>
    <string>SifuBar</string>
    <key>CFBundleDisplayName</key>
    <string>SifuBar</string>
    <key>CFBundleVersion</key>
    <string>1.0</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleExecutable</key>
    <string>SifuBar</string>
    <key>LSUIElement</key>
    <true/>
    <key>LSMinimumSystemVersion</key>
    <string>13.0</string>
    <key>NSAccessibilityUsageDescription</key>
    <string>Sifu needs Accessibility access to track your workflow — clicks, keystrokes, and app switches. All data stays 100% local on your machine.</string>
    <key>NSScreenCaptureUsageDescription</key>
    <string>Sifu needs Screen Recording access to capture screenshots of your workflow. All data stays 100% local on your machine.</string>
</dict>
</plist>
```

- [ ] **Step 2: Update Package.swift to use .app bundle with Info.plist**

```swift
// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "SifuBar",
    platforms: [.macOS(.v13)],
    targets: [
        .executableTarget(
            name: "SifuBar",
            path: "SifuBar",
            resources: [
                .copy("Info.plist"),
            ],
            linkerSettings: [
                .linkedLibrary("sqlite3"),
            ]
        ),
    ]
)
```

- [ ] **Step 3: Verify build compiles**

Run: `cd extras/SifuBar && swift build 2>&1 | tail -5`
Expected: Build succeeds (existing SifuBarApp.swift still compiles)

- [ ] **Step 4: Commit**

```bash
git add extras/SifuBar/SifuBar/Info.plist extras/SifuBar/Package.swift
git commit -m "Add Info.plist with permission descriptions, link sqlite3"
```

---

## Task 2: Config.swift — Read shared config

**Files:**
- Create: `extras/SifuBar/SifuBar/Config.swift`

- [ ] **Step 1: Write Config.swift**

Reads `~/.sifu/config.json` and provides typed access with defaults matching Python's `config.py`.

```swift
import Foundation

struct SifuConfig {
    let screenshotBudgetMB: Int
    let screenshotMinIntervalS: Double
    let screenshotQuality: Int
    let idleTimeoutS: Int
    let sessionGapS: Int
    let ignoreApps: Set<String>
    let terminalApps: Set<String>
    let sensitivePurgeMinutes: Int
    let startAtLogin: Bool

    static let defaultIgnoreApps: Set<String> = [
        "1Password", "Bitwarden", "KeyChain Access",
        "loginwindow", "ScreenSaverEngine",
    ]

    static let defaultTerminalApps: Set<String> = [
        "Terminal", "iTerm2", "Ghostty", "Alacritty",
        "kitty", "Warp", "Hyper",
    ]

    static func load() -> SifuConfig {
        let configPath = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent(".sifu/config.json")

        var raw: [String: Any] = [:]
        if let data = try? Data(contentsOf: configPath),
           let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
            raw = json
        }

        return SifuConfig(
            screenshotBudgetMB: raw["screenshot_budget_mb"] as? Int ?? 1024,
            screenshotMinIntervalS: raw["screenshot_min_interval_s"] as? Double ?? 2.0,
            screenshotQuality: raw["screenshot_quality"] as? Int ?? 80,
            idleTimeoutS: raw["idle_timeout_s"] as? Int ?? 300,
            sessionGapS: raw["session_gap_s"] as? Int ?? 30,
            ignoreApps: Set((raw["ignore_apps"] as? [String]) ?? Array(defaultIgnoreApps)),
            terminalApps: Set((raw["terminal_apps"] as? [String]) ?? Array(defaultTerminalApps)),
            sensitivePurgeMinutes: raw["sensitive_purge_minutes"] as? Int ?? 5,
            startAtLogin: raw["start_at_login"] as? Bool ?? true
        )
    }
}
```

- [ ] **Step 2: Verify build**

Run: `cd extras/SifuBar && swift build 2>&1 | tail -5`
Expected: Build succeeds

- [ ] **Step 3: Commit**

```bash
git add extras/SifuBar/SifuBar/Config.swift
git commit -m "Add Config.swift to read shared ~/.sifu/config.json"
```

---

## Task 3: EventStore.swift — SQLite writer

**Files:**
- Create: `extras/SifuBar/SifuBar/Storage/EventStore.swift`

- [ ] **Step 1: Write EventStore.swift**

Thread-safe SQLite writer using the C API. Schema matches Python's `db.py` exactly.

```swift
import Foundation
import SQLite3

final class EventStore: @unchecked Sendable {
    private var db: OpaquePointer?
    private let queue = DispatchQueue(label: "com.sifu.eventstore")

    init() {
        let sifuDir = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent(".sifu")
        try? FileManager.default.createDirectory(at: sifuDir, withIntermediateDirectories: true)
        let dbPath = sifuDir.appendingPathComponent("capture.db").path

        if sqlite3_open(dbPath, &db) != SQLITE_OK {
            print("[SifuBar] ERROR: Could not open database at \(dbPath)")
            return
        }

        createTables()
    }

    deinit {
        if let db = db { sqlite3_close(db) }
    }

    // MARK: - Schema

    private func createTables() {
        let sql = """
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY,
            timestamp TEXT NOT NULL,
            type TEXT NOT NULL,
            app TEXT,
            window TEXT,
            description TEXT,
            element TEXT,
            position_x INTEGER,
            position_y INTEGER,
            text_content TEXT,
            shortcut TEXT,
            screenshot_path TEXT,
            session_id TEXT,
            workflow_id TEXT
        );
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            start_time TEXT,
            end_time TEXT,
            app_summary TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);
        CREATE INDEX IF NOT EXISTS idx_events_session ON events(session_id);
        CREATE INDEX IF NOT EXISTS idx_events_type ON events(type);
        CREATE INDEX IF NOT EXISTS idx_events_app ON events(app);
        """
        queue.sync {
            sqlite3_exec(db, sql, nil, nil, nil)
        }
    }

    // MARK: - Event insertion

    func insertEvent(
        timestamp: String,
        type: String,
        app: String?,
        window: String?,
        description: String?,
        element: String?,
        positionX: Int?,
        positionY: Int?,
        textContent: String?,
        shortcut: String?,
        screenshotPath: String?,
        sessionId: String?,
        workflowId: String? = nil
    ) -> Int64 {
        var rowId: Int64 = 0
        queue.sync {
            let sql = """
            INSERT INTO events
                (timestamp, type, app, window, description, element,
                 position_x, position_y, text_content, shortcut,
                 screenshot_path, session_id, workflow_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            var stmt: OpaquePointer?
            guard sqlite3_prepare_v2(db, sql, -1, &stmt, nil) == SQLITE_OK else { return }
            defer { sqlite3_finalize(stmt) }

            sqlite3_bind_text(stmt, 1, (timestamp as NSString).utf8String, -1, nil)
            sqlite3_bind_text(stmt, 2, (type as NSString).utf8String, -1, nil)
            Self.bindOptionalText(stmt, 3, app)
            Self.bindOptionalText(stmt, 4, window)
            Self.bindOptionalText(stmt, 5, description)
            Self.bindOptionalText(stmt, 6, element)
            Self.bindOptionalInt(stmt, 7, positionX)
            Self.bindOptionalInt(stmt, 8, positionY)
            Self.bindOptionalText(stmt, 9, textContent)
            Self.bindOptionalText(stmt, 10, shortcut)
            Self.bindOptionalText(stmt, 11, screenshotPath)
            Self.bindOptionalText(stmt, 12, sessionId)
            Self.bindOptionalText(stmt, 13, workflowId)

            sqlite3_step(stmt)
            rowId = sqlite3_last_insert_rowid(db)
        }
        return rowId
    }

    func updateScreenshotPath(eventId: Int64, path: String) {
        queue.sync {
            let sql = "UPDATE events SET screenshot_path = ? WHERE id = ?"
            var stmt: OpaquePointer?
            guard sqlite3_prepare_v2(db, sql, -1, &stmt, nil) == SQLITE_OK else { return }
            defer { sqlite3_finalize(stmt) }
            sqlite3_bind_text(stmt, 1, (path as NSString).utf8String, -1, nil)
            sqlite3_bind_int64(stmt, 2, eventId)
            sqlite3_step(stmt)
        }
    }

    // MARK: - Session management

    func createSession(id: String, startTime: String) {
        queue.sync {
            let sql = "INSERT INTO sessions (id, start_time) VALUES (?, ?)"
            var stmt: OpaquePointer?
            guard sqlite3_prepare_v2(db, sql, -1, &stmt, nil) == SQLITE_OK else { return }
            defer { sqlite3_finalize(stmt) }
            sqlite3_bind_text(stmt, 1, (id as NSString).utf8String, -1, nil)
            sqlite3_bind_text(stmt, 2, (startTime as NSString).utf8String, -1, nil)
            sqlite3_step(stmt)
        }
    }

    func endSession(id: String, endTime: String) {
        queue.sync {
            let sql = "UPDATE sessions SET end_time = ? WHERE id = ?"
            var stmt: OpaquePointer?
            guard sqlite3_prepare_v2(db, sql, -1, &stmt, nil) == SQLITE_OK else { return }
            defer { sqlite3_finalize(stmt) }
            sqlite3_bind_text(stmt, 1, (endTime as NSString).utf8String, -1, nil)
            sqlite3_bind_text(stmt, 2, (id as NSString).utf8String, -1, nil)
            sqlite3_step(stmt)
        }
    }

    /// Purge events from the last N minutes and return their screenshot paths.
    func purgeRecent(minutes: Int) -> [String] {
        var paths: [String] = []
        queue.sync {
            let cutoff = ISO8601DateFormatter().string(from: Date().addingTimeInterval(-Double(minutes * 60)))
            // Collect screenshot paths first
            let selectSQL = "SELECT screenshot_path FROM events WHERE timestamp >= ? AND screenshot_path IS NOT NULL"
            var stmt: OpaquePointer?
            if sqlite3_prepare_v2(db, selectSQL, -1, &stmt, nil) == SQLITE_OK {
                sqlite3_bind_text(stmt, 1, (cutoff as NSString).utf8String, -1, nil)
                while sqlite3_step(stmt) == SQLITE_ROW {
                    if let cStr = sqlite3_column_text(stmt, 0) {
                        paths.append(String(cString: cStr))
                    }
                }
                sqlite3_finalize(stmt)
            }
            // Delete the events
            let deleteSQL = "DELETE FROM events WHERE timestamp >= ?"
            if sqlite3_prepare_v2(db, deleteSQL, -1, &stmt, nil) == SQLITE_OK {
                sqlite3_bind_text(stmt, 1, (cutoff as NSString).utf8String, -1, nil)
                sqlite3_step(stmt)
                sqlite3_finalize(stmt)
            }
        }
        return paths
    }

    // MARK: - Helpers

    private static func bindOptionalText(_ stmt: OpaquePointer?, _ index: Int32, _ value: String?) {
        if let value = value {
            sqlite3_bind_text(stmt, index, (value as NSString).utf8String, -1, nil)
        } else {
            sqlite3_bind_null(stmt, index)
        }
    }

    private static func bindOptionalInt(_ stmt: OpaquePointer?, _ index: Int32, _ value: Int?) {
        if let value = value {
            sqlite3_bind_int(stmt, index, Int32(value))
        } else {
            sqlite3_bind_null(stmt, index)
        }
    }
}
```

- [ ] **Step 2: Verify build**

Run: `cd extras/SifuBar && swift build 2>&1 | tail -5`
Expected: Build succeeds

- [ ] **Step 3: Commit**

```bash
git add extras/SifuBar/SifuBar/Storage/EventStore.swift
git commit -m "Add EventStore.swift — SQLite writer matching Python schema"
```

---

## Task 4: SessionManager.swift — Session lifecycle + state file

**Files:**
- Create: `extras/SifuBar/SifuBar/Storage/SessionManager.swift`

- [ ] **Step 1: Write SessionManager.swift**

Manages session lifecycle and the `daemon.state` file that the CLI and menu UI read.

```swift
import Foundation

final class SessionManager {
    private let store: EventStore
    private let sifuDir: URL
    private let stateFile: URL
    private let pidFile: URL
    private var _sessionId: String?
    private var _startTime: String?
    private var _eventCount: Int = 0
    private let lock = NSLock()

    var sessionId: String? { _sessionId }
    var isActive: Bool { _sessionId != nil }

    init(store: EventStore) {
        self.store = store
        self.sifuDir = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent(".sifu")
        self.stateFile = sifuDir.appendingPathComponent("daemon.state")
        self.pidFile = sifuDir.appendingPathComponent("sifubar.pid")
    }

    func startSession() {
        lock.lock()
        defer { lock.unlock() }

        let uuid = UUID().uuidString.prefix(8).lowercased()
        _sessionId = "session-\(uuid)"
        _startTime = Self.isoNow()
        _eventCount = 0

        store.createSession(id: _sessionId!, startTime: _startTime!)
        writePidFile()
        writeState()
    }

    func endSession() {
        lock.lock()
        defer { lock.unlock() }

        if let sid = _sessionId {
            store.endSession(id: sid, endTime: Self.isoNow())
        }
        _sessionId = nil
        _startTime = nil
        _eventCount = 0

        removePidFile()
        writeStoppedState()
    }

    func incrementEventCount() {
        lock.lock()
        _eventCount += 1
        let count = _eventCount
        lock.unlock()
        writeState()
    }

    var eventCount: Int {
        lock.lock()
        defer { lock.unlock() }
        return _eventCount
    }

    // MARK: - State file

    private func writeState() {
        let state: [String: Any] = [
            "status": "recording",
            "session_id": _sessionId ?? "",
            "start_time": _startTime ?? "",
            "events": _eventCount,
            "pid": ProcessInfo.processInfo.processIdentifier,
        ]
        writeJSON(state, to: stateFile)
    }

    func writePausedState() {
        lock.lock()
        let state: [String: Any] = [
            "status": "paused",
            "session_id": _sessionId ?? "",
            "start_time": _startTime ?? "",
            "events": _eventCount,
            "pid": ProcessInfo.processInfo.processIdentifier,
        ]
        lock.unlock()
        writeJSON(state, to: stateFile)
    }

    func writeRecordingState() {
        writeState()
    }

    private func writeStoppedState() {
        writeJSON(["status": "stopped"], to: stateFile)
    }

    // MARK: - PID file

    private func writePidFile() {
        let pid = "\(ProcessInfo.processInfo.processIdentifier)"
        try? pid.write(to: pidFile, atomically: true, encoding: .utf8)
    }

    private func removePidFile() {
        try? FileManager.default.removeItem(at: pidFile)
    }

    // MARK: - Helpers

    private func writeJSON(_ dict: [String: Any], to url: URL) {
        try? FileManager.default.createDirectory(at: sifuDir, withIntermediateDirectories: true)
        if let data = try? JSONSerialization.data(withJSONObject: dict) {
            try? data.write(to: url)
        }
    }

    static func isoNow() -> String {
        let f = DateFormatter()
        f.dateFormat = "yyyy-MM-dd'T'HH:mm:ss"
        return f.string(from: Date())
    }
}
```

- [ ] **Step 2: Verify build**

Run: `cd extras/SifuBar && swift build 2>&1 | tail -5`
Expected: Build succeeds

- [ ] **Step 3: Commit**

```bash
git add extras/SifuBar/SifuBar/Storage/SessionManager.swift
git commit -m "Add SessionManager.swift — session lifecycle + state file"
```

---

## Task 5: PermissionManager.swift — Check and request permissions

**Files:**
- Create: `extras/SifuBar/SifuBar/PermissionManager.swift`

- [ ] **Step 1: Write PermissionManager.swift**

Checks Accessibility + Screen Recording permissions. Shows native alerts with "Open System Settings" button. Polls until both are granted.

```swift
import AppKit
import ApplicationServices

final class PermissionManager {
    private var pollTimer: Timer?

    var hasAccessibility: Bool {
        AXIsProcessTrusted()
    }

    var hasScreenRecording: Bool {
        // CGWindowListCreateImage returns nil without Screen Recording permission
        let testImage = CGWindowListCreateImage(
            CGRect(x: 0, y: 0, width: 1, height: 1),
            .optionOnScreenOnly,
            kCGNullWindowID,
            []
        )
        return testImage != nil
    }

    var allGranted: Bool {
        hasAccessibility && hasScreenRecording
    }

    /// Run the full permission check flow. Calls `onReady` when both permissions are granted.
    func checkAndRequest(onReady: @escaping () -> Void) {
        if allGranted {
            onReady()
            return
        }

        // Show alerts for missing permissions
        if !hasAccessibility {
            showAlert(
                title: "Accessibility Permission Required",
                message: "Sifu needs Accessibility access to track your workflow — clicks, keystrokes, and app switches. All data stays 100% local on your machine.",
                settingsURL: "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"
            )
        }

        if !hasScreenRecording {
            showAlert(
                title: "Screen Recording Permission Required",
                message: "Sifu needs Screen Recording access to capture screenshots of your workflow. All data stays 100% local on your machine.",
                settingsURL: "x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture"
            )
        }

        // Poll every 5 seconds until permissions are granted
        pollTimer = Timer.scheduledTimer(withTimeInterval: 5.0, repeats: true) { [weak self] timer in
            guard let self = self else { timer.invalidate(); return }
            if self.allGranted {
                timer.invalidate()
                self.pollTimer = nil
                self.writePermissionStatus()
                onReady()
            }
        }
    }

    func stopPolling() {
        pollTimer?.invalidate()
        pollTimer = nil
    }

    // MARK: - Alert

    private func showAlert(title: String, message: String, settingsURL: String) {
        let alert = NSAlert()
        alert.messageText = title
        alert.informativeText = message
        alert.alertStyle = .informational
        alert.addButton(withTitle: "Open System Settings")
        alert.addButton(withTitle: "Not Now")

        let response = alert.runModal()
        if response == .alertFirstButtonReturn {
            if let url = URL(string: settingsURL) {
                NSWorkspace.shared.open(url)
            }
        }
    }

    // MARK: - Status file

    private func writePermissionStatus() {
        let sifuDir = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent(".sifu")
        let statusFile = sifuDir.appendingPathComponent("permissions.json")

        let status: [String: Any] = [
            "accessibility": hasAccessibility,
            "screen_recording": hasScreenRecording,
            "last_checked": SessionManager.isoNow(),
            "granted_at": SessionManager.isoNow(),
        ]

        try? FileManager.default.createDirectory(at: sifuDir, withIntermediateDirectories: true)
        if let data = try? JSONSerialization.data(withJSONObject: status) {
            try? data.write(to: statusFile)
        }
    }
}
```

- [ ] **Step 2: Verify build**

Run: `cd extras/SifuBar && swift build 2>&1 | tail -5`
Expected: Build succeeds

- [ ] **Step 3: Commit**

```bash
git add extras/SifuBar/SifuBar/PermissionManager.swift
git commit -m "Add PermissionManager.swift — check and request macOS permissions"
```

---

## Task 6: TextAggregator.swift — Keystroke buffering

**Files:**
- Create: `extras/SifuBar/SifuBar/CaptureEngine/TextAggregator.swift`

- [ ] **Step 1: Write TextAggregator.swift**

Buffers individual keystrokes and flushes them as text_input or command events. Matches the Python `keyboard.py` buffering logic exactly.

```swift
import Foundation

final class TextAggregator {
    private var buffer: [Character] = []
    private var flushTimer: Timer?
    private let lock = NSLock()
    private let flushInterval: TimeInterval = 2.0

    /// Called when the buffer is flushed. Parameters: (text, isEnterPressed)
    var onFlush: ((String, Bool) -> Void)?

    func accumulate(_ char: Character) {
        lock.lock()
        buffer.append(char)
        lock.unlock()
        resetFlushTimer()
    }

    func handleBackspace() {
        lock.lock()
        if !buffer.isEmpty {
            buffer.removeLast()
        }
        lock.unlock()
    }

    func handleEnter() {
        cancelFlushTimer()
        flush(enterPressed: true)
    }

    /// Force flush on app switch or stop.
    func forceFlush() {
        cancelFlushTimer()
        flush(enterPressed: false)
    }

    func clear() {
        lock.lock()
        buffer.removeAll()
        lock.unlock()
        cancelFlushTimer()
    }

    // MARK: - Timer

    private func resetFlushTimer() {
        cancelFlushTimer()
        DispatchQueue.main.async { [weak self] in
            guard let self = self else { return }
            self.flushTimer = Timer.scheduledTimer(withTimeInterval: self.flushInterval, repeats: false) { [weak self] _ in
                self?.flush(enterPressed: false)
            }
        }
    }

    private func cancelFlushTimer() {
        DispatchQueue.main.async { [weak self] in
            self?.flushTimer?.invalidate()
            self?.flushTimer = nil
        }
    }

    // MARK: - Flush

    private func flush(enterPressed: Bool) {
        lock.lock()
        guard !buffer.isEmpty else {
            lock.unlock()
            return
        }
        let text = String(buffer)
        buffer.removeAll()
        lock.unlock()

        onFlush?(text, enterPressed)
    }
}
```

- [ ] **Step 2: Verify build**

Run: `cd extras/SifuBar && swift build 2>&1 | tail -5`
Expected: Build succeeds

- [ ] **Step 3: Commit**

```bash
git add extras/SifuBar/SifuBar/CaptureEngine/TextAggregator.swift
git commit -m "Add TextAggregator.swift — keystroke buffering with timer flush"
```

---

## Task 7: EventTapManager.swift — Mouse + keyboard capture

**Files:**
- Create: `extras/SifuBar/SifuBar/CaptureEngine/EventTapManager.swift`

- [ ] **Step 1: Write EventTapManager.swift**

CGEventTap for mouse clicks and keyboard events. Replaces Python `mouse.py` + `keyboard.py`. Includes the full keycode table, shift map, modifier detection, and AX element queries.

```swift
import ApplicationServices
import AppKit
import Foundation

// MARK: - Keycode table (matches data/keycodes.json)

private let keycodeTable: [UInt16: String] = [
    0: "a", 1: "s", 2: "d", 3: "f", 4: "h", 5: "g",
    6: "z", 7: "x", 8: "c", 9: "v", 11: "b", 12: "q",
    13: "w", 14: "e", 15: "r", 16: "y", 17: "t",
    18: "1", 19: "2", 20: "3", 21: "4", 22: "6", 23: "5",
    24: "=", 25: "9", 26: "7", 27: "-", 28: "8", 29: "0",
    30: "]", 31: "o", 32: "u", 33: "[", 34: "i", 35: "p",
    36: "Return", 37: "l", 38: "j", 39: "'", 40: "k",
    41: ";", 42: "\\", 43: ",", 44: "/", 45: "n", 46: "m",
    47: ".", 48: "Tab", 49: "Space", 50: "`", 51: "Delete",
    53: "Escape",
    55: "Command", 56: "Shift", 57: "CapsLock",
    58: "Option", 59: "Control",
    60: "RightShift", 61: "RightOption", 62: "RightControl",
    63: "Function",
    96: "F5", 97: "F6", 98: "F7", 99: "F3", 100: "F8",
    101: "F9", 103: "F11", 105: "F13", 107: "F14",
    109: "F10", 111: "F12", 113: "F15",
    115: "Home", 116: "PageUp", 117: "ForwardDelete", 118: "F4",
    119: "End", 120: "F2", 121: "PageDown", 122: "F1",
    123: "LeftArrow", 124: "RightArrow", 125: "DownArrow", 126: "UpArrow",
]

private let shiftMap: [Character: Character] = [
    "1": "!", "2": "@", "3": "#", "4": "$", "5": "%",
    "6": "^", "7": "&", "8": "*", "9": "(", "0": ")",
    "-": "_", "=": "+", "[": "{", "]": "}", "\\": "|",
    ";": ":", "'": "\"", ",": "<", ".": ">", "/": "?", "`": "~",
]

private let nonPrintableKeys: Set<String> = [
    "Return", "Tab", "Delete", "ForwardDelete", "Escape",
    "Command", "Shift", "CapsLock", "Option", "Control",
    "RightShift", "RightOption", "RightControl", "Function",
    "LeftArrow", "RightArrow", "UpArrow", "DownArrow",
    "Home", "End", "PageUp", "PageDown",
    "F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8",
    "F9", "F10", "F11", "F12", "F13", "F14", "F15",
]

private let modifierKeycodes: Set<UInt16> = [55, 56, 57, 58, 59, 60, 61, 62, 63]
private let keycodeReturn: UInt16 = 36
private let keycodeDelete: UInt16 = 51

/// Callback for captured events
struct CapturedEvent {
    let type: String          // "click", "right_click", "shortcut", "text_input", "command"
    let app: String?
    let window: String?
    let description: String?
    let element: String?
    let positionX: Int?
    let positionY: Int?
    let textContent: String?
    let shortcut: String?
}

final class EventTapManager {
    private var eventTap: CFMachPort?
    private var runLoopSource: CFRunLoopSource?
    private let textAggregator = TextAggregator()
    private var config: SifuConfig
    var paused: Bool = false

    /// Called for each captured event
    var onEvent: ((CapturedEvent) -> Void)?

    init(config: SifuConfig) {
        self.config = config

        textAggregator.onFlush = { [weak self] text, enterPressed in
            self?.handleTextFlush(text: text, enterPressed: enterPressed)
        }
    }

    // MARK: - Start / Stop

    func start() -> Bool {
        let mask: CGEventMask =
            (1 << CGEventType.leftMouseDown.rawValue) |
            (1 << CGEventType.rightMouseDown.rawValue) |
            (1 << CGEventType.keyDown.rawValue)

        // We need to use a C callback that bridges to our instance
        let refcon = Unmanaged.passUnretained(self).toOpaque()

        eventTap = CGEvent.tapCreate(
            tap: .cgSessionEventTap,
            place: .headInsertEventTap,
            options: .listenOnly,
            eventsOfInterest: mask,
            callback: eventTapCallback,
            userInfo: refcon
        )

        guard let tap = eventTap else {
            return false
        }

        runLoopSource = CFMachPortCreateRunLoopSource(kCFAllocatorDefault, tap, 0)
        CFRunLoopAddSource(CFRunLoopGetCurrent(), runLoopSource, .commonModes)
        CGEvent.tapEnable(tap: tap, enable: true)
        return true
    }

    func stop() {
        textAggregator.forceFlush()
        if let tap = eventTap {
            CGEvent.tapEnable(tap: tap, enable: false)
            eventTap = nil
        }
    }

    /// Flush text buffer (call on app switch)
    func flushText() {
        textAggregator.forceFlush()
    }

    // MARK: - Event handling

    fileprivate func handleCGEvent(type: CGEventType, event: CGEvent) {
        guard !paused else { return }

        let appName = Self.getFrontmostApp()
        if let app = appName, config.ignoreApps.contains(app) { return }

        switch type {
        case .leftMouseDown:
            handleMouseClick(event: event, isRight: false, app: appName)
        case .rightMouseDown:
            handleMouseClick(event: event, isRight: true, app: appName)
        case .keyDown:
            handleKeyDown(event: event, app: appName)
        default:
            break
        }
    }

    // MARK: - Mouse

    private func handleMouseClick(event: CGEvent, isRight: Bool, app: String?) {
        let loc = event.location
        let x = Int(loc.x)
        let y = Int(loc.y)

        let window = Self.getWindowTitle()
        let element = Self.getElementAtPosition(x: loc.x, y: loc.y)

        let desc: String
        if let el = element {
            desc = "Clicked '\(el)' in \(app ?? "unknown")"
        } else {
            desc = "Clicked at (\(x), \(y)) in \(app ?? "unknown")"
        }

        let captured = CapturedEvent(
            type: isRight ? "right_click" : "click",
            app: app,
            window: window,
            description: desc,
            element: element,
            positionX: x,
            positionY: y,
            textContent: nil,
            shortcut: nil
        )
        onEvent?(captured)
    }

    // MARK: - Keyboard

    private func handleKeyDown(event: CGEvent, app: String?) {
        let keycode = UInt16(event.getIntegerValueField(.keyboardEventKeycode))
        let flags = event.flags

        // Skip bare modifier keys
        if modifierKeycodes.contains(keycode) { return }

        let keyName = keycodeTable[keycode] ?? "key\(keycode)"

        // Shortcut: Cmd, Ctrl, or Opt held
        let hasCmdCtrlOpt = !flags.intersection([.maskCommand, .maskAlternate, .maskControl]).isEmpty

        if hasCmdCtrlOpt {
            handleShortcut(keyName: keyName, flags: flags, app: app)
            return
        }

        // Skip password fields for plain keystrokes
        if Self.isPasswordField() { return }

        // Enter key
        if keycode == keycodeReturn {
            textAggregator.handleEnter()
            return
        }

        // Delete key
        if keycode == keycodeDelete {
            textAggregator.handleBackspace()
            return
        }

        // Map keycode to character
        if let char = keycodeToChar(keycode: keycode, shiftHeld: flags.contains(.maskShift)) {
            textAggregator.accumulate(char)
        }
    }

    private func handleShortcut(keyName: String, flags: CGEventFlags, app: String?) {
        if Self.isPasswordField() { return }

        var parts: [String] = []
        if flags.contains(.maskCommand) { parts.append("Cmd") }
        if flags.contains(.maskShift) { parts.append("Shift") }
        if flags.contains(.maskAlternate) { parts.append("Opt") }
        if flags.contains(.maskControl) { parts.append("Ctrl") }

        guard !parts.isEmpty else { return }

        let shortcutStr = parts.joined(separator: "+") + "+" + keyName
        let window = Self.getWindowTitle()

        let captured = CapturedEvent(
            type: "shortcut",
            app: app,
            window: window,
            description: "Shortcut: \(shortcutStr)",
            element: nil,
            positionX: nil,
            positionY: nil,
            textContent: nil,
            shortcut: shortcutStr
        )
        onEvent?(captured)
    }

    private func handleTextFlush(text: String, enterPressed: Bool) {
        let app = Self.getFrontmostApp()
        if let a = app, config.ignoreApps.contains(a) { return }
        if paused { return }

        let isTerminal = app.map { config.terminalApps.contains($0) } ?? false
        let type: String
        let desc: String

        if enterPressed && isTerminal {
            type = "command"
            desc = "Command: \(text)"
        } else {
            type = "text_input"
            let truncated = text.count > 60 ? String(text.prefix(60)) + "\u{2026}" : text
            desc = "Typed: \(truncated)"
        }

        let window = Self.getWindowTitle()
        let captured = CapturedEvent(
            type: type,
            app: app,
            window: window,
            description: desc,
            element: nil,
            positionX: nil,
            positionY: nil,
            textContent: text,
            shortcut: nil
        )
        onEvent?(captured)
    }

    // MARK: - Keycode mapping

    private func keycodeToChar(keycode: UInt16, shiftHeld: Bool) -> Character? {
        guard let name = keycodeTable[keycode] else { return nil }
        if nonPrintableKeys.contains(name) { return nil }
        if name == "Space" { return " " }

        guard name.count == 1, let base = name.first else { return nil }

        if shiftHeld {
            return shiftMap[base] ?? Character(base.uppercased())
        }
        return base
    }

    // MARK: - Accessibility helpers

    static func getFrontmostApp() -> String? {
        NSWorkspace.shared.frontmostApplication?.localizedName
    }

    static func getWindowTitle() -> String? {
        guard let app = NSWorkspace.shared.frontmostApplication else { return nil }
        let axApp = AXUIElementCreateApplication(app.processIdentifier)
        var value: AnyObject?
        guard AXUIElementCopyAttributeValue(axApp, "AXFocusedWindow" as CFString, &value) == .success,
              let window = value else { return nil }
        var title: AnyObject?
        guard AXUIElementCopyAttributeValue(window as! AXUIElement, "AXTitle" as CFString, &title) == .success,
              let titleStr = title as? String else { return nil }
        return titleStr
    }

    static func getElementAtPosition(x: CGFloat, y: CGFloat) -> String? {
        let systemWide = AXUIElementCreateSystemWide()
        var element: AXUIElement?
        guard AXUIElementCopyElementAtPosition(systemWide, Float(x), Float(y), &element) == .success,
              let el = element else { return nil }

        // Skip password fields
        var role: AnyObject?
        if AXUIElementCopyAttributeValue(el, "AXRole" as CFString, &role) == .success,
           let roleStr = role as? String, roleStr == "AXSecureTextField" {
            return nil
        }

        // Prefer AXDescription
        var desc: AnyObject?
        if AXUIElementCopyAttributeValue(el, "AXDescription" as CFString, &desc) == .success,
           let descStr = desc as? String, !descStr.isEmpty {
            return descStr
        }

        // Fall back to AXTitle
        var title: AnyObject?
        if AXUIElementCopyAttributeValue(el, "AXTitle" as CFString, &title) == .success,
           let titleStr = title as? String, !titleStr.isEmpty {
            return titleStr
        }

        return nil
    }

    static func isPasswordField() -> Bool {
        guard let app = NSWorkspace.shared.frontmostApplication else { return false }
        let axApp = AXUIElementCreateApplication(app.processIdentifier)
        var focused: AnyObject?
        guard AXUIElementCopyAttributeValue(axApp, "AXFocusedUIElement" as CFString, &focused) == .success,
              let el = focused else { return false }
        var role: AnyObject?
        if AXUIElementCopyAttributeValue(el as! AXUIElement, "AXRole" as CFString, &role) == .success,
           let roleStr = role as? String, roleStr == "AXSecureTextField" {
            return true
        }
        return false
    }
}

// MARK: - C callback bridge

private func eventTapCallback(
    proxy: CGEventTapProxy,
    type: CGEventType,
    event: CGEvent,
    userInfo: UnsafeMutableRawPointer?
) -> Unmanaged<CGEvent>? {
    guard let userInfo = userInfo else { return Unmanaged.passUnretained(event) }
    let manager = Unmanaged<EventTapManager>.fromOpaque(userInfo).takeUnretainedValue()

    // Re-enable tap if it was disabled by the system (rate limiting)
    if type == .tapDisabledByTimeout || type == .tapDisabledByUserInput {
        if let tap = manager.eventTap {
            CGEvent.tapEnable(tap: tap, enable: true)
        }
        return Unmanaged.passUnretained(event)
    }

    manager.handleCGEvent(type: type, event: event)
    return Unmanaged.passUnretained(event)
}
```

- [ ] **Step 2: Verify build**

Run: `cd extras/SifuBar && swift build 2>&1 | tail -5`
Expected: Build succeeds

- [ ] **Step 3: Commit**

```bash
git add extras/SifuBar/SifuBar/CaptureEngine/EventTapManager.swift
git commit -m "Add EventTapManager.swift — CGEventTap for mouse + keyboard capture"
```

---

## Task 8: AppTracker.swift — App and window switch tracking

**Files:**
- Create: `extras/SifuBar/SifuBar/CaptureEngine/AppTracker.swift`

- [ ] **Step 1: Write AppTracker.swift**

Monitors app switches via NSWorkspace notifications and polls window titles via Accessibility API.

```swift
import AppKit
import ApplicationServices

final class AppTracker {
    private var currentApp: String?
    private var currentWindow: String?
    private var pollTimer: Timer?
    private let config: SifuConfig
    var paused: Bool = false

    /// Called on app or window switch. Parameters: (eventType, newApp, newWindow, description)
    var onSwitch: ((String, String?, String?, String) -> Void)?

    init(config: SifuConfig) {
        self.config = config
    }

    func start() {
        // Snapshot initial state
        if let app = NSWorkspace.shared.frontmostApplication {
            currentApp = app.localizedName
        }
        currentWindow = EventTapManager.getWindowTitle()

        // Register for app activation notifications
        NSWorkspace.shared.notificationCenter.addObserver(
            self,
            selector: #selector(appDidActivate(_:)),
            name: NSWorkspace.didActivateApplicationNotification,
            object: nil
        )

        // Poll window title every 3 seconds
        pollTimer = Timer.scheduledTimer(withTimeInterval: 3.0, repeats: true) { [weak self] _ in
            self?.pollWindowTitle()
        }
    }

    func stop() {
        NSWorkspace.shared.notificationCenter.removeObserver(self)
        pollTimer?.invalidate()
        pollTimer = nil
    }

    // MARK: - App switch

    @objc private func appDidActivate(_ notification: Notification) {
        guard !paused else { return }
        guard let app = notification.userInfo?[NSWorkspace.applicationUserInfoKey] as? NSRunningApplication,
              let newApp = app.localizedName else { return }
        guard newApp != currentApp else { return }

        if config.ignoreApps.contains(newApp) {
            currentApp = newApp
            return
        }

        let prevApp = currentApp ?? "unknown"
        let desc = "Switched from \(prevApp) to \(newApp)"
        currentApp = newApp

        onSwitch?("app_switch", newApp, currentWindow, desc)
    }

    // MARK: - Window title polling

    private func pollWindowTitle() {
        guard !paused else { return }

        let title = EventTapManager.getWindowTitle()
        if let title = title, title != currentWindow {
            guard let app = currentApp, !config.ignoreApps.contains(app) else {
                currentWindow = title
                return
            }

            let desc = "Window: \(title)"
            currentWindow = title
            onSwitch?("window_switch", currentApp, title, desc)
        } else if let title = title {
            currentWindow = title
        }
    }
}
```

- [ ] **Step 2: Verify build**

Run: `cd extras/SifuBar && swift build 2>&1 | tail -5`
Expected: Build succeeds

- [ ] **Step 3: Commit**

```bash
git add extras/SifuBar/SifuBar/CaptureEngine/AppTracker.swift
git commit -m "Add AppTracker.swift — app/window switch tracking via NSWorkspace + AX"
```

---

## Task 9: ScreenshotCapture.swift — Screenshot capture with dedup

**Files:**
- Create: `extras/SifuBar/SifuBar/CaptureEngine/ScreenshotCapture.swift`

- [ ] **Step 1: Write ScreenshotCapture.swift**

Captures screenshots on significant events with deduplication and disk budget management. Matches Python `screenshots.py` + `disk.py` logic.

```swift
import AppKit
import Foundation

final class ScreenshotCapture {
    private let config: SifuConfig
    private let screenshotsDir: URL
    private var lastApp: String?
    private var lastWindow: String?
    private var lastTime: Date = .distantPast
    private var captureCount: Int = 0
    private let lock = NSLock()

    init(config: SifuConfig) {
        self.config = config
        self.screenshotsDir = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent(".sifu/screenshots")
    }

    /// Capture a screenshot if conditions are met. Returns the file path or nil.
    func captureIfNeeded(app: String?, window: String?, eventType: String) -> String? {
        lock.lock()
        defer { lock.unlock() }

        // Skip mid-typing text events
        if eventType == "text_input" { return nil }

        // Dedup: skip if same context within min interval
        if app == lastApp && window == lastWindow &&
           Date().timeIntervalSince(lastTime) < config.screenshotMinIntervalS {
            return nil
        }

        guard let path = takeScreenshot() else { return nil }

        lastApp = app
        lastWindow = window
        lastTime = Date()

        // Periodic disk budget enforcement
        captureCount += 1
        if captureCount % 100 == 0 {
            DispatchQueue.global(qos: .utility).async { [weak self] in
                self?.evictOldest()
            }
        }

        return path
    }

    // MARK: - Capture

    private func takeScreenshot() -> String? {
        guard let image = CGWindowListCreateImage(
            CGRect.infinite,
            .optionOnScreenOnly,
            kCGNullWindowID,
            []
        ) else { return nil }

        let bitmap = NSBitmapImageRep(cgImage: image)
        let quality = CGFloat(config.screenshotQuality) / 100.0
        guard let jpegData = bitmap.representation(
            using: .jpeg,
            properties: [.compressionFactor: quality]
        ) else { return nil }

        let path = generatePath()
        let dirURL = URL(fileURLWithPath: path).deletingLastPathComponent()
        try? FileManager.default.createDirectory(at: dirURL, withIntermediateDirectories: true)

        do {
            try jpegData.write(to: URL(fileURLWithPath: path))
            return path
        } catch {
            return nil
        }
    }

    // MARK: - Path generation (matches Python disk.py)

    private func generatePath() -> String {
        let now = Date()
        let dayFmt = DateFormatter()
        dayFmt.dateFormat = "yyyy-MM-dd"
        let timeFmt = DateFormatter()
        timeFmt.dateFormat = "HH-mm-ss"
        let ms = Int((now.timeIntervalSince1970.truncatingRemainder(dividingBy: 1)) * 1000)

        let dayDir = screenshotsDir.appendingPathComponent(dayFmt.string(from: now))
        let filename = "\(timeFmt.string(from: now))-\(String(format: "%03d", ms)).jpg"
        return dayDir.appendingPathComponent(filename).path
    }

    // MARK: - Disk budget (matches Python disk.py)

    private func getDiskUsageMB() -> Double {
        guard FileManager.default.fileExists(atPath: screenshotsDir.path) else { return 0.0 }

        var total: UInt64 = 0
        if let enumerator = FileManager.default.enumerator(at: screenshotsDir, includingPropertiesForKeys: [.fileSizeKey]) {
            for case let fileURL as URL in enumerator {
                if let size = try? fileURL.resourceValues(forKeys: [.fileSizeKey]).fileSize {
                    total += UInt64(size)
                }
            }
        }
        return Double(total) / (1024 * 1024)
    }

    private func evictOldest() {
        while getDiskUsageMB() > Double(config.screenshotBudgetMB) {
            var oldestURL: URL?
            var oldestDate: Date = .distantFuture

            if let enumerator = FileManager.default.enumerator(at: screenshotsDir, includingPropertiesForKeys: [.contentModificationDateKey]) {
                for case let fileURL as URL in enumerator {
                    if let date = try? fileURL.resourceValues(forKeys: [.contentModificationDateKey]).contentModificationDate,
                       date < oldestDate {
                        oldestDate = date
                        oldestURL = fileURL
                    }
                }
            }

            guard let toDelete = oldestURL else { break }
            try? FileManager.default.removeItem(at: toDelete)

            // Clean empty parent directory
            let parent = toDelete.deletingLastPathComponent()
            if let contents = try? FileManager.default.contentsOfDirectory(atPath: parent.path), contents.isEmpty {
                try? FileManager.default.removeItem(at: parent)
            }
        }
    }
}
```

- [ ] **Step 2: Verify build**

Run: `cd extras/SifuBar && swift build 2>&1 | tail -5`
Expected: Build succeeds

- [ ] **Step 3: Commit**

```bash
git add extras/SifuBar/SifuBar/CaptureEngine/ScreenshotCapture.swift
git commit -m "Add ScreenshotCapture.swift — screenshot capture with dedup + disk budget"
```

---

## Task 10: CLIBridge.swift + LoginItemManager.swift

**Files:**
- Create: `extras/SifuBar/SifuBar/Bridge/CLIBridge.swift`
- Create: `extras/SifuBar/SifuBar/Bridge/LoginItemManager.swift`

- [ ] **Step 1: Write CLIBridge.swift**

Watches `~/.sifu/command.json` for CLI commands. Polled during the existing 5s timer.

```swift
import Foundation

final class CLIBridge {
    private let commandFile: URL

    /// Called when a command is received. Parameter: command string (start, stop, pause, resume, sensitive)
    var onCommand: ((String) -> Void)?

    init() {
        commandFile = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent(".sifu/command.json")
    }

    /// Check for a pending command. Call this from the poll timer.
    func checkForCommand() {
        guard FileManager.default.fileExists(atPath: commandFile.path),
              let data = try? Data(contentsOf: commandFile),
              let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let command = json["command"] as? String else { return }

        // Delete the command file before executing
        try? FileManager.default.removeItem(at: commandFile)

        onCommand?(command)
    }
}
```

- [ ] **Step 2: Write LoginItemManager.swift**

```swift
import ServiceManagement

final class LoginItemManager {
    var isEnabled: Bool {
        SMAppService.mainApp.status == .enabled
    }

    func enable() {
        try? SMAppService.mainApp.register()
    }

    func disable() {
        try? SMAppService.mainApp.unregister()
    }

    func toggle() {
        if isEnabled {
            disable()
        } else {
            enable()
        }
    }
}
```

- [ ] **Step 3: Verify build**

Run: `cd extras/SifuBar && swift build 2>&1 | tail -5`
Expected: Build succeeds

- [ ] **Step 4: Commit**

```bash
git add extras/SifuBar/SifuBar/Bridge/CLIBridge.swift extras/SifuBar/SifuBar/Bridge/LoginItemManager.swift
git commit -m "Add CLIBridge.swift + LoginItemManager.swift — CLI command file + login item"
```

---

## Task 11: Rewrite SifuBarApp.swift — Wire everything together

**Files:**
- Modify: `extras/SifuBar/SifuBar/SifuBarApp.swift`

This is the main integration task. Rewrite the app delegate to wire up: permissions -> capture engine -> event store -> menu UI -> CLI bridge.

- [ ] **Step 1: Rewrite SifuBarApp.swift**

Replace the entire file with the new version that owns capture:

```swift
import SwiftUI
import AppKit

@main
struct SifuBarApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var appDelegate

    var body: some Scene {
        Settings { EmptyView() }
    }
}

class AppDelegate: NSObject, NSApplicationDelegate {
    private var statusItem: NSStatusItem?
    private var pollTimer: Timer?

    // Core components
    private let permissionManager = PermissionManager()
    private let eventStore = EventStore()
    private lazy var sessionManager = SessionManager(store: eventStore)
    private lazy var config = SifuConfig.load()
    private lazy var eventTapManager = EventTapManager(config: config)
    private lazy var appTracker = AppTracker(config: config)
    private lazy var screenshotCapture = ScreenshotCapture(config: config)
    private let cliBridge = CLIBridge()
    private let loginItemManager = LoginItemManager()

    private var isCapturing = false

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.accessory)

        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        updateMenu()

        // Enable login item on first launch
        if config.startAtLogin && !loginItemManager.isEnabled {
            loginItemManager.enable()
        }

        // Wire up CLI bridge
        cliBridge.onCommand = { [weak self] command in
            self?.handleCLICommand(command)
        }

        // Start poll timer (menu updates + CLI bridge checks)
        pollTimer = Timer.scheduledTimer(withTimeInterval: 5.0, repeats: true) { [weak self] _ in
            self?.updateMenu()
            self?.cliBridge.checkForCommand()
        }

        // Check permissions and auto-start capture
        permissionManager.checkAndRequest { [weak self] in
            DispatchQueue.main.async {
                self?.startCapture()
            }
        }
    }

    func applicationWillTerminate(_ notification: Notification) {
        stopCapture()
    }

    // MARK: - Capture lifecycle

    private func startCapture() {
        guard !isCapturing else { return }
        guard permissionManager.allGranted else {
            permissionManager.checkAndRequest { [weak self] in
                DispatchQueue.main.async {
                    self?.startCapture()
                }
            }
            return
        }

        sessionManager.startSession()

        // Wire event tap -> store + screenshot
        eventTapManager.onEvent = { [weak self] captured in
            guard let self = self else { return }
            let sessionId = self.sessionManager.sessionId

            let eventId = self.eventStore.insertEvent(
                timestamp: SessionManager.isoNow(),
                type: captured.type,
                app: captured.app,
                window: captured.window,
                description: captured.description,
                element: captured.element,
                positionX: captured.positionX,
                positionY: captured.positionY,
                textContent: captured.textContent,
                shortcut: captured.shortcut,
                screenshotPath: nil,
                sessionId: sessionId
            )
            self.sessionManager.incrementEventCount()

            // Delayed screenshot (300ms for UI to update after click)
            let delay: TimeInterval = (captured.type == "click" || captured.type == "right_click") ? 0.3 : 0.0
            DispatchQueue.global(qos: .utility).asyncAfter(deadline: .now() + delay) {
                if let path = self.screenshotCapture.captureIfNeeded(
                    app: captured.app,
                    window: captured.window,
                    eventType: captured.type
                ) {
                    self.eventStore.updateScreenshotPath(eventId: eventId, path: path)
                }
            }
        }

        // Wire app tracker -> store + screenshot + text flush
        appTracker.onSwitch = { [weak self] eventType, app, window, description in
            guard let self = self else { return }
            let sessionId = self.sessionManager.sessionId

            // Flush text buffer on app switch
            if eventType == "app_switch" {
                self.eventTapManager.flushText()
            }

            let eventId = self.eventStore.insertEvent(
                timestamp: SessionManager.isoNow(),
                type: eventType,
                app: app,
                window: window,
                description: description,
                element: nil,
                positionX: nil,
                positionY: nil,
                textContent: nil,
                shortcut: nil,
                screenshotPath: nil,
                sessionId: sessionId
            )
            self.sessionManager.incrementEventCount()

            // Screenshot on app switch
            if eventType == "app_switch" {
                DispatchQueue.global(qos: .utility).async {
                    if let path = self.screenshotCapture.captureIfNeeded(
                        app: app, window: window, eventType: eventType
                    ) {
                        self.eventStore.updateScreenshotPath(eventId: eventId, path: path)
                    }
                }
            }
        }

        let tapStarted = eventTapManager.start()
        if !tapStarted {
            print("[SifuBar] WARNING: CGEventTap creation failed — check Accessibility permissions")
        }
        appTracker.start()
        isCapturing = true
        updateMenu()
    }

    private func stopCapture() {
        guard isCapturing else { return }
        eventTapManager.stop()
        appTracker.stop()
        sessionManager.endSession()
        isCapturing = false
        updateMenu()
    }

    private func pauseCapture() {
        eventTapManager.paused = true
        appTracker.paused = true
        sessionManager.writePausedState()
        updateMenu()
    }

    private func resumeCapture() {
        eventTapManager.paused = false
        appTracker.paused = false
        sessionManager.writeRecordingState()
        updateMenu()
    }

    private func handleSensitive() {
        pauseCapture()
        let paths = eventStore.purgeRecent(minutes: config.sensitivePurgeMinutes)
        for path in paths {
            try? FileManager.default.removeItem(atPath: path)
        }
    }

    // MARK: - CLI bridge

    private func handleCLICommand(_ command: String) {
        switch command {
        case "start": startCapture()
        case "stop": stopCapture()
        case "pause": pauseCapture()
        case "resume": resumeCapture()
        case "sensitive": handleSensitive()
        default: break
        }
    }

    // MARK: - Menu UI

    private func updateMenu() {
        guard let statusItem = statusItem else { return }

        let isPaused = eventTapManager.paused

        // Menu bar title
        if !permissionManager.allGranted {
            statusItem.button?.title = "\u{25C7} Sifu (setup needed)"
        } else if isCapturing {
            statusItem.button?.title = isPaused ? "\u{25CE} Sifu" : "\u{25C9} Sifu"
        } else {
            statusItem.button?.title = "\u{25C7} Sifu"
        }

        let menu = NSMenu()

        if !permissionManager.allGranted {
            let permItem = NSMenuItem(title: "Grant permissions to start recording", action: #selector(requestPermissions), keyEquivalent: "")
            permItem.target = self
            menu.addItem(permItem)
            menu.addItem(NSMenuItem.separator())
        } else if isCapturing {
            let events = sessionManager.eventCount
            let sessionId = sessionManager.sessionId ?? "\u{2014}"

            if isPaused {
                let h = NSMenuItem(title: "Paused \u{2014} \(events) events", action: nil, keyEquivalent: "")
                h.isEnabled = false
                menu.addItem(h)
            } else {
                let h = NSMenuItem(title: "Recording \u{2014} \(events) events", action: nil, keyEquivalent: "")
                h.isEnabled = false
                menu.addItem(h)
            }

            let s = NSMenuItem(title: sessionId, action: nil, keyEquivalent: "")
            s.isEnabled = false
            menu.addItem(s)

            menu.addItem(NSMenuItem.separator())

            let stopItem = NSMenuItem(title: "\u{23F9} Stop (+ analyze)", action: #selector(stopAction), keyEquivalent: "")
            stopItem.target = self
            menu.addItem(stopItem)

            if isPaused {
                let resumeItem = NSMenuItem(title: "\u{25B6} Resume", action: #selector(resumeAction), keyEquivalent: "")
                resumeItem.target = self
                menu.addItem(resumeItem)
            } else {
                let pauseItem = NSMenuItem(title: "\u{23F8} Pause", action: #selector(pauseAction), keyEquivalent: "")
                pauseItem.target = self
                menu.addItem(pauseItem)
            }

            let sensitiveItem = NSMenuItem(title: "\u{1F512} Sensitive (purge 5m)", action: #selector(sensitiveAction), keyEquivalent: "")
            sensitiveItem.target = self
            menu.addItem(sensitiveItem)
        } else {
            let h = NSMenuItem(title: "Not recording", action: nil, keyEquivalent: "")
            h.isEnabled = false
            menu.addItem(h)
            menu.addItem(NSMenuItem.separator())

            let startItem = NSMenuItem(title: "\u{25B6} Start Recording", action: #selector(startAction), keyEquivalent: "")
            startItem.target = self
            menu.addItem(startItem)
        }

        menu.addItem(NSMenuItem.separator())

        // Quick actions
        for (title, sel) in [
            ("\u{1F4CB} Compile SOPs", #selector(compileSifu)),
            ("\u{1F3AF} Coach Report", #selector(coachSifu)),
            ("\u{1F4CA} Show Patterns", #selector(patternsSifu)),
            ("\u{1F4DD} Show Log", #selector(logSifu)),
        ] as [(String, Selector)] {
            let item = NSMenuItem(title: title, action: sel, keyEquivalent: "")
            item.target = self
            menu.addItem(item)
        }

        menu.addItem(NSMenuItem.separator())

        // Login item toggle
        let loginTitle = loginItemManager.isEnabled ? "\u{2705} Start at Login" : "Start at Login"
        let loginItem = NSMenuItem(title: loginTitle, action: #selector(toggleLoginItem), keyEquivalent: "")
        loginItem.target = self
        menu.addItem(loginItem)

        let configItem = NSMenuItem(title: "\u{2699}\u{FE0F} Config", action: #selector(configSifu), keyEquivalent: "")
        configItem.target = self
        menu.addItem(configItem)

        let openDataItem = NSMenuItem(title: "\u{1F4C2} Open Data", action: #selector(openData), keyEquivalent: "")
        openDataItem.target = self
        menu.addItem(openDataItem)

        menu.addItem(NSMenuItem.separator())

        let quitItem = NSMenuItem(title: "Quit SifuBar", action: #selector(quitApp), keyEquivalent: "q")
        quitItem.target = self
        menu.addItem(quitItem)

        statusItem.menu = menu
    }

    // MARK: - Menu actions

    @objc private func requestPermissions() {
        permissionManager.checkAndRequest { [weak self] in
            DispatchQueue.main.async {
                self?.startCapture()
            }
        }
    }

    @objc private func startAction() { startCapture() }
    @objc private func stopAction() {
        stopCapture()
        // Launch analysis via CLI
        runSifuInTerminal("_analyze")
    }
    @objc private func pauseAction() { pauseCapture() }
    @objc private func resumeAction() { resumeCapture() }
    @objc private func sensitiveAction() { handleSensitive() }

    @objc private func compileSifu() { runSifuInTerminal("compile") }
    @objc private func coachSifu() { runSifuInTerminal("coach --today") }
    @objc private func patternsSifu() { runSifuInTerminal("patterns --today") }
    @objc private func logSifu() { runSifuInTerminal("log --last 1h") }
    @objc private func configSifu() { runSifuInTerminal("config") }
    @objc private func toggleLoginItem() { loginItemManager.toggle(); updateMenu() }

    @objc private func openData() {
        let sifuDir = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent(".sifu")
        NSWorkspace.shared.open(sifuDir)
    }

    @objc private func quitApp() {
        stopCapture()
        NSApp.terminate(nil)
    }

    // MARK: - Terminal helper

    private func runSifuInTerminal(_ subcommand: String) {
        let script = "tell application \"Terminal\" to do script \"sifu \(subcommand)\""
        let proc = Process()
        proc.executableURL = URL(fileURLWithPath: "/usr/bin/osascript")
        proc.arguments = ["-e", script]
        try? proc.run()
    }
}
```

- [ ] **Step 2: Verify build**

Run: `cd extras/SifuBar && swift build 2>&1 | tail -5`
Expected: Build succeeds

- [ ] **Step 3: Smoke test — launch the app**

Run: `cd extras/SifuBar && swift run SifuBar &`
Expected: SifuBar icon appears in menu bar. If permissions not yet granted, alert dialogs appear.

- [ ] **Step 4: Commit**

```bash
git add extras/SifuBar/SifuBar/SifuBarApp.swift
git commit -m "Rewrite SifuBarApp.swift — full capture engine with permissions, sessions, CLI bridge"
```

---

## Task 12: Update Python daemon.py — Delegate to SifuBar

**Files:**
- Modify: `src/sifu/daemon.py`

- [ ] **Step 1: Rewrite daemon.py to delegate to SifuBar**

Replace the capture-loop code with command-file writes. Keep `get_status()` and analysis launch unchanged.

```python
"""Sifu daemon interface — delegates capture to native SifuBar.app.

SifuBar.app (Swift) owns all macOS permissions and runs the capture
engine.  This module provides the CLI interface that communicates
with SifuBar via a command file (~/.sifu/command.json).
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import click

SIFU_DIR = Path.home() / ".sifu"
PID_FILE = SIFU_DIR / "sifubar.pid"
STATE_FILE = SIFU_DIR / "daemon.state"
COMMAND_FILE = SIFU_DIR / "command.json"
LOG_FILE = SIFU_DIR / "daemon.log"


# -- State helpers -----------------------------------------------------------

def _read_state() -> dict:
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def _is_sifubar_running() -> bool:
    """Check if SifuBar is running via its PID file."""
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
            os.kill(pid, 0)
            return True
        except (OSError, ValueError):
            pass
    return False


def _send_command(command: str):
    """Write a command to the command file for SifuBar to pick up."""
    SIFU_DIR.mkdir(parents=True, exist_ok=True)
    with open(COMMAND_FILE, "w") as f:
        json.dump({"command": command, "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S")}, f)


def _launch_sifubar():
    """Launch SifuBar.app if not already running."""
    if _is_sifubar_running():
        return True

    # Try to open the app bundle
    app_paths = [
        Path("/Applications/SifuBar.app"),
        Path.home() / "Applications" / "SifuBar.app",
        # Development: built from extras/SifuBar
        Path(__file__).parent.parent.parent / "extras" / "SifuBar" / ".build" / "release" / "SifuBar",
    ]

    for app_path in app_paths:
        if app_path.exists():
            if app_path.suffix == ".app":
                subprocess.Popen(["open", str(app_path)])
            else:
                subprocess.Popen(
                    [str(app_path)],
                    stdout=open(LOG_FILE, "a"),
                    stderr=open(LOG_FILE, "a"),
                    start_new_session=True,
                )
            # Wait briefly for it to start
            time.sleep(2)
            return True

    return False


# -- Public API (called from CLI) --------------------------------------------

def start_daemon():
    """Start capture via SifuBar."""
    state = _read_state()
    if state.get("status") in ("recording", "paused"):
        click.echo("Sifu is already running.")
        return

    if not _launch_sifubar():
        click.echo(
            "SifuBar not found. Install SifuBar.app or build from extras/SifuBar.\n"
            "  cd extras/SifuBar && swift build -c release"
        )
        return

    _send_command("start")
    click.echo("Sifu starting (via SifuBar).")


def stop_daemon():
    """Stop capture and launch analysis."""
    state = _read_state()
    if state.get("status") not in ("recording", "paused"):
        click.echo("Sifu is not running.")
        return

    _send_command("stop")
    click.echo("Sifu stopped.")

    # Auto-launch analysis
    click.echo("\nAnalyzing session...")
    _launch_analysis()


def _launch_analysis():
    """Run pattern detection -> compile SOPs -> coaching, all inline."""
    try:
        from sifu.patterns.engine import show_patterns
        show_patterns(today=True)
    except Exception as exc:
        click.echo(f"  Pattern detection: {exc}")

    click.echo("\nCompiling SOPs...")
    try:
        from sifu.compiler.sop import compile_workflows
        compile_workflows(today=True)
    except Exception as exc:
        click.echo(f"  Compile error: {exc}")

    click.echo("\nLaunching coach (background)...")
    log_fh = open(LOG_FILE, "a")
    subprocess.Popen(
        [sys.executable, "-c",
         "from sifu.coach.analyzer import run_coach; run_coach(today=True)"],
        stdout=log_fh, stderr=log_fh, start_new_session=True,
    )
    click.echo("  Coaching report building in background -> ~/.sifu/output/coach/")


def pause_daemon():
    """Pause capture."""
    if _read_state().get("status") != "recording":
        click.echo("Sifu is not recording.")
        return
    _send_command("pause")
    click.echo("Sifu paused.")


def resume_daemon():
    """Resume capture after pause."""
    if _read_state().get("status") != "paused":
        click.echo("Sifu is not paused.")
        return
    _send_command("resume")
    click.echo("Sifu resumed.")


def get_status(as_json=False):
    """Display daemon status and session stats."""
    state = _read_state()
    running = _is_sifubar_running()
    status = state.get("status", "stopped")

    info = {
        "running": running,
        "pid": state.get("pid"),
        "status": status,
        "session_id": state.get("session_id"),
        "start_time": state.get("start_time"),
        "steps": state.get("events", 0),
    }

    if info["start_time"]:
        from datetime import datetime
        start = datetime.fromisoformat(info["start_time"])
        info["duration_min"] = round((datetime.now() - start).total_seconds() / 60, 1)

    if as_json:
        click.echo(json.dumps(info))
    else:
        if running and status != "stopped":
            click.echo(f"  Status:   {status}")
            click.echo(f"  PID:      {info.get('pid', '?')}")
            click.echo(f"  Session:  {info.get('session_id', '?')}")
            click.echo(f"  Started:  {info.get('start_time', '?')}")
            click.echo(f"  Events:   {info.get('steps', 0)}")
            if "duration_min" in info:
                click.echo(f"  Duration: {info['duration_min']}m")
        else:
            click.echo("  Sifu is not running.")


def toggle_sensitive():
    """Pause capture and purge last N minutes."""
    if _read_state().get("status") not in ("recording", "paused"):
        click.echo("Sifu is not running.")
        return
    _send_command("sensitive")
    from sifu.config import get
    minutes = get("sensitive_purge_minutes", 5)
    click.echo(f"Purged last {minutes} minutes. Use 'sifu resume' to continue.")
```

- [ ] **Step 2: Verify Python CLI still works**

Run: `cd /Users/heymitch/sifu && python -m sifu.cli status`
Expected: Shows "Sifu is not running." or current status

- [ ] **Step 3: Commit**

```bash
git add src/sifu/daemon.py
git commit -m "Rewrite daemon.py — delegate capture to SifuBar via command file"
```

---

## Task 13: Remove Python capture modules

**Files:**
- Remove: `src/sifu/capture/mouse.py`
- Remove: `src/sifu/capture/keyboard.py`
- Remove: `src/sifu/capture/apps.py`
- Remove: `src/sifu/capture/screenshots.py`
- Remove: `src/sifu/bar/app.py`
- Modify: `src/sifu/capture/__init__.py` (clear it)

- [ ] **Step 1: Remove replaced Python capture files**

```bash
cd /Users/heymitch/sifu
rm src/sifu/capture/mouse.py
rm src/sifu/capture/keyboard.py
rm src/sifu/capture/apps.py
rm src/sifu/capture/screenshots.py
rm src/sifu/bar/app.py
echo "" > src/sifu/capture/__init__.py
```

- [ ] **Step 2: Check for remaining imports of removed modules**

Run: `grep -r "from sifu.capture" src/sifu/ --include="*.py"`
Expected: Only `__init__.py` and daemon.py references remain (daemon.py no longer imports capture modules)

Run: `grep -r "from sifu.bar" src/sifu/ --include="*.py"`
Expected: Only daemon.py `_launch_sifubar` reference (if any), no imports of `bar.app`

- [ ] **Step 3: Fix any remaining import references**

If any files still import from removed modules, update or remove those imports.

- [ ] **Step 4: Verify Python package still loads**

Run: `cd /Users/heymitch/sifu && python -c "from sifu.cli import cli; print('OK')"`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add -A src/sifu/capture/ src/sifu/bar/
git commit -m "Remove Python capture modules — replaced by Swift SifuBar"
```

---

## Task 14: Build .app bundle + integration test

**Files:**
- Create: `extras/SifuBar/build-app.sh`

- [ ] **Step 1: Create build script that produces a proper .app bundle**

```bash
#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

echo "Building SifuBar..."
swift build -c release

APP_DIR="build/SifuBar.app/Contents"
mkdir -p "$APP_DIR/MacOS"

cp .build/release/SifuBar "$APP_DIR/MacOS/SifuBar"
cp SifuBar/Info.plist "$APP_DIR/Info.plist"

echo "Built: build/SifuBar.app"
echo ""
echo "To install: cp -r build/SifuBar.app /Applications/"
echo "To run:     open build/SifuBar.app"
```

- [ ] **Step 2: Make executable and run**

```bash
chmod +x extras/SifuBar/build-app.sh
cd extras/SifuBar && ./build-app.sh
```

Expected: `build/SifuBar.app` created with proper bundle structure

- [ ] **Step 3: Launch the built app**

Run: `open extras/SifuBar/build/SifuBar.app`
Expected: SifuBar appears in menu bar. Permission prompts appear if needed. After granting permissions, capture begins automatically.

- [ ] **Step 4: Test CLI integration**

Run: `echo '{"command":"pause","timestamp":"2026-04-01T15:00:00"}' > ~/.sifu/command.json && sleep 6 && cat ~/.sifu/daemon.state`
Expected: State file shows `"status": "paused"`

Run: `echo '{"command":"resume","timestamp":"2026-04-01T15:00:05"}' > ~/.sifu/command.json && sleep 6 && cat ~/.sifu/daemon.state`
Expected: State file shows `"status": "recording"`

- [ ] **Step 5: Verify events are in SQLite**

Run: `sqlite3 ~/.sifu/capture.db "SELECT COUNT(*) FROM events WHERE timestamp >= date('now')"`
Expected: Non-zero count (events captured by SifuBar)

Run: `sqlite3 ~/.sifu/capture.db "SELECT type, app, description FROM events ORDER BY id DESC LIMIT 5"`
Expected: Recent events with types matching the spec (click, shortcut, app_switch, etc.)

- [ ] **Step 6: Verify Python can read SifuBar's events**

Run: `cd /Users/heymitch/sifu && python -m sifu.cli log --last 1h`
Expected: Shows events that SifuBar captured

- [ ] **Step 7: Commit**

```bash
git add extras/SifuBar/build-app.sh
git commit -m "Add build-app.sh — creates proper .app bundle for SifuBar"
```

---

## Task 15: Install to /Applications and final verification

- [ ] **Step 1: Install app**

```bash
cp -r extras/SifuBar/build/SifuBar.app /Applications/
```

- [ ] **Step 2: Verify CLI can launch installed app**

Run: `cd /Users/heymitch/sifu && python -m sifu.cli start`
Expected: "Sifu starting (via SifuBar)." — SifuBar launches from /Applications

- [ ] **Step 3: Verify login item**

Open SifuBar menu -> "Start at Login" should have checkmark. Verify in System Settings -> General -> Login Items that SifuBar appears.

- [ ] **Step 4: Full stop + analyze cycle**

Run: `cd /Users/heymitch/sifu && python -m sifu.cli stop`
Expected: "Sifu stopped." followed by pattern detection, SOP compilation, and coach launch

- [ ] **Step 5: Commit final state**

```bash
git add -A
git commit -m "SifuBar native capture engine — complete migration from Python daemon"
```
