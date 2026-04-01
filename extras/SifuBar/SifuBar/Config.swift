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
