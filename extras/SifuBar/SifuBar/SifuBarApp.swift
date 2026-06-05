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
    private var workingLayer: String? = nil  // nil = not working, or "compile", "coach", "classify", "patterns"

    func applicationDidFinishLaunching(_ notification: Notification) {
        // LSUIElement=true in Info.plist handles hiding from Dock.
        // setActivationPolicy(.accessory) can conflict on Sequoia — skip it.

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

        // Silently check permissions — start capture if granted, show menu hint if not.
        // Only show permission dialogs when user explicitly clicks the menu item.
        if permissionManager.allGranted {
            startCapture()
        }
        // If not granted, menu shows the permissions hint — no popup on launch.
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

            let frame = EventTapManager.getFrameSnapshot()
            let url = self.appTracker.currentURL(for: captured.app)

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
                sessionId: sessionId,
                displayId: frame?.displayID,
                displayBounds: frame?.displayBounds,
                windowRect: frame?.windowRect,
                backingScale: frame?.backingScale,
                url: url
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

            let frame = EventTapManager.getFrameSnapshot()
            let url = self.appTracker.currentURL(for: app)

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
                sessionId: sessionId,
                displayId: frame?.displayID,
                displayBounds: frame?.displayBounds,
                windowRect: frame?.windowRect,
                backingScale: frame?.backingScale,
                url: url
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

        // Menu bar title — icon matches active layer
        if let layer = workingLayer {
            let icon: String
            switch layer {
            case "compile":  icon = "\u{25C8}"  // ◈ Compiler
            case "coach":    icon = "\u{25C7}"  // ◇ Coach
            case "classify": icon = "\u{2B21}"  // ⬡ Classifier
            case "patterns": icon = "\u{25CE}"  // ◎ Pattern Detection
            default:         icon = "\u{25C8}"  // ◈ default working
            }
            statusItem.button?.title = "\(icon) Sifu"
        } else if isCapturing {
            statusItem.button?.title = isPaused ? "\u{25CE} Sifu" : "\u{25C9} Sifu"  // ◎ paused / ◉ recording
        } else {
            statusItem.button?.title = "\u{25C7} Sifu"  // ◇ idle
        }

        let menu = NSMenu()

        if isCapturing {
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

            let stopItem = NSMenuItem(title: "\u{23F9} Stop + Analyze", action: #selector(stopAction), keyEquivalent: "")
            stopItem.target = self
            menu.addItem(stopItem)

            let cancelItem = NSMenuItem(title: "\u{1F5D1} Cancel Recording", action: #selector(cancelAction), keyEquivalent: "")
            cancelItem.target = self
            menu.addItem(cancelItem)

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

            if !permissionManager.allGranted {
                menu.addItem(NSMenuItem.separator())
                let permItem = NSMenuItem(title: "\u{26A0}\u{FE0F} Permissions needed to record", action: #selector(requestPermissions), keyEquivalent: "")
                permItem.target = self
                menu.addItem(permItem)
            }
        }

        menu.addItem(NSMenuItem.separator())

        // Copy Last Workflow — gated while a compile is still analyzing the
        // latest session, so it can't hand back a stale (previous) unit.
        let analyzing = (workingLayer != nil)
        let copyItem = NSMenuItem(
            title: analyzing ? "\u{23F3} Analyzing latest\u{2026}" : "\u{1F4E4} Copy Last Workflow",
            action: analyzing ? nil : #selector(copyLastSifu),
            keyEquivalent: ""
        )
        copyItem.target = self
        menu.addItem(copyItem)

        // Quick actions
        for (title, sel) in [
            ("\u{1F4CB} Compile SOPs", #selector(compileSifu)),
            ("\u{1F310} Open Dashboard", #selector(openDashboard)),
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

        // Auto-open the dashboard to the just-compiled workflow (copy always happens regardless)
        let autoOpenTitle = autoOpenViewer
            ? "\u{2705} Open Dashboard on Compile"
            : "Open Dashboard on Compile"
        let autoOpenItem = NSMenuItem(title: autoOpenTitle, action: #selector(toggleAutoOpenViewer), keyEquivalent: "")
        autoOpenItem.target = self
        menu.addItem(autoOpenItem)

        let configItem = NSMenuItem(title: "\u{2699}\u{FE0F} Config", action: #selector(configSifu), keyEquivalent: "")
        configItem.target = self
        menu.addItem(configItem)

        let openDataItem = NSMenuItem(title: "\u{1F4C2} Show Location in Finder", action: #selector(openData), keyEquivalent: "")
        openDataItem.target = self
        menu.addItem(openDataItem)

        menu.addItem(NSMenuItem.separator())

        let restartItem = NSMenuItem(title: "\u{1F504} Restart", action: #selector(restartApp), keyEquivalent: "r")
        restartItem.target = self
        menu.addItem(restartItem)

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

    @objc private func startAction() {
        if !permissionManager.allGranted {
            permissionManager.checkAndRequest { [weak self] in
                DispatchQueue.main.async {
                    self?.startCapture()
                }
            }
        } else {
            startCapture()
        }
    }
    @objc private func stopAction() {
        stopCapture()
        runSifuWithLayer("compile --today", layer: "compile")
    }
    @objc private func cancelAction() {
        // Delete this session's events and screenshots, then stop
        let sessionId = sessionManager.sessionId
        stopCapture()
        if let sid = sessionId {
            let deletedPaths = eventStore.purgeSession(sid)
            for path in deletedPaths {
                try? FileManager.default.removeItem(atPath: path)
            }
        }
    }
    @objc private func pauseAction() { pauseCapture() }
    @objc private func resumeAction() { resumeCapture() }
    @objc private func sensitiveAction() { handleSensitive() }

    @objc private func compileSifu() { runSifuWithLayer("compile", layer: "compile") }
    @objc private func coachSifu() { runSifuWithLayer("coach --today", layer: "coach") }
    @objc private func patternsSifu() { runSifuWithLayer("patterns --today", layer: "patterns") }
    @objc private func logSifu() { runSifu("log --last 1h") }
    @objc private func configSifu() { runSifu("config") }

    @objc private func copyLastSifu() {
        // `sifu copy-last` writes the most recent workflow + skill-building
        // instructions to the clipboard; flash the menu bar to confirm.
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            self?.runSifuSync("copy-last")
            DispatchQueue.main.async { self?.flashStatus("\u{2705} Copied") }
        }
    }

    private func flashStatus(_ text: String) {
        guard let button = statusItem?.button else { return }
        button.title = text
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.6) { [weak self] in
            self?.updateMenu()  // restores the normal status glyph
        }
    }

    private func runSifuWithLayer(_ subcommand: String, layer: String) {
        workingLayer = layer
        updateMenu()
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            self?.runSifuSync(subcommand)
            if layer == "compile" {
                self?.handleCompileFinished()
            }
            DispatchQueue.main.async {
                self?.workingLayer = nil
                self?.updateMenu()
            }
        }
    }

    /// After a compile finishes: ALWAYS copy the fresh workflow to the clipboard
    /// and notify; if the user opted in, also open the dashboard to it. Runs on a
    /// background thread (called from runSifuWithLayer's worker).
    private func handleCompileFinished() {
        runSifuSync("copy-last")  // workflow + skill-building instructions -> clipboard
        notify("Workflow copied",
               "The compiled workflow is on your clipboard \u{2014} paste it into your agent.")
        if autoOpenViewer {
            runSifu("open --last")  // starts the UI server if needed, opens /workflow/{id}
        }
    }

    /// Bar-only UI preference (does not touch the engine's config.json).
    private var autoOpenViewer: Bool {
        get { UserDefaults.standard.bool(forKey: "autoOpenViewerOnCompile") }
        set { UserDefaults.standard.set(newValue, forKey: "autoOpenViewerOnCompile") }
    }

    @objc private func openDashboard() { runSifu("open") }  // list view

    @objc private func toggleAutoOpenViewer() {
        autoOpenViewer.toggle()
        updateMenu()
    }

    /// Notification Center banner via osascript — no entitlement / authorization
    /// prompt required, matches the app's shell-out pattern.
    private func notify(_ title: String, _ body: String) {
        let task = Process()
        task.executableURL = URL(fileURLWithPath: "/usr/bin/osascript")
        task.arguments = ["-e", "display notification \"\(body)\" with title \"\(title)\""]
        try? task.run()
    }

    @objc private func toggleLoginItem() { loginItemManager.toggle(); updateMenu() }

    @objc private func openData() {
        let sifuDir = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent(".sifu")
        NSWorkspace.shared.open(sifuDir)
    }

    @objc private func restartApp() {
        // Relaunch self to pick up newly granted permissions
        let executableURL = Bundle.main.executableURL!
        let task = Process()
        task.executableURL = URL(fileURLWithPath: "/usr/bin/open")
        task.arguments = ["-a", Bundle.main.bundlePath]
        try? task.run()
        NSApp.terminate(nil)
    }

    @objc private func quitApp() {
        stopCapture()
        NSApp.terminate(nil)
    }

    // MARK: - Sifu CLI helper

    private func runSifuSync(_ subcommand: String) {
        // Synchronous version — blocks until sifu finishes. Call from background thread.
        let proc = _makeSifuProcess(subcommand)
        guard let proc = proc else { return }
        proc.waitUntilExit()
    }

    private func runSifu(_ subcommand: String) {
        // Fire and forget
        guard let proc = _makeSifuProcess(subcommand) else { return }
        _ = proc  // process runs detached
    }

    private func _makeSifuProcess(_ subcommand: String) -> Process? {
        // Find sifu on common paths (pip install -e puts it in user or system bin)
        let searchPaths = [
            "/opt/homebrew/bin/sifu",
            "/usr/local/bin/sifu",
            "/Library/Frameworks/Python.framework/Versions/Current/bin/sifu",
            FileManager.default.homeDirectoryForCurrentUser
                .appendingPathComponent(".local/bin/sifu").path,
            FileManager.default.homeDirectoryForCurrentUser
                .appendingPathComponent("sifu/venv/bin/sifu").path,
        ]

        var sifuPath: String?
        for path in searchPaths {
            if FileManager.default.isExecutableFile(atPath: path) {
                sifuPath = path
                break
            }
        }

        // Fallback: try PATH via /usr/bin/env
        let execPath = sifuPath ?? "/usr/bin/env"
        var args = subcommand.split(separator: " ").map(String.init)
        if sifuPath == nil {
            args.insert("sifu", at: 0)
        }

        let proc = Process()
        proc.executableURL = URL(fileURLWithPath: execPath)
        proc.arguments = args
        proc.environment = ProcessInfo.processInfo.environment

        // Log output to daemon.log
        let logPath = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent(".sifu/daemon.log")
        let logHandle = try? FileHandle(forWritingTo: logPath)
        logHandle?.seekToEndOfFile()
        proc.standardOutput = logHandle ?? FileHandle.nullDevice
        proc.standardError = logHandle ?? FileHandle.nullDevice

        try? proc.run()
        return proc
    }
}
