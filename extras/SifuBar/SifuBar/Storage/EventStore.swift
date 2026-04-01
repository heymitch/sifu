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
