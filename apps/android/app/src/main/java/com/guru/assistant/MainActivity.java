/**
 * GURU Android Application - Google Play Store Compliant
 * 
 * COMPLIANCE REQUIREMENTS:
 * - Google Play Developer Program Policies
 * - Android Permission Model
 * - Foreground Service Rules
 * - Data Safety Declarations
 * - No system automation
 * - No accessibility abuse
 * - API-only LLM processing
 * 
 * FEATURES:
 * - Voice assistant (push-to-talk)
 * - Face avatar display
 * - API-based conversation
 * - Secure credential storage
 * - Explicit permission requests
 */

package com.guru.assistant;

import android.Manifest;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.content.Context;
import andr

package com.guru.assistant;

import android.Manifest;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.os.Bundle;
import android.speech.RecognizerIntent;
import android.speech.SpeechRecognizer;
import android.speech.tts.TextToSpeech;
import android.util.Log;
import android.view.View;
import android.widget.Button;
import android.widget.ImageView;
import android.widget.TextView;
import android.widget.Toast;

import androidx.annotation.NonNull;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;

import java.util.ArrayList;
import java.util.Locale;

public class MainActivity extends AppCompatActivity implements TextToSpeech.OnInitListener {
    
    private static final String TAG = "GuruMainActivity";
    private static final int PERMISSION_REQUEST_RECORD_AUDIO = 1001;
    private static final int SPEECH_REQUEST_CODE = 1002;
    
    // UI Components
    private ImageView avatarFace;
    private Button micButton;
    private TextView statusText;
    private TextView responseText;
    
    // Core Components
    private TextToSpeech textToSpeech;
    private SpeechRecognizer speechRecognizer;
    private GuruApiClient apiClient;
    private AndroidCredentialManager credentialManager;
    private AvatarFaceEngine avatarEngine;
    
    // State
    private boolean isListening = false;
    private boolean isSpeaking = false;
    private boolean isInitialized = false;
    
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);
        
        Log.i(TAG, "GURU Android Application starting - Store Compliant Mode");
        
        initializeUI();
        initializeComponents();
        checkPermissions();
    }
    
    private void initializeUI() {
        avatarFace = findViewById(R.id.avatar_face);
        micButton = findViewById(R.id.mic_button);
        statusText = findViewById(R.id.status_text);
        responseText = findViewById(R.id.response_text);
        
        // Set up mic button (push-to-talk)
        micButton.setOnClickListener(v -> {
            if (isListening) {
                stopListening();
            } else {
                startListening();
            }
        });
        
        // Initial UI state
        updateStatus("Initializing GURU...");
        avatarFace.setImageResource(R.drawable.avatar_neutral);
    }
    
    private void initializeComponents() {
        try {
            // Initialize TTS
            textToSpeech = new TextToSpeech(this, this);
            
            // Initialize API client (cloud-only)
            apiClient = new GuruApiClient();
            
            // Initialize credential manager
            credentialManager = new AndroidCredentialManager(this);
            
            // Initialize avatar engine (face only)
            avatarEngine = new AvatarFaceEngine(avatarFace);
            
            Log.i(TAG, "Core components initialized");
            
        } catch (Exception e) {
            Log.e(TAG, "Component initialization failed", e);
            showError("Initialization failed: " + e.getMessage());
        }
    }
    
    private void checkPermissions() {
        // Check microphone permission
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) 
                != PackageManager.PERMISSION_GRANTED) {
            
            // Request permission with clear explanation
            ActivityCompat.requestPermissions(this,
                    new String[]{Manifest.permission.RECORD_AUDIO},
                    PERMISSION_REQUEST_RECORD_AUDIO);
        } else {
            onPermissionsGranted();
        }
    }
    
    @Override
    public void onRequestPermissionsResult(int requestCode, @NonNull String[] permissions, 
                                         @NonNull int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        
        if (requestCode == PERMISSION_REQUEST_RECORD_AUDIO) {
            if (grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
                onPermissionsGranted();
            } else {
                showError("Microphone permission required for voice interaction");
                micButton.setEnabled(false);
            }
        }
    }
    
    private void onPermissionsGranted() {
        Log.i(TAG, "Permissions granted, completing initialization");
        
        // Initialize speech recognizer
        if (SpeechRecognizer.isRecognitionAvailable(this)) {
            speechRecognizer = SpeechRecognizer.createSpeechRecognizer(this);
            speechRecognizer.setRecognitionListener(new GuruSpeechRecognitionListener());
        }
        
        // Check API configuration
        checkApiConfiguration();
    }
    
    private void checkApiConfiguration() {
        credentialManager.getConfiguredApis(new AndroidCredentialManager.ApiCallback() {
            @Override
            public void onSuccess(ArrayList<String> configuredApis) {
                if (configuredApis.isEmpty()) {
                    // Launch setup wizard
                    launchSetupWizard();
                } else {
                    onInitializationComplete();
                }
            }
            
            @Override
            public void onError(String error) {
                Log.e(TAG, "API configuration check failed: " + error);
                launchSetupWizard();
            }
        });
    }
    
    private void launchSetupWizard() {
        Log.i(TAG, "Launching API setup wizard");
        Intent setupIntent = new Intent(this, SetupWizardActivity.class);
        startActivity(setupIntent);
    }
    
    private void onInitializationComplete() {
        isInitialized = true;
        updateStatus("Ready - Tap microphone to speak");
        micButton.setEnabled(true);
        avatarEngine.setEmotion(AvatarFaceEngine.Emotion.READY);
        
        Log.i(TAG, "GURU Android Application ready");
    }
    
    private void startListening() {
        if (!isInitialized || isListening || isSpeaking) {
            return;
        }
        
        try {
            Intent intent = new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH);
            intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL,
                    RecognizerIntent.LANGUAGE_MODEL_FREE_FORM);
            intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE, Locale.getDefault());
            intent.putExtra(RecognizerIntent.EXTRA_PROMPT, "Speak to GURU...");
            
            speechRecognizer.startListening(intent);
            
            isListening = true;
            updateStatus("Listening... (tap to stop)");
            micButton.setText("Stop");
            avatarEngine.setEmotion(AvatarFaceEngine.Emotion.LISTENING);
            
            Log.d(TAG, "Started listening for voice input");
            
        } catch (Exception e) {
            Log.e(TAG, "Failed to start listening", e);
            showError("Voice recognition failed");
        }
    }
    
    private void stopListening() {
        if (!isListening) {
            return;
        }
        
        speechRecognizer.stopListening();
        isListening = false;
        updateStatus("Processing...");
        micButton.setText("Speak");
        avatarEngine.setEmotion(AvatarFaceEngine.Emotion.THINKING);
        
        Log.d(TAG, "Stopped listening");
    }
    
    private void processVoiceInput(String input) {
        Log.i(TAG, "Processing voice input: " + input.substring(0, Math.min(input.length(), 50)) + "...");
        
        updateStatus("Processing your request...");
        avatarEngine.setEmotion(AvatarFaceEngine.Emotion.THINKING);
        
        // Process through API (cloud-only)
        apiClient.processInput(input, new GuruApiClient.ResponseCallback() {
            @Override
            public void onSuccess(String response) {
                runOnUiThread(() -> {
                    displayResponse(response);
                    speakResponse(response);
                });
            }
            
            @Override
            public void onError(String error) {
                runOnUiThread(() -> {
                    Log.e(TAG, "API processing error: " + error);
                    showError("Processing failed: " + error);
                    updateStatus("Ready - Tap microphone to speak");
                    avatarEngine.setEmotion(AvatarFaceEngine.Emotion.ERROR);
                });
            }
        });
    }
    
    private void displayResponse(String response) {
        responseText.setText(response);
        updateStatus("Speaking response...");
    }
    
    private void speakResponse(String response) {
        if (textToSpeech != null) {
            isSpeaking = true;
            avatarEngine.setEmotion(AvatarFaceEngine.Emotion.SPEAKING);
            avatarEngine.startSpeaking(response);
            
            textToSpeech.speak(response, TextToSpeech.QUEUE_FLUSH, null, "guru_response");
        }
    }
    
    private void onSpeechComplete() {
        isSpeaking = false;
        updateStatus("Ready - Tap microphone to speak");
        avatarEngine.setEmotion(AvatarFaceEngine.Emotion.READY);
        avatarEngine.stopSpeaking();
    }
    
    private void updateStatus(String status) {
        statusText.setText(status);
        Log.d(TAG, "Status: " + status);
    }
    
    private void showError(String error) {
        Toast.makeText(this, error, Toast.LENGTH_LONG).show();
        updateStatus("Error: " + error);
        avatarEngine.setEmotion(AvatarFaceEngine.Emotion.ERROR);
    }
    
    @Override
    public void onInit(int status) {
        if (status == TextToSpeech.SUCCESS) {
            int result = textToSpeech.setLanguage(Locale.getDefault());
            
            if (result == TextToSpeech.LANG_MISSING_DATA || 
                result == TextToSpeech.LANG_NOT_SUPPORTED) {
                Log.w(TAG, "TTS language not supported");
            } else {
                Log.i(TAG, "TTS initialized successfully");
            }
            
            // Set up TTS completion listener
            textToSpeech.setOnUtteranceProgressListener(new GuruUtteranceProgressListener(this));
            
        } else {
            Log.e(TAG, "TTS initialization failed");
            showError("Text-to-speech initialization failed");
        }
    }
    
    @Override
    protected void onDestroy() {
        super.onDestroy();
        
        // Cleanup resources
        if (textToSpeech != null) {
            textToSpeech.stop();
            textToSpeech.shutdown();
        }
        
        if (speechRecognizer != null) {
            speechRecognizer.destroy();
        }
        
        if (apiClient != null) {
            apiClient.shutdown();
        }
        
        Log.i(TAG, "GURU Android Application destroyed");
    }
    
    // Package-private method for TTS completion callback
    void onTtsComplete() {
        onSpeechComplete();
    }
    
    // Inner class for speech recognition
    private class GuruSpeechRecognitionListener implements android.speech.RecognitionListener {
        
        @Override
        public void onReadyForSpeech(Bundle params) {
            Log.d(TAG, "Speech recognizer ready");
        }
        
        @Override
        public void onBeginningOfSpeech() {
            Log.d(TAG, "Speech input detected");
        }
        
        @Override
        public void onRmsChanged(float rmsdB) {
            // Update visual feedback based on audio level
            avatarEngine.updateAudioLevel(rmsdB);
        }
        
        @Override
        public void onBufferReceived(byte[] buffer) {
            // Not used
        }
        
        @Override
        public void onEndOfSpeech() {
            Log.d(TAG, "End of speech detected");
            stopListening();
        }
        
        @Override
        public void onError(int error) {
            String errorMessage = "Speech recognition error: " + error;
            Log.e(TAG, errorMessage);
            
            isListening = false;
            micButton.setText("Speak");
            showError("Voice recognition failed");
            avatarEngine.setEmotion(AvatarFaceEngine.Emotion.ERROR);
        }
        
        @Override
        public void onResults(Bundle results) {
            ArrayList<String> matches = results.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION);
            
            if (matches != null && !matches.isEmpty()) {
                String input = matches.get(0);
                processVoiceInput(input);
            } else {
                showError("No speech recognized");
                updateStatus("Ready - Tap microphone to speak");
                avatarEngine.setEmotion(AvatarFaceEngine.Emotion.READY);
            }
        }
        
        @Override
        public void onPartialResults(Bundle partialResults) {
            // Show partial results for better UX
            ArrayList<String> matches = partialResults.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION);
            if (matches != null && !matches.isEmpty()) {
                updateStatus("Heard: " + matches.get(0));
            }
        }
        
        @Override
        public void onEvent(int eventType, Bundle params) {
            // Not used
        }
    }
}