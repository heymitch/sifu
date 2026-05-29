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

    // MARK: - Browser URL

    static let browserApps: Set<String> = ["Google Chrome", "Safari", "Arc", "Microsoft Edge", "Brave Browser"]

    /// Chromium browsers don't expose AXURL — their URL comes via AppleScript.
    private static let chromiumApps: Set<String> = ["Google Chrome", "Brave Browser", "Microsoft Edge", "Arc"]

    /// Active-tab URL, cached. Refreshed only on app/window switch and poll —
    /// NOT per event — because the AppleScript path costs ~10-50ms and resolving
    /// it on every click would back up the capture queue.
    private var cachedURL: String?
    private var cachedURLApp: String?

    /// Cached browser URL for the per-event path. Returns nil for non-browsers,
    /// or when the cache belongs to a different app than the one asked about.
    func currentURL(for appName: String?) -> String? {
        guard let appName = appName, Self.browserApps.contains(appName) else { return nil }
        return appName == cachedURLApp ? cachedURL : nil
    }

    /// Resolve the active tab URL: AXURL first (Safari/WebKit), then AppleScript
    /// for Chromium browsers (Chrome/Brave/Edge/Arc) which don't expose AXURL.
    static func resolveBrowserURL(appName: String) -> String? {
        if let app = NSWorkspace.shared.frontmostApplication {
            let axApp = AXUIElementCreateApplication(app.processIdentifier)
            var winRef: CFTypeRef?
            AXUIElementCopyAttributeValue(axApp, kAXFocusedWindowAttribute as CFString, &winRef)
            if let winRaw = winRef, CFGetTypeID(winRaw) == AXUIElementGetTypeID() {
                let win = winRaw as! AXUIElement
                var urlRef: CFTypeRef?
                if AXUIElementCopyAttributeValue(win, "AXURL" as CFString, &urlRef) == .success,
                   let u = urlRef as? NSURL {
                    return u.absoluteString
                }
            }
        }
        return chromiumApps.contains(appName) ? urlViaAppleScript(appName: appName) : nil
    }

    /// Active-tab URL via AppleScript. Chromium browsers share Chrome's
    /// scripting dictionary. Returns nil (degrades gracefully) until the user
    /// grants Automation permission for SifuBar → the browser.
    private static func urlViaAppleScript(appName: String) -> String? {
        let source = "tell application \"\(appName)\" to get URL of active tab of window 1"
        guard let script = NSAppleScript(source: source) else { return nil }
        var error: NSDictionary?
        let result = script.executeAndReturnError(&error)
        if error != nil { return nil }
        let url = result.stringValue
        return (url?.isEmpty == false) ? url : nil
    }

    /// Recompute the cached URL for the current app. Cheap for non-browsers.
    private func refreshURL() {
        guard let app = currentApp, Self.browserApps.contains(app) else {
            cachedURL = nil
            cachedURLApp = nil
            return
        }
        cachedURL = Self.resolveBrowserURL(appName: app)
        cachedURLApp = app
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
        refreshURL()  // new frontmost app may be a browser — refresh cached URL

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
            refreshURL()  // title change usually means navigation — refresh URL
            onSwitch?("window_switch", currentApp, title, desc)
        } else if let title = title {
            currentWindow = title
        }
    }
}
