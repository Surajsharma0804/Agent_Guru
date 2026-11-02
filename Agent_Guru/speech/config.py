"""Configuration for the speech engine."""

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

#: Devices WhisperTranscriber understands; anything else in AGENT_GURU_STT_DEVICE is refused.
_STT_DEVICES = frozenset({"auto", "cpu", "cuda"})
#: CTranslate2 compute types; a misspelt one would only fail when the model loads, mid-startup.
_STT_COMPUTE_TYPES = frozenset({
    "default", "auto", "int8", "int8_float16", "int8_float32", "int8_bfloat16",
    "int16", "float16", "bfloat16", "float32",
})


def _stt_prompt() -> str | None:
    """AGENT_GURU_STT_PROMPT: unset keeps the transcriber's own prompt, "none" turns it off."""
    value = os.environ.get("AGENT_GURU_STT_PROMPT", "").strip()
    if not value:
        return None
    return "" if value.lower() == "none" else value


def _stt_device() -> str:
    """AGENT_GURU_STT_DEVICE, or "auto" when unset or not a device the transcriber knows."""
    value = os.environ.get("AGENT_GURU_STT_DEVICE", "").strip().lower()
    if not value:
        return "auto"
    if value not in _STT_DEVICES:
        logger.warning("AGENT_GURU_STT_DEVICE=%r is not one of %s; using auto", value, sorted(_STT_DEVICES))
        return "auto"
    return value


def _stt_compute_type() -> str | None:
    """AGENT_GURU_STT_COMPUTE_TYPE, or None (chosen per device) when unset or unknown."""
    value = os.environ.get("AGENT_GURU_STT_COMPUTE_TYPE", "").strip().lower()
    if not value:
        return None
    if value not in _STT_COMPUTE_TYPES:
        logger.warning(
            "AGENT_GURU_STT_COMPUTE_TYPE=%r is not a CTranslate2 compute type; choosing one per device",
            value,
        )
        return None
    return value


@dataclass
class AudioConfig:
    """Audio input/output configuration."""

    sample_rate: int = 16000
    channels: int = 1
    chunk_size: int = 1024
    buffer_size: int = 4096
    format: str = "int16"


@dataclass
class AudioProcessingConfig:
    """Audio processing configuration."""

    enable_noise_reduction: bool = True
    enable_vad: bool = True
    enable_echo_cancellation: bool = True
    enable_agc: bool = True
    vad_aggressiveness: int = 2  # 0-3
    noise_reduction_strength: float = 0.5  # 0.0-1.0


@dataclass
class WakeWordConfig:
    """Wake word detection configuration."""

    wake_words: list[str] = field(default_factory=lambda: ["Hey Guru", "Hey Maya"])
    sensitivity: float = 0.5  # 0.0-1.0
    model_path: str | None = None
    detection_timeout_ms: int = 200


@dataclass
class STTConfig:
    """Speech-to-text configuration."""
    model_size: str = "base"  # base fits in ~300MB VRAM, already cached - no HuggingFace download needed
    model_path: str | None = None
    # None picks per device: int8_float16 on the GPU (213 MiB for base,
    # against 232 MiB for float16 at the same speed, measured on an RTX 2050
    # where gemma4 leaves ~147 MiB spare), float32 on the CPU.
    # AGENT_GURU_STT_COMPUTE_TYPE sets it; the device and compute type used to
    # be fixed here, so trying Whisper on the other device meant editing code.
    compute_type: str | None = field(default_factory=_stt_compute_type)
    beam_size: int = 5
    # "auto": the GPU when a CUDA device and the optional CUDA libraries work,
    # otherwise the CPU with a log line saying why. This said "cuda" but was
    # never read: SpeechEngine built the transcriber without a device, so
    # every command ran on the CPU. See README, "GPU speech recognition".
    # AGENT_GURU_STT_DEVICE sets it.
    device: str = field(default_factory=_stt_device)
    language: str | None = "en"  # force English - stops Whisper misidentifying as Hindi
    # The names prompt Whisper is primed with. None: WhisperTranscriber's own
    # default; "": no prompt. AGENT_GURU_STT_PROMPT sets it ("none" for no
    # prompt), so the prompt can be changed without a release if a name the
    # owner uses keeps being misheard.
    initial_prompt: str | None = field(default_factory=_stt_prompt)


@dataclass
class TTSConfigSettings:
    """Text-to-speech configuration."""

    engine: str = "pyttsx3"  # pyttsx3, coqui, google, azure, aws
    male_voice_id: str | None = None
    female_voice_id: str | None = None
    sample_rate: int = 22050
    enable_emotion: bool = True
    enable_ssml: bool = False


@dataclass
class EmotionConfig:
    """Emotion detection configuration."""

    model_path: str | None = None
    confidence_threshold: float = 0.5
    enable_streaming: bool = True


@dataclass
class VoiceBiometricConfig:
    """Voice biometric configuration."""

    model_path: str | None = None
    enrollment_samples: int = 5
    verification_threshold: float = 0.7
    enable_liveness_detection: bool = True


@dataclass
class VoiceCloningConfig:
    """Voice cloning configuration."""

    target_similarity: float = 0.85
    training_epochs: int = 100
    use_gpu: bool = True
    model_architecture: str = "tacotron2"


@dataclass
class NoiseCancellationConfig:
    """Advanced noise cancellation configuration."""

    reduction_level: str = "medium"  # light, medium, aggressive
    target_snr_db: float = 20.0
    enable_adaptive: bool = True


@dataclass
class StreamingConfig:
    """Streaming audio configuration."""

    chunk_duration_ms: int = 200
    max_latency_ms: int = 500
    codec: str = "pcm"  # pcm, opus, aac
    enable_full_duplex: bool = True


@dataclass
class CommandConfig:
    """Command parsing configuration."""

    enable_custom_commands: bool = True
    enable_command_chaining: bool = True
    confidence_threshold: float = 0.6


@dataclass
class ContextConfig:
    """Conversation context configuration."""

    max_turns: int = 10
    enable_reference_resolution: bool = True
    enable_topic_detection: bool = True


@dataclass
class LanguageConfig:
    """Multi-language configuration."""

    supported_languages: list[str] = field(
        default_factory=lambda: ["en", "es", "fr", "de", "zh", "ja", "hi", "pa"],
    )
    auto_detect: bool = True
    default_language: str = "en"


@dataclass
class ModelRouterConfig:
    """Model router configuration."""

    prefer_local: bool = False
    prefer_cloud: bool = False
    enable_fallback: bool = True
    cloud_providers: list[str] = field(default_factory=lambda: ["google", "azure", "aws"])


@dataclass
class BackgroundServiceConfig:
    """Background service configuration."""

    enable_auto_start: bool = True
    sleep_mode_timeout_seconds: int = 3
    max_cpu_percent_sleep: float = 5.0
    max_memory_mb_sleep: int = 100
    max_cpu_percent_wake: float = 30.0
    max_memory_mb_wake: int = 500


@dataclass
class BatteryConfig:
    """Battery optimization configuration."""

    optimization_level: str = "balanced"  # aggressive, balanced, performance
    low_battery_threshold: float = 0.2
    critical_battery_threshold: float = 0.05
    max_battery_impact_percent_per_hour: float = 10.0


@dataclass
class SpeechEngineConfig:
    """Main speech engine configuration."""

    # Component configurations
    audio: AudioConfig = field(default_factory=AudioConfig)
    audio_processing: AudioProcessingConfig = field(default_factory=AudioProcessingConfig)
    wake_word: WakeWordConfig = field(default_factory=WakeWordConfig)
    stt: STTConfig = field(default_factory=STTConfig)
    tts: TTSConfigSettings = field(default_factory=TTSConfigSettings)
    emotion: EmotionConfig = field(default_factory=EmotionConfig)
    voice_biometric: VoiceBiometricConfig = field(default_factory=VoiceBiometricConfig)
    voice_cloning: VoiceCloningConfig = field(default_factory=VoiceCloningConfig)
    noise_cancellation: NoiseCancellationConfig = field(default_factory=NoiseCancellationConfig)
    streaming: StreamingConfig = field(default_factory=StreamingConfig)
    command: CommandConfig = field(default_factory=CommandConfig)
    context: ContextConfig = field(default_factory=ContextConfig)
    language: LanguageConfig = field(default_factory=LanguageConfig)
    model_router: ModelRouterConfig = field(default_factory=ModelRouterConfig)
    background_service: BackgroundServiceConfig = field(default_factory=BackgroundServiceConfig)
    battery: BatteryConfig = field(default_factory=BatteryConfig)

    # Global settings
    log_level: str = "INFO"
    enable_metrics: bool = True
    data_dir: Path = field(default_factory=lambda: Path.home() / ".guru" / "speech")

    @classmethod
    def for_guru_personality(cls) -> "SpeechEngineConfig":
        """Create configuration optimized for Guru (male) personality."""
        return cls()
        # Guru-specific settings can be added here

    @classmethod
    def for_maya_personality(cls) -> "SpeechEngineConfig":
        """Create configuration optimized for Maya (female) personality."""
        return cls()
        # Maya-specific settings can be added here
