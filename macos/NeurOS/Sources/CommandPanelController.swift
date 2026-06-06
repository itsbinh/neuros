import AppKit
import SwiftUI

@MainActor
final class CommandPanelController: NSObject, NSWindowDelegate {
    private lazy var panel: NSPanel = {
        let view = CommandPanelView(
            onSubmit: { [weak self] text in
                self?.appendAssistantStub(for: text)
            },
            onDismiss: { [weak self] in
                self?.hide()
            }
        )
        let hostingView = NSHostingView(rootView: view)
        let panel = NSPanel(
            contentRect: NSRect(x: 0, y: 0, width: 620, height: 420),
            styleMask: [.borderless, .nonactivatingPanel, .fullSizeContentView],
            backing: .buffered,
            defer: false
        )
        panel.contentView = hostingView
        panel.delegate = self
        panel.isFloatingPanel = true
        panel.level = .modalPanel
        panel.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]
        panel.isOpaque = false
        panel.backgroundColor = .clear
        panel.hasShadow = true
        panel.hidesOnDeactivate = false
        return panel
    }()

    private var messages: [TranscriptMessage] = []

    func toggle() {
        panel.isVisible ? hide() : show()
    }

    func show() {
        centerPanel()
        panel.orderFrontRegardless()
        NSApp.activate(ignoringOtherApps: true)
    }

    func hide() {
        panel.orderOut(nil)
    }

    func windowDidResignKey(_ notification: Notification) {
        hide()
    }

    private func centerPanel() {
        guard let screenFrame = NSScreen.main?.visibleFrame else { return }
        let size = panel.frame.size
        let origin = NSPoint(
            x: screenFrame.midX - size.width / 2,
            y: screenFrame.midY - size.height / 2
        )
        panel.setFrameOrigin(origin)
    }

    private func appendAssistantStub(for text: String) {
        messages.append(.user(text))
        messages.append(.assistant("Native shell ready. Agent streaming lands in Phase 2."))
    }
}
