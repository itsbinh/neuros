import SwiftUI

struct TranscriptMessage: Identifiable, Equatable {
    enum Role {
        case user
        case assistant
    }

    let id = UUID()
    let role: Role
    let text: String

    static func user(_ text: String) -> TranscriptMessage {
        TranscriptMessage(role: .user, text: text)
    }

    static func assistant(_ text: String) -> TranscriptMessage {
        TranscriptMessage(role: .assistant, text: text)
    }
}

struct CommandPanelView: View {
    let onSubmit: (String) -> Void
    let onDismiss: () -> Void

    @State private var query = ""
    @State private var selectedModel = "qwen35"
    @State private var messages: [TranscriptMessage] = []

    private let modelNames = ["qwen35", "qwen27-vision", "gemma-4-e2b"]

    var body: some View {
        VStack(spacing: 0) {
            TextEditor(text: $query)
                .font(.system(size: 16))
                .scrollContentBackground(.hidden)
                .frame(minHeight: 96)
                .padding(.horizontal, 14)
                .padding(.top, 14)
                .onSubmit {
                    submit()
                }

            if !messages.isEmpty {
                Divider()
                    .opacity(0.45)
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 12) {
                        ForEach(messages) { message in
                            TranscriptRow(message: message)
                        }
                    }
                    .padding(18)
                }
                .frame(maxHeight: 230)
            }

            Divider()
                .opacity(0.45)

            HStack(spacing: 8) {
                Picker("Model", selection: $selectedModel) {
                    ForEach(modelNames, id: \.self) { name in
                        Text(name).tag(name)
                    }
                }
                .pickerStyle(.menu)
                .labelsHidden()
                .frame(width: 150)

                Spacer()

                Button("Cancel", action: onDismiss)
                    .buttonStyle(.plain)
                    .foregroundStyle(.secondary)

                Button("Send", action: submit)
                    .keyboardShortcut(.return, modifiers: [])
                    .disabled(query.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
            }
            .font(.system(size: 13, weight: .medium))
            .padding(.horizontal, 14)
            .padding(.vertical, 10)
        }
        .background(.regularMaterial)
        .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
        .overlay {
            RoundedRectangle(cornerRadius: 16, style: .continuous)
                .stroke(.separator.opacity(0.45), lineWidth: 1)
        }
        .frame(width: 620)
    }

    private func submit() {
        let text = query.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return }
        messages.append(.user(text))
        messages.append(.assistant("Native shell ready. Agent streaming lands in Phase 2."))
        onSubmit(text)
        query = ""
    }
}

private struct TranscriptRow: View {
    let message: TranscriptMessage

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(message.role == .user ? "You" : "NeurOS")
                .font(.system(size: 11, weight: .semibold))
                .foregroundStyle(.secondary)
            Text(message.text)
                .font(.system(size: 14))
                .lineSpacing(3)
                .textSelection(.enabled)
        }
    }
}

#Preview {
    CommandPanelView(onSubmit: { _ in }, onDismiss: {})
        .padding()
}
