import SwiftUI

@main
struct SifuBarApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var appDelegate

    var body: some Scene {
        // No main window — menu bar only
        Settings { EmptyView() }
    }
}

class AppDelegate: NSObject, NSApplicationDelegate {
    var statusItem: NSStatusItem?
    var timer: Timer?

    func applicationDidFinishLaunching(_ notification: Notification) {
        // Hide dock icon — menu bar only app
        NSApp.setActivationPolicy(.accessory)

        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        updateMenu()

        // Poll state file every 5 seconds
        timer = Timer.scheduledTimer(withTimeInterval: 5.0, repeats: true) { [weak self] _ in
            self?.updateMenu()
        }
    }

    func updateMenu() {
        guard let statusItem = statusItem else { return }

        let state = readState()
        let isRunning = pidIsAlive(state["pid"] as? Int)
        let status = state["status"] as? String ?? "stopped"

        // Menu bar title
        if isRunning {
            if status == "paused" {
                statusItem.button?.title = "⏸ Sifu"
            } else {
                statusItem.button?.title = "🔴 Sifu"
            }
        } else {
            statusItem.button?.title = "⚪ Sifu"
        }

        // Build dropdown menu
        let menu = NSMenu()

        if isRunning {
            let events = state["events"] as? Int ?? 0
            let sessionId = state["session_id"] as? String ?? "—"

            if status == "paused" {
                menu.addItem(NSMenuItem(title: "Paused — \(events) events", action: nil, keyEquivalent: ""))
            } else {
                menu.addItem(NSMenuItem(title: "Recording — \(events) events", action: nil, keyEquivalent: ""))
            }

            let sessionItem = NSMenuItem(title: sessionId, action: nil, keyEquivalent: "")
            sessionItem.isEnabled = false
            menu.addItem(sessionItem)

            if let startTime = state["start_time"] as? String {
                let sinceItem = NSMenuItem(title: "Since \(startTime)", action: nil, keyEquivalent: "")
                sinceItem.isEnabled = false
                menu.addItem(sinceItem)
            }

            menu.addItem(NSMenuItem.separator())

            menu.addItem(NSMenuItem(title: "⏹ Stop (+ analyze)", action: #selector(stopSifu), keyEquivalent: ""))
            if status == "paused" {
                menu.addItem(NSMenuItem(title: "▶ Resume", action: #selector(resumeSifu), keyEquivalent: ""))
            } else {
                menu.addItem(NSMenuItem(title: "⏸ Pause", action: #selector(pauseSifu), keyEquivalent: ""))
            }
            menu.addItem(NSMenuItem(title: "🔒 Sensitive (purge 5m)", action: #selector(sensitiveSifu), keyEquivalent: ""))
        } else {
            menu.addItem(NSMenuItem(title: "Not recording", action: nil, keyEquivalent: ""))
            menu.addItem(NSMenuItem.separator())
            menu.addItem(NSMenuItem(title: "▶ Start Recording", action: #selector(startSifu), keyEquivalent: ""))
        }

        menu.addItem(NSMenuItem.separator())

        // Quick actions
        menu.addItem(NSMenuItem(title: "📋 Compile SOPs", action: #selector(compileSifu), keyEquivalent: ""))
        menu.addItem(NSMenuItem(title: "🎯 Coach Report", action: #selector(coachSifu), keyEquivalent: ""))
        menu.addItem(NSMenuItem(title: "📊 Show Patterns", action: #selector(patternsSifu), keyEquivalent: ""))
        menu.addItem(NSMenuItem(title: "📝 Show Log", action: #selector(logSifu), keyEquivalent: ""))

        menu.addItem(NSMenuItem.separator())
        menu.addItem(NSMenuItem(title: "⚙️ Config", action: #selector(configSifu), keyEquivalent: ""))
        menu.addItem(NSMenuItem(title: "📂 Open Data", action: #selector(openData), keyEquivalent: ""))
        menu.addItem(NSMenuItem.separator())
        menu.addItem(NSMenuItem(title: "Quit SifuBar", action: #selector(quitApp), keyEquivalent: "q"))

        // Set targets
        for item in menu.items {
            item.target = self
        }

        statusItem.menu = menu
    }

    // ── State reading ──────────────────────────────────

    func readState() -> [String: Any] {
        let statePath = NSHomeDirectory() + "/.sifu/daemon.state"
        guard let data = try? Data(contentsOf: URL(fileURLWithPath: statePath)),
              let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any]
        else { return [:] }
        return json
    }

    func pidIsAlive(_ pid: Int?) -> Bool {
        guard let pid = pid, pid > 0 else { return false }
        return kill(Int32(pid), 0) == 0
    }

    // Also check PID file directly (state file may not have pid)
    func isDaemonRunning() -> Bool {
        let pidPath = NSHomeDirectory() + "/.sifu/daemon.pid"
        guard let pidStr = try? String(contentsOfFile: pidPath).trimmingCharacters(in: .whitespacesAndNewlines),
              let pid = Int(pidStr)
        else { return false }
        return kill(Int32(pid), 0) == 0
    }

    // ── Actions ────────────────────────────────────────

    @objc func startSifu() { runSifuInTerminal("start") }

    @objc func stopSifu() { runSifuInTerminal("stop") }

    @objc func pauseSifu() { runSifuSilent("pause") }

    @objc func resumeSifu() { runSifuSilent("resume") }

    @objc func sensitiveSifu() { runSifuSilent("sensitive") }

    @objc func compileSifu() { runSifuInTerminal("compile") }

    @objc func coachSifu() { runSifuInTerminal("coach --today") }

    @objc func patternsSifu() { runSifuInTerminal("patterns --today") }

    @objc func logSifu() { runSifuInTerminal("log --last 1h") }

    @objc func configSifu() { runSifuInTerminal("config") }

    @objc func openData() {
        NSWorkspace.shared.open(URL(fileURLWithPath: NSHomeDirectory() + "/.sifu"))
    }

    @objc func quitApp() {
        NSApp.terminate(nil)
    }

    // ── Helpers ────────────────────────────────────────

    func runSifuSilent(_ subcommand: String) {
        DispatchQueue.global().async {
            let process = Process()
            process.executableURL = URL(fileURLWithPath: "/usr/bin/env")
            process.arguments = ["sifu"] + subcommand.split(separator: " ").map(String.init)
            try? process.run()
            process.waitUntilExit()
            DispatchQueue.main.async { self.updateMenu() }
        }
    }

    func runSifuInTerminal(_ subcommand: String) {
        let script = """
        tell application "Terminal"
            activate
            do script "sifu \(subcommand)"
        end tell
        """
        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/usr/bin/osascript")
        process.arguments = ["-e", script]
        try? process.run()
    }
}
