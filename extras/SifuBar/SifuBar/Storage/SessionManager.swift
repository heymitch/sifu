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
