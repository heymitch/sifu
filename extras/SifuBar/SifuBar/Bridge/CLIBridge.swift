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
