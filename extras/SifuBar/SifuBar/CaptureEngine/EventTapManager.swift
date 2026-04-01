import ApplicationServices
import AppKit
import Foundation

// MARK: - Keycode table (matches data/keycodes.json)

private let keycodeTable: [UInt16: String] = [
    0: "a", 1: "s", 2: "d", 3: "f", 4: "h", 5: "g",
    6: "z", 7: "x", 8: "c", 9: "v", 11: "b", 12: "q",
    13: "w", 14: "e", 15: "r", 16: "y", 17: "t",
    18: "1", 19: "2", 20: "3", 21: "4", 22: "6", 23: "5",
    24: "=", 25: "9", 26: "7", 27: "-", 28: "8", 29: "0",
    30: "]", 31: "o", 32: "u", 33: "[", 34: "i", 35: "p",
    36: "Return", 37: "l", 38: "j", 39: "'", 40: "k",
    41: ";", 42: "\\", 43: ",", 44: "/", 45: "n", 46: "m",
    47: ".", 48: "Tab", 49: "Space", 50: "`", 51: "Delete",
    53: "Escape",
    55: "Command", 56: "Shift", 57: "CapsLock",
    58: "Option", 59: "Control",
    60: "RightShift", 61: "RightOption", 62: "RightControl",
    63: "Function",
    96: "F5", 97: "F6", 98: "F7", 99: "F3", 100: "F8",
    101: "F9", 103: "F11", 105: "F13", 107: "F14",
    109: "F10", 111: "F12", 113: "F15",
    115: "Home", 116: "PageUp", 117: "ForwardDelete", 118: "F4",
    119: "End", 120: "F2", 121: "PageDown", 122: "F1",
    123: "LeftArrow", 124: "RightArrow", 125: "DownArrow", 126: "UpArrow",
]

private let shiftMap: [Character: Character] = [
    "1": "!", "2": "@", "3": "#", "4": "$", "5": "%",
    "6": "^", "7": "&", "8": "*", "9": "(", "0": ")",
    "-": "_", "=": "+", "[": "{", "]": "}", "\\": "|",
    ";": ":", "'": "\"", ",": "<", ".": ">", "/": "?", "`": "~",
]

private let nonPrintableKeys: Set<String> = [
    "Return", "Tab", "Delete", "ForwardDelete", "Escape",
    "Command", "Shift", "CapsLock", "Option", "Control",
    "RightShift", "RightOption", "RightControl", "Function",
    "LeftArrow", "RightArrow", "UpArrow", "DownArrow",
    "Home", "End", "PageUp", "PageDown",
    "F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8",
    "F9", "F10", "F11", "F12", "F13", "F14", "F15",
]

private let modifierKeycodes: Set<UInt16> = [55, 56, 57, 58, 59, 60, 61, 62, 63]
private let keycodeReturn: UInt16 = 36
private let keycodeDelete: UInt16 = 51

/// Callback for captured events
struct CapturedEvent {
    let type: String          // "click", "right_click", "shortcut", "text_input", "command"
    let app: String?
    let window: String?
    let description: String?
    let element: String?
    let positionX: Int?
    let positionY: Int?
    let textContent: String?
    let shortcut: String?
}

final class EventTapManager {
    fileprivate var eventTap: CFMachPort?
    private var runLoopSource: CFRunLoopSource?
    private let textAggregator = TextAggregator()
    private var config: SifuConfig
    var paused: Bool = false

    /// Called for each captured event
    var onEvent: ((CapturedEvent) -> Void)?

    init(config: SifuConfig) {
        self.config = config

        textAggregator.onFlush = { [weak self] text, enterPressed in
            self?.handleTextFlush(text: text, enterPressed: enterPressed)
        }
    }

    // MARK: - Start / Stop

    func start() -> Bool {
        let mask: CGEventMask =
            (1 << CGEventType.leftMouseDown.rawValue) |
            (1 << CGEventType.rightMouseDown.rawValue) |
            (1 << CGEventType.keyDown.rawValue)

        // We need to use a C callback that bridges to our instance
        let refcon = Unmanaged.passUnretained(self).toOpaque()

        eventTap = CGEvent.tapCreate(
            tap: .cgSessionEventTap,
            place: .headInsertEventTap,
            options: .listenOnly,
            eventsOfInterest: mask,
            callback: eventTapCallback,
            userInfo: refcon
        )

        guard let tap = eventTap else {
            return false
        }

        runLoopSource = CFMachPortCreateRunLoopSource(kCFAllocatorDefault, tap, 0)
        CFRunLoopAddSource(CFRunLoopGetCurrent(), runLoopSource, .commonModes)
        CGEvent.tapEnable(tap: tap, enable: true)
        return true
    }

    func stop() {
        textAggregator.forceFlush()
        if let tap = eventTap {
            CGEvent.tapEnable(tap: tap, enable: false)
            eventTap = nil
        }
    }

    /// Flush text buffer (call on app switch)
    func flushText() {
        textAggregator.forceFlush()
    }

    // MARK: - Event handling

    fileprivate func handleCGEvent(type: CGEventType, event: CGEvent) {
        guard !paused else { return }

        let appName = Self.getFrontmostApp()
        if let app = appName, config.ignoreApps.contains(app) { return }

        switch type {
        case .leftMouseDown:
            handleMouseClick(event: event, isRight: false, app: appName)
        case .rightMouseDown:
            handleMouseClick(event: event, isRight: true, app: appName)
        case .keyDown:
            handleKeyDown(event: event, app: appName)
        default:
            break
        }
    }

    // MARK: - Mouse

    private func handleMouseClick(event: CGEvent, isRight: Bool, app: String?) {
        let loc = event.location
        let x = Int(loc.x)
        let y = Int(loc.y)

        let window = Self.getWindowTitle()
        let element = Self.getElementAtPosition(x: loc.x, y: loc.y)

        let desc: String
        if let el = element {
            desc = "Clicked '\(el)' in \(app ?? "unknown")"
        } else {
            desc = "Clicked at (\(x), \(y)) in \(app ?? "unknown")"
        }

        let captured = CapturedEvent(
            type: isRight ? "right_click" : "click",
            app: app,
            window: window,
            description: desc,
            element: element,
            positionX: x,
            positionY: y,
            textContent: nil,
            shortcut: nil
        )
        onEvent?(captured)
    }

    // MARK: - Keyboard

    private func handleKeyDown(event: CGEvent, app: String?) {
        let keycode = UInt16(event.getIntegerValueField(.keyboardEventKeycode))
        let flags = event.flags

        // Skip bare modifier keys
        if modifierKeycodes.contains(keycode) { return }

        let keyName = keycodeTable[keycode] ?? "key\(keycode)"

        // Shortcut: Cmd, Ctrl, or Opt held
        let hasCmdCtrlOpt = !flags.intersection([.maskCommand, .maskAlternate, .maskControl]).isEmpty

        if hasCmdCtrlOpt {
            handleShortcut(keyName: keyName, flags: flags, app: app)
            return
        }

        // Skip password fields for plain keystrokes
        if Self.isPasswordField() { return }

        // Enter key
        if keycode == keycodeReturn {
            textAggregator.handleEnter()
            return
        }

        // Delete key
        if keycode == keycodeDelete {
            textAggregator.handleBackspace()
            return
        }

        // Map keycode to character
        if let char = keycodeToChar(keycode: keycode, shiftHeld: flags.contains(.maskShift)) {
            textAggregator.accumulate(char)
        }
    }

    private func handleShortcut(keyName: String, flags: CGEventFlags, app: String?) {
        if Self.isPasswordField() { return }

        var parts: [String] = []
        if flags.contains(.maskCommand) { parts.append("Cmd") }
        if flags.contains(.maskShift) { parts.append("Shift") }
        if flags.contains(.maskAlternate) { parts.append("Opt") }
        if flags.contains(.maskControl) { parts.append("Ctrl") }

        guard !parts.isEmpty else { return }

        let shortcutStr = parts.joined(separator: "+") + "+" + keyName
        let window = Self.getWindowTitle()

        let captured = CapturedEvent(
            type: "shortcut",
            app: app,
            window: window,
            description: "Shortcut: \(shortcutStr)",
            element: nil,
            positionX: nil,
            positionY: nil,
            textContent: nil,
            shortcut: shortcutStr
        )
        onEvent?(captured)
    }

    private func handleTextFlush(text: String, enterPressed: Bool) {
        let app = Self.getFrontmostApp()
        if let a = app, config.ignoreApps.contains(a) { return }
        if paused { return }

        let isTerminal = app.map { config.terminalApps.contains($0) } ?? false
        let type: String
        let desc: String

        if enterPressed && isTerminal {
            type = "command"
            desc = "Command: \(text)"
        } else {
            type = "text_input"
            let truncated = text.count > 60 ? String(text.prefix(60)) + "\u{2026}" : text
            desc = "Typed: \(truncated)"
        }

        let window = Self.getWindowTitle()
        let captured = CapturedEvent(
            type: type,
            app: app,
            window: window,
            description: desc,
            element: nil,
            positionX: nil,
            positionY: nil,
            textContent: text,
            shortcut: nil
        )
        onEvent?(captured)
    }

    // MARK: - Keycode mapping

    private func keycodeToChar(keycode: UInt16, shiftHeld: Bool) -> Character? {
        guard let name = keycodeTable[keycode] else { return nil }
        if nonPrintableKeys.contains(name) { return nil }
        if name == "Space" { return " " }

        guard name.count == 1, let base = name.first else { return nil }

        if shiftHeld {
            return shiftMap[base] ?? Character(base.uppercased())
        }
        return base
    }

    // MARK: - Accessibility helpers

    static func getFrontmostApp() -> String? {
        NSWorkspace.shared.frontmostApplication?.localizedName
    }

    static func getWindowTitle() -> String? {
        guard let app = NSWorkspace.shared.frontmostApplication else { return nil }
        let axApp = AXUIElementCreateApplication(app.processIdentifier)
        var value: AnyObject?
        guard AXUIElementCopyAttributeValue(axApp, "AXFocusedWindow" as CFString, &value) == .success,
              let window = value else { return nil }
        var title: AnyObject?
        guard AXUIElementCopyAttributeValue(window as! AXUIElement, "AXTitle" as CFString, &title) == .success,
              let titleStr = title as? String else { return nil }
        return titleStr
    }

    static func getElementAtPosition(x: CGFloat, y: CGFloat) -> String? {
        let systemWide = AXUIElementCreateSystemWide()
        var element: AXUIElement?
        guard AXUIElementCopyElementAtPosition(systemWide, Float(x), Float(y), &element) == .success,
              let el = element else { return nil }

        // Skip password fields
        var role: AnyObject?
        if AXUIElementCopyAttributeValue(el, "AXRole" as CFString, &role) == .success,
           let roleStr = role as? String, roleStr == "AXSecureTextField" {
            return nil
        }

        // Prefer AXDescription
        var desc: AnyObject?
        if AXUIElementCopyAttributeValue(el, "AXDescription" as CFString, &desc) == .success,
           let descStr = desc as? String, !descStr.isEmpty {
            return descStr
        }

        // Fall back to AXTitle
        var title: AnyObject?
        if AXUIElementCopyAttributeValue(el, "AXTitle" as CFString, &title) == .success,
           let titleStr = title as? String, !titleStr.isEmpty {
            return titleStr
        }

        return nil
    }

    static func isPasswordField() -> Bool {
        guard let app = NSWorkspace.shared.frontmostApplication else { return false }
        let axApp = AXUIElementCreateApplication(app.processIdentifier)
        var focused: AnyObject?
        guard AXUIElementCopyAttributeValue(axApp, "AXFocusedUIElement" as CFString, &focused) == .success,
              let el = focused else { return false }
        var role: AnyObject?
        if AXUIElementCopyAttributeValue(el as! AXUIElement, "AXRole" as CFString, &role) == .success,
           let roleStr = role as? String, roleStr == "AXSecureTextField" {
            return true
        }
        return false
    }
}

// MARK: - C callback bridge

private func eventTapCallback(
    proxy: CGEventTapProxy,
    type: CGEventType,
    event: CGEvent,
    userInfo: UnsafeMutableRawPointer?
) -> Unmanaged<CGEvent>? {
    guard let userInfo = userInfo else { return Unmanaged.passUnretained(event) }
    let manager = Unmanaged<EventTapManager>.fromOpaque(userInfo).takeUnretainedValue()

    // Re-enable tap if it was disabled by the system (rate limiting)
    if type == .tapDisabledByTimeout || type == .tapDisabledByUserInput {
        if let tap = manager.eventTap {
            CGEvent.tapEnable(tap: tap, enable: true)
        }
        return Unmanaged.passUnretained(event)
    }

    manager.handleCGEvent(type: type, event: event)
    return Unmanaged.passUnretained(event)
}
