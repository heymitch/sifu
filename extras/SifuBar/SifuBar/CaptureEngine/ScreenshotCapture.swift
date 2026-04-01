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
