import Foundation

final class TextAggregator {
    private var buffer: [Character] = []
    private var flushTimer: Timer?
    private let lock = NSLock()
    private let flushInterval: TimeInterval = 2.0

    /// Called when the buffer is flushed. Parameters: (text, isEnterPressed)
    var onFlush: ((String, Bool) -> Void)?

    func accumulate(_ char: Character) {
        lock.lock()
        buffer.append(char)
        lock.unlock()
        resetFlushTimer()
    }

    func handleBackspace() {
        lock.lock()
        if !buffer.isEmpty {
            buffer.removeLast()
        }
        lock.unlock()
    }

    func handleEnter() {
        cancelFlushTimer()
        flush(enterPressed: true)
    }

    /// Force flush on app switch or stop.
    func forceFlush() {
        cancelFlushTimer()
        flush(enterPressed: false)
    }

    func clear() {
        lock.lock()
        buffer.removeAll()
        lock.unlock()
        cancelFlushTimer()
    }

    // MARK: - Timer

    private func resetFlushTimer() {
        cancelFlushTimer()
        DispatchQueue.main.async { [weak self] in
            guard let self = self else { return }
            self.flushTimer = Timer.scheduledTimer(withTimeInterval: self.flushInterval, repeats: false) { [weak self] _ in
                self?.flush(enterPressed: false)
            }
        }
    }

    private func cancelFlushTimer() {
        DispatchQueue.main.async { [weak self] in
            self?.flushTimer?.invalidate()
            self?.flushTimer = nil
        }
    }

    // MARK: - Flush

    private func flush(enterPressed: Bool) {
        lock.lock()
        guard !buffer.isEmpty else {
            lock.unlock()
            return
        }
        let text = String(buffer)
        buffer.removeAll()
        lock.unlock()

        onFlush?(text, enterPressed)
    }
}
