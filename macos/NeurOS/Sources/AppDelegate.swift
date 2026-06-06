import AppKit

@MainActor
@main
final class AppDelegate: NSObject, NSApplicationDelegate {
    private var statusItemController: StatusItemController?
    private var panelController: CommandPanelController?
    private var hotKeyController: HotKeyController?

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.accessory)

        let panelController = CommandPanelController()
        self.panelController = panelController

        statusItemController = StatusItemController(panelController: panelController)
        hotKeyController = HotKeyController {
            panelController.toggle()
        }
        hotKeyController?.register()
    }

    func applicationWillTerminate(_ notification: Notification) {
        hotKeyController?.unregister()
    }
}
