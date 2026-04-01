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
