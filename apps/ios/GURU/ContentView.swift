/**
 * GURU iOS Application - App Store Compliant
 *
 * STORE COMPLIANCE: App Store Review Guidelines
 * SECURITY: iOS App Sandbox, privacy nutrition labels
 * PRIVACY: No background mic usage, explicit permissions
 *
 * CRITICAL FEATURES:
 * - Face avatar only (optimized for mobile)
 * - Siri-style voice interaction with visual indicators
 * - API-only AI operation (NO local models)
 * - iOS Keychain for secure API key storage
 * - On-screen interaction only (no OS automation)
 *
 * HARD RESTRICTIONS ENFORCED:
 * - NO OS automation (App Store policy violation)
 * - NO file system access beyond sandbox
 * - NO background mic usage without indicator
 * - NO code download or execution
 *
 * ZERO TOLERANCE PRINCIPLES:
 * - App Privacy Nutrition Label compliance
 * - Purpose strings for every permission
 * - Strict API usage disclosure
 * - Professional assistant behavior
 */

import SwiftUI
import Speech
import AVFoundation
import Combine

struct ContentView: View {
    @StateObject private var viewModel = GuruViewModel()
    @State private var isShowingSetup = false
    
    var body: some View {
        NavigationView {
            VStack(spacing: 30) {
                // Status Header
                VStack {
                    Text("GURU")
                        .font(.largeTitle)
                        .fontWeight(.bold)
                        .foregroundColor(.primary)
                    
                    Text(viewModel.statusMessage)
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                        .multilineTextAlignment(.center)
                }
                .padding(.top)
                
                Spacer()
                
                // Avatar Face
                AvatarFaceView(emotion: viewModel.avatarEmotion,
                             isListening: viewModel.isListening,
                             isSpeaking: viewModel.isSpeaking,
                             audioLevel: viewModel.audioLevel)
                    .frame(width: 200, height: 200)
                
                Spacer()
                
                // Response Display
                if !viewModel.lastResponse.isEmpty {
                    ScrollView {
                        Text(viewModel.lastResponse)
                            .font(.body)
                            .padding()
                            .background(Color(.systemGray6))
                            .cornerRadius(12)
                    }
                    .frame(maxHeight: 120)
                    .padding(.horizontal)
                }
                
                Spacer()
                
                // Voice Control Button
                VStack(spacing: 16) {
                    Button(action: {
                        if viewModel.isListening {
                            viewModel.stopListening()
                        } else {
                            viewModel.startListening()
                        }
                    }) {
                        HStack {
                            Image(systemName: viewModel.isListening ? "mic.fill" : "mic")
                                .font(.title2)
                            Text(viewModel.isListening ? "Stop Listening" : "Tap to Speak")
                                .fontWeight(.medium)
                        }
                        .foregroundColor(.white)
                        .padding()
                        .frame(maxWidth: .infinity)
                        .background(viewModel.isListening ? Color.red : Color.blue)
                        .cornerRadius(12)
                    }
                    .disabled(!viewModel.isInitialized || viewModel.isSpeaking)
                    
                    // Privacy Indicator
                    if viewModel.isListening {
                        HStack {
                            Circle()
                                .fill(Color.red)
                                .frame(width: 8, height: 8)
                            Text("Microphone Active")
                                .font(.caption)
                                .foregroundColor(.red)
                        }
                    }
                }
                .padding(.horizontal)
                .padding(.bottom)
            }
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Settings") {
                        isShowingSetup = true
                    }
                }
            }
        }
        .onAppear {
            viewModel.initialize()
        }
        .sheet(isPresented: $isShowingSetup) {
            SetupView(viewModel: viewModel)
        }
        .alert("Error", isPresented: .constant(!viewModel.errorMessage.isEmpty)) {
            Button("OK") {
                viewModel.clearError()
            }
        } message: {
            Text(viewModel.errorMessage)
        }
    }
}

@MainActor
class GuruViewModel: ObservableObject {
    // Published properties for UI binding
    @Published var statusMessage = "Initializing GURU..."
    @Published var isInitialized = false
    @Published var isListening = false
    @Published var isSpeaking = false
    @Published var avatarEmotion: AvatarEmotion = .neutral
    @Published var audioLevel: Float = 0.0
    @Published var lastResponse = ""
    @Published var errorMessage = ""
    
    // Core components
    private let speechRecognizer = SFSpeechRecognizer()
    private let audioEngine = AVAudioEngine()
    private let synthesizer = AVSpeechSynthesizer()
    private var recognitionRequest: SFSpeechAudioBufferRecognitionRequest?
    private var recognitionTask: SFSpeechRecognitionTask?
    
    // API and security
    private let apiClient = GuruApiClient()
    private let credentialManager = IOSCredentialManager()
    
    // Cancellables for Combine
    private var cancellables = Set<AnyCancellable>()
    
    init() {
        setupSpeechSynthesizer()
    }
    
    func initialize() {
        Task {
            do {
                // Request speech recognition permission
                let speechPermission = await requestSpeechPermission()
                guard speechPermission else {
                    await updateStatus("Speech permission required")
                    return
                }
                
                // Request microphone permission
                let micPermission = await requestMicrophonePermission()
                guard micPermission else {
                    await updateStatus("Microphone permission required")
                    return
                }
                
                // Check API configuration
                let hasApiKeys = await credentialManager.hasConfiguredApis()
                if !hasApiKeys {
                    await updateStatus("API setup required - Tap Settings")
                } else {
                    await updateStatus("Ready - Tap to speak")
                    isInitialized = true
                    avatarEmotion = .ready
                }
                
                print("GURU iOS Application initialized successfully")
                
            } catch {
                await showError("Initialization failed: \(error.localizedDescription)")
            }
        }
    }
    
    private func requestSpeechPermission() async -> Bool {
        return await withCheckedContinuation { continuation in
            SFSpeechRecognizer.requestAuthorization { status in
                continuation.resume(returning: status == .authorized)
            }
        }
    }
    
    private func requestMicrophonePermission() async -> Bool {
        return await withCheckedContinuation { continuation in
            AVAudioSession.sharedInstance().requestRecordPermission { granted in
                continuation.resume(returning: granted)
            }
        }
    }
    
    func startListening() {
        guard !isListening && !isSpeaking else { return }
        
        Task {
            do {
                try await startSpeechRecognition()
                await MainActor.run {
                    isListening = true
                    avatarEmotion = .listening
                    statusMessage = "Listening... (tap to stop)"
                }
            } catch {
                await showError("Failed to start listening: \(error.localizedDescription)")
            }
        }
    }
    
    func stopListening() {
        guard isListening else { return }
        
        audioEngine.stop()
        recognitionRequest?.endAudio()
        
        isListening = false
        avatarEmotion = .thinking
        statusMessage = "Processing..."
    }
    
    private func startSpeechRecognition() async throws {
        // Cancel any existing task
        recognitionTask?.cancel()
        recognitionTask = nil
        
        // Configure audio session
        let audioSession = AVAudioSession.sharedInstance()
        try audioSession.setCategory(.record, mode: .measurement, options: .duckOthers)
        try audioSession.setActive(true, options: .notifyOthersOnDeactivation)
        
        // Create recognition request
        recognitionRequest = SFSpeechAudioBufferRecognitionRequest()
        guard let recognitionRequest = recognitionRequest else {
            throw GuruError.speechRecognitionFailed
        }
        
        recognitionRequest.shouldReportPartialResults = true
        
        // Configure audio engine
        let inputNode = audioEngine.inputNode
        let recordingFormat = inputNode.outputFormat(forBus: 0)
        
        inputNode.installTap(onBus: 0, bufferSize: 1024, format: recordingFormat) { buffer, _ in
            recognitionRequest.append(buffer)
            
            // Update audio level for visual feedback
            let level = self.calculateAudioLevel(from: buffer)
            DispatchQueue.main.async {
                self.audioLevel = level
            }
        }
        
        audioEngine.prepare()
        try audioEngine.start()
        
        // Start recognition
        recognitionTask = speechRecognizer?.recognitionTask(with: recognitionRequest) { [weak self] result, error in
            guard let self = self else { return }
            
            if let result = result {
                let transcription = result.bestTranscription.formattedString
                
                DispatchQueue.main.async {
                    if result.isFinal {
                        self.processVoiceInput(transcription)
                    } else {
                        self.statusMessage = "Heard: \(transcription)"
                    }
                }
            }
            
            if let error = error {
                DispatchQueue.main.async {
                    self.showError("Speech recognition error: \(error.localizedDescription)")
                    self.stopListening()
                }
            }
        }
    }
    
    private func calculateAudioLevel(from buffer: AVAudioPCMBuffer) -> Float {
        guard let channelData = buffer.floatChannelData?[0] else { return 0.0 }
        
        let frames = buffer.frameLength
        var sum: Float = 0.0
        
        for i in 0..<Int(frames) {
            sum += abs(channelData[i])
        }
        
        let average = sum / Float(frames)
        return min(average * 10, 1.0) // Normalize and cap at 1.0
    }
    
    private func processVoiceInput(_ input: String) {
        print("Processing voice input: \(String(input.prefix(50)))...")
        
        statusMessage = "Processing your request..."
        avatarEmotion = .thinking
        
        Task {
            do {
                let response = try await apiClient.processInput(input)
                
                await MainActor.run {
                    self.lastResponse = response
                    self.speakResponse(response)
                }
                
            } catch {
                await showError("Processing failed: \(error.localizedDescription)")
                await updateStatus("Ready - Tap to speak")
                avatarEmotion = .error
            }
        }
    }
    
    private func speakResponse(_ response: String) {
        guard !response.isEmpty else { return }
        
        isSpeaking = true
        avatarEmotion = .speaking
        statusMessage = "Speaking response..."
        
        let utterance = AVSpeechUtterance(string: response)
        utterance.voice = AVSpeechSynthesisVoice(language: "en-US")
        utterance.rate = AVSpeechUtteranceDefaultSpeechRate
        
        synthesizer.speak(utterance)
    }
    
    private func setupSpeechSynthesizer() {
        synthesizer.delegate = self
    }
    
    private func updateStatus(_ message: String) async {
        await MainActor.run {
            statusMessage = message
        }
    }
    
    private func showError(_ message: String) async {
        await MainActor.run {
            errorMessage = message
            print("GURU Error: \(message)")
        }
    }
    
    func clearError() {
        errorMessage = ""
    }
}

// MARK: - AVSpeechSynthesizerDelegate
extension GuruViewModel: AVSpeechSynthesizerDelegate {
    func speechSynthesizer(_ synthesizer: AVSpeechSynthesizer, didFinish utterance: AVSpeechUtterance) {
        DispatchQueue.main.async {
            self.isSpeaking = false
            self.avatarEmotion = .ready
            self.statusMessage = "Ready - Tap to speak"
        }
    }
    
    func speechSynthesizer(_ synthesizer: AVSpeechSynthesizer, didStart utterance: AVSpeechUtterance) {
        // Speech started
    }
}

// MARK: - Supporting Types
enum AvatarEmotion {
    case neutral, ready, listening, thinking, speaking, error
}

enum GuruError: Error {
    case speechRecognitionFailed
    case apiConfigurationMissing
    case networkError
    
    var localizedDescription: String {
        switch self {
        case .speechRecognitionFailed:
            return "Speech recognition setup failed"
        case .apiConfigurationMissing:
            return "API configuration required"
        case .networkError:
            return "Network connection failed"
        }
    }
}

// MARK: - Preview
struct ContentView_Previews: PreviewProvider {
    static var previews: some View {
        ContentView()
    }
}