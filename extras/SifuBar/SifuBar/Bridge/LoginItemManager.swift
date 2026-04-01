import ServiceManagement

final class LoginItemManager {
    var isEnabled: Bool {
        SMAppService.mainApp.status == .enabled
    }

    func enable() {
        try? SMAppService.mainApp.register()
    }

    func disable() {
        try? SMAppService.mainApp.unregister()
    }

    func toggle() {
        if isEnabled {
            disable()
        } else {
            enable()
        }
    }
}
