import Foundation

@MainActor
final class HotKeyController {
    private let action: () -> Void

    init(action: @escaping () -> Void) {
        self.action = action
    }

    func register() {
        // Phase 1 placeholder. The native app shell builds and runs without
        // Hammerspoon; global hotkey registration lands once the app bundle and
        // permissions model are settled.
    }

    func unregister() {}
}
