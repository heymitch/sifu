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
