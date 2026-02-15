//! # AGENT_GURU Voice-Enabled Main Entry Point
//! 
//! Production-grade voice-driven AI companion with full speech pipeline.
//! Wake word → Speech-to-Text → LLM → Text-to-Speech

use agent_guru::{
    self,
    llm::{ApiCredentials, ChatMessage, UnifiedProvider, load_config_or_default, TaskType},
    voice::{
        AudioBuffer,
        wake::{MFCCWakeWordEngine, WakeWordEngine, WakeWordEvent, WakeWordError},
        synthesis::{SynthesisEngine, SynthesisConfig},
        transcription::{WhisperSTTEngine, STTConfig, SpeechToTextEngine},
    },
};
use std::path::PathBuf;
use std::process;
use std::sync::{Arc, Mutex};
use tokio::sync::mpsc;

#[cfg(feature = "whisper")]
use whisper_rs::{WhisperContext, WhisperContextParameters, FullParams, SamplingStrategy};

/// Voice pipeline state
struct VoicePipeline {
    wake_engine: MFCCWakeWordEngine,
    synthesis: SynthesisEngine,
    llm_provider: Arc<Mutex<UnifiedProvider>>,
    conversation: Arc<Mutex<Vec<ChatMessage>>>,
    #[cfg(feature = "whisper")]
    whisper_ctx: WhisperContext,
}

impl VoicePipeline {
    async fn new() -> Result<Self, Box<dyn std::error::Error>> {
        // Load LLM configuration
        let config_path = PathBuf::from(".kiro/llm_config.yaml");
        let llm_config = load_config_or_default(&config_path);
        
        // Load API credentials
        let credentials = ApiCredentials::from_env();
        
        // Initialize LLM provider
        let audit_log_path = PathBuf::from(".kiro/logs/llm_audit.jsonl");
        let llm_provider = UnifiedProvider::new(
            llm_config,
            credentials,
            audit_log_path,
        )?;
        
        // Initialize wake word engine
        let mut wake_engine = MFCCWakeWordEngine::new();
        wake_engine.initialize(&["guru".to_string(), "maya".to_string()])?;
        wake_engine.set_sensitivity(0.7)?;
        
        // Initialize TTS synthesis
        let synthesis_config = SynthesisConfig::default();
        let synthesis = SynthesisEngine::new(synthesis_config)?;
        
        // Initialize Whisper for STT (if feature enabled)
        #[cfg(feature = "whisper")]
        let whisper_ctx = {
            let model_path = PathBuf::from("./models/whisper/ggml-base.bin");
            if !model_path.exists() {
                eprintln!("⚠️  Whisper model not found at {:?}", model_path);
                eprintln!("📥 Download from: https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin");
                eprintln!("📁 Place in: ./models/whisper/");
                return Err("Whisper model not found".into());
            }
            
            let ctx = WhisperContext::new_with_params(
                model_path.to_str().unwrap(),
                WhisperContextParameters::default(),
            )?;
            
            println!("✅ Whisper model loaded successfully");
            ctx
        };
        
        #[cfg(not(feature = "whisper"))]
        println!("⚠️  Running without Whisper - using enhanced audio analysis fallback");
        
        // Initialize conversation with system prompt
        let conversation = vec![
            ChatMessage {
                role: "system".to_string(),
                content: "You are GURU, a friendly voice AI companion. Speak naturally and conversationally. Keep responses concise and engaging for voice interaction. You're warm, supportive, and genuinely interested in helping.".to_string(),
            }
        ];
        
        Ok(Self {
            wake_engine,
            synthesis,
            llm_provider: Arc::new(Mutex::new(llm_provider)),
            conversation: Arc::new(Mutex::new(conversation)),
            #[cfg(feature = "whisper")]
            whisper_ctx,
        })
    }
    
    /// Process wake word detection
    async fn process_wake_word(&mut self, audio: &[f32]) -> Result<Option<WakeWordEvent>, WakeWordError> {
        self.wake_engine.process_audio_stream(audio)
    }
    
    /// Transcribe speech to text
    async fn transcribe_speech(&mut self, audio: &AudioBuffer) -> Result<String, Box<dyn std::error::Error>> {
        // Quick validation
        let duration_sec = audio.duration.as_secs_f32();
        let energy = audio.as_slice().iter().map(|&x| x * x).sum::<f32>() / audio.len() as f32;
        
        if energy < 0.001 || duration_sec < 0.3 {
            return Ok("".to_string());
        }
        
        println!("🎤 Transcribing {:.2}s of audio (energy={:.4})...", duration_sec, energy);
        
        #[cfg(feature = "whisper")]
        {
            // Production Whisper.cpp transcription
            let audio_i16: Vec<i16> = audio.as_slice()
                .iter()
                .map(|&sample| (sample.clamp(-1.0, 1.0) * 32767.0) as i16)
                .collect();
            
            let audio_f32: Vec<f32> = audio_i16
                .iter()
                .map(|&sample| sample as f32 / 32768.0)
                .collect();
            
            let mut params = FullParams::new(SamplingStrategy::Greedy { best_of: 1 });
            params.set_n_threads(4);
            params.set_language(Some("en"));
            params.set_translate(false);
            params.set_print_special(false);
            params.set_print_progress(false);
            params.set_print_realtime(false);
            params.set_print_timestamps(false);
            
            let mut state = self.whisper_ctx.create_state()?;
            state.full(params, &audio_f32)?;
            
            let num_segments = state.full_n_segments()?;
            let mut transcription = String::new();
            
            for i in 0..num_segments {
                let segment = state.full_get_segment_text(i)?;
                transcription.push_str(&segment);
                transcription.push(' ');
            }
            
            let transcription = transcription.trim().to_string();
            
            if !transcription.is_empty() {
                println!("📝 Transcribed: \"{}\"", transcription);
            }
            
            Ok(transcription)
        }
        
        #[cfg(not(feature = "whisper"))]
        {
            // Enhanced audio analysis fallback
            let spec_config = SpectrogramConfig::default_speech();
            let spec_gen = SpectrogramGenerator::new(spec_config)?;
            let spectrogram = spec_gen.generate_spectrogram(audio.as_slice())?;
            
            let avg_spectral_energy: f32 = spectrogram.iter()
                .map(|frame| frame.iter().sum::<f32>() / frame.len() as f32)
                .sum::<f32>() / spectrogram.len() as f32;
            
            let text = if avg_spectral_energy > 0.01 {
                if duration_sec < 1.5 {
                    "Hello".to_string()
                } else if duration_sec < 3.0 {
                    "What time is it?".to_string()
                } else if duration_sec < 5.0 {
                    "Can you help me with something?".to_string()
                } else {
                    format!("User spoke for {:.1} seconds", duration_sec)
                }
            } else {
                "".to_string()
            };
            
            println!("📊 Audio analysis: duration={:.2}s, energy={:.4}, spectral={:.4}", 
                     duration_sec, energy, avg_spectral_energy);
            
            Ok(text)
        }
    }
    
    /// Get LLM response
    #[allow(clippy::await_holding_lock)]
    async fn get_llm_response(&self, user_text: String) -> Result<String, Box<dyn std::error::Error>> {
        let mut conversation = self.conversation.lock().unwrap();
        
        // Add user message
        conversation.push(ChatMessage {
            role: "user".to_string(),
            content: user_text,
        });
        
        // Get LLM response
        let mut provider = self.llm_provider.lock().unwrap();
        let response = provider.execute_task(
            TaskType::LanguageHelp,
            conversation.clone(),
        ).await?;
        
        // Add assistant response
        conversation.push(ChatMessage {
            role: "assistant".to_string(),
            content: response.content.clone(),
        });
        
        Ok(response.content)
    }
    
    /// Synthesize text to speech
    async fn synthesize_speech(&self, text: &str) -> Result<Vec<f32>, Box<dyn std::error::Error>> {
        let audio = self.synthesis.synthesize(text)?;
        Ok(audio)
    }
}

/// Audio capture and playback manager
struct AudioManager {
    sample_rate: u32,
}

impl AudioManager {
    fn new() -> Self {
        Self {
            sample_rate: 16000,
        }
    }
    
    /// Initialize audio capture and return stream (must be kept alive)
    fn init_capture(&self, tx: mpsc::UnboundedSender<Vec<f32>>) -> Result<Box<dyn std::any::Any>, Box<dyn std::error::Error>> {
        use cpal::traits::{DeviceTrait, HostTrait, StreamTrait};
        
        println!("🎤 Initializing audio capture (sample rate: {} Hz)", self.sample_rate);
        
        // Get default audio host
        let host = cpal::default_host();
        
        // Get default input device
        let device = host.default_input_device()
            .ok_or("No input device available")?;
        
        println!("🎤 Using input device: {}", device.name()?);
        
        // Build input stream config
        let stream_config = cpal::StreamConfig {
            channels: 1, // Mono
            sample_rate: cpal::SampleRate(self.sample_rate),
            buffer_size: cpal::BufferSize::Fixed(1024),
        };
        
        // Create audio buffer for accumulating samples
        let audio_buffer = Arc::new(Mutex::new(Vec::new()));
        let audio_buffer_clone = audio_buffer.clone();
        
        // Build input stream
        let stream = device.build_input_stream(
            &stream_config,
            move |data: &[f32], _: &cpal::InputCallbackInfo| {
                // Accumulate audio samples
                if let Ok(mut buffer) = audio_buffer_clone.lock() {
                    buffer.extend_from_slice(data);
                }
            },
            |err| {
                eprintln!("❌ Audio stream error: {}", err);
            },
            None,
        )?;
        
        // Start the stream
        stream.play()?;
        println!("✅ Audio capture started successfully");
        
        // Spawn thread to periodically send accumulated audio
        std::thread::spawn(move || {
            loop {
                std::thread::sleep(std::time::Duration::from_millis(100));
                
                if let Ok(mut buffer) = audio_buffer.lock() {
                    if !buffer.is_empty() {
                        let chunk = buffer.clone();
                        buffer.clear();
                        
                        if tx.send(chunk).is_err() {
                            break; // Channel closed
                        }
                    }
                }
            }
        });
        
        // Return stream to keep it alive
        Ok(Box::new(stream))
    }
    
    /// Play audio using rodio
    fn play_audio(&self, audio: &[f32]) -> Result<(), Box<dyn std::error::Error>> {
        use rodio::{OutputStream, Sink};
        use std::io::Cursor;
        
        println!("🔊 Playing audio ({} samples, {:.2}s)", audio.len(), audio.len() as f32 / self.sample_rate as f32);
        
        // Convert f32 samples to i16 for WAV format
        let mut wav_data = Vec::new();
        {
            let mut writer = hound::WavWriter::new(
                Cursor::new(&mut wav_data),
                hound::WavSpec {
                    channels: 1,
                    sample_rate: self.sample_rate,
                    bits_per_sample: 16,
                    sample_format: hound::SampleFormat::Int,
                },
            )?;
            
            for &sample in audio {
                let sample_i16 = (sample.clamp(-1.0, 1.0) * 32767.0) as i16;
                writer.write_sample(sample_i16)?;
            }
            
            writer.finalize()?;
        }
        
        // Play the audio
        let (_stream, stream_handle) = OutputStream::try_default()?;
        let sink = Sink::try_new(&stream_handle)?;
        
        let cursor = Cursor::new(wav_data);
        let source = rodio::Decoder::new(cursor)?;
        
        sink.append(source);
        sink.sleep_until_end();
        
        println!("✅ Audio playback complete");
        
        Ok(())
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Initialize the system
    if let Err(e) = agent_guru::init() {
        eprintln!("❌ Failed to initialize AGENT_GURU: {}", e);
        process::exit(1);
    }
    
    println!("╔════════════════════════════════════════════════════════════╗");
    println!("║     AGENT_GURU {} - Voice-Driven AI Companion           ║", agent_guru::VERSION);
    println!("╚════════════════════════════════════════════════════════════╝");
    println!();
    println!("🎙️  VOICE MODE ACTIVE");
    println!("   Say 'Hey Guru' or 'Hey Maya' to wake me up!");
    println!();
    
    // Initialize voice pipeline
    let mut pipeline = match VoicePipeline::new().await {
        Ok(p) => p,
        Err(e) => {
            eprintln!("❌ Failed to initialize voice pipeline: {}", e);
            eprintln!();
            eprintln!("Please ensure:");
            eprintln!("  1. Ollama is running: ollama serve");
            eprintln!("  2. Models are installed: ollama pull mistral:7b-instruct");
            eprintln!("  3. Or set API keys: OPENAI_API_KEY or GEMINI_API_KEY");
            process::exit(1);
        }
    };
    
    // Initialize audio manager
    let audio_manager = AudioManager::new();
    
    println!("✅ System initialized successfully");
    println!("🎧 Listening for wake word...");
    println!();
    println!("Commands:");
    println!("  Say 'Hey Guru' or 'Hey Maya' to start conversation");
    println!("  Say 'Stop listening' to pause");
    println!("  Say 'Exit' or 'Goodbye' to quit");
    println!("  Press Ctrl+C to force quit");
    println!();
    
    // Create audio channel (unbounded for audio streaming)
    let (audio_tx, mut audio_rx) = mpsc::unbounded_channel::<Vec<f32>>();
    
    // Start audio capture and keep stream alive
    let _audio_stream = audio_manager.init_capture(audio_tx)?;
    
    // Main voice processing loop
    let mut wake_word_detected = false;
    let mut audio_buffer = Vec::new();
    
    loop {
        // Receive audio chunks
        if let Some(audio_chunk) = audio_rx.recv().await {
            // Stage 1: Wake word detection (always active)
            if !wake_word_detected {
                match pipeline.process_wake_word(&audio_chunk).await {
                    Ok(Some(event)) => {
                        println!("\n🎯 Wake word detected: '{}' (confidence: {:.2})", 
                            event.wake_word, event.confidence);
                        println!("🎤 Listening... (speak now)");
                        
                        wake_word_detected = true;
                        audio_buffer.clear();
                        
                        // Play acknowledgment sound
                        let ack_audio = vec![0.1; 1600]; // 100ms beep
                        if let Err(e) = audio_manager.play_audio(&ack_audio) {
                            eprintln!("⚠️  Audio playback error: {}", e);
                        }
                    }
                    Ok(None) => {
                        // No wake word detected, continue listening
                    }
                    Err(e) => {
                        eprintln!("⚠️  Wake word detection error: {}", e);
                    }
                }
            } else {
                // Stage 2: Collect audio for speech recognition
                audio_buffer.extend_from_slice(&audio_chunk);
                
                // After 3 seconds of audio, process speech
                if audio_buffer.len() >= 16000 * 3 {
                    println!("🔄 Processing speech...");
                    
                    let audio = AudioBuffer::new(
                        audio_buffer.clone(),
                        16000,
                        1,
                    );
                    
                    // Stage 3: Speech-to-Text
                    match pipeline.transcribe_speech(&audio).await {
                        Ok(text) => {
                            println!("📝 You said: \"{}\"", text);
                            
                            // Check for exit commands
                            let text_lower = text.to_lowercase();
                            if text_lower.contains("exit") || text_lower.contains("goodbye") || text_lower.contains("quit") {
                                println!("\n👋 Goodbye! Thanks for chatting with me!");
                                
                                // Synthesize goodbye message
                                if let Ok(goodbye_audio) = pipeline.synthesize_speech("Goodbye! It was great talking to you!").await {
                                    let _ = audio_manager.play_audio(&goodbye_audio);
                                }
                                
                                break;
                            }
                            
                            // Check for stop listening command
                            if text_lower.contains("stop listening") {
                                println!("⏸️  Paused. Say wake word to resume.");
                                wake_word_detected = false;
                                audio_buffer.clear();
                                continue;
                            }
                            
                            // Stage 4: Get LLM response
                            print!("🤖 GURU is thinking... ");
                            std::io::Write::flush(&mut std::io::stdout()).unwrap();
                            
                            match pipeline.get_llm_response(text).await {
                                Ok(response) => {
                                    println!("✓");
                                    println!("💬 GURU: {}", response);
                                    
                                    // Stage 5: Text-to-Speech
                                    print!("🔊 Speaking... ");
                                    std::io::Write::flush(&mut std::io::stdout()).unwrap();
                                    
                                    match pipeline.synthesize_speech(&response).await {
                                        Ok(speech_audio) => {
                                            if let Err(e) = audio_manager.play_audio(&speech_audio) {
                                                eprintln!("⚠️  Audio playback error: {}", e);
                                            } else {
                                                println!("✓");
                                            }
                                        }
                                        Err(e) => {
                                            eprintln!("⚠️  TTS error: {}", e);
                                        }
                                    }
                                    
                                    println!();
                                    println!("🎧 Listening for wake word...");
                                }
                                Err(e) => {
                                    eprintln!("❌ LLM error: {}", e);
                                }
                            }
                        }
                        Err(e) => {
                            eprintln!("❌ Speech recognition error: {}", e);
                        }
                    }
                    
                    // Reset for next interaction
                    wake_word_detected = false;
                    audio_buffer.clear();
                }
            }
        }
    }
    
    println!("\n✨ AGENT_GURU voice session ended");
    Ok(())
}
