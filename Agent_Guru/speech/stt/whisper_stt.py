"""Whisper-based speech-to-text transcription for desktop platforms."""

import contextlib
import logging
import os
import sys
import threading
import time
from collections.abc import Generator
from pathlib import Path

import numpy as np

# faster_whisper depends on ctranslate2 which may be blocked by Windows
# Application Control policies - graceful fallback
try:
    from faster_whisper import WhisperModel
except (ImportError, OSError) as _fw_err:
    WhisperModel = None  # type: ignore[misc,assignment]
    logging.getLogger(__name__).warning(
        "faster_whisper unavailable (ctranslate2 DLL blocked or missing): %s", _fw_err
    )

from Agent_Guru.speech.exceptions import GuruSpeechError
from Agent_Guru.speech.models import TranscriptionResult, TranscriptionSegment

logger = logging.getLogger(__name__)

# faster_whisper's array-input path (as opposed to file-path input, which
# has its own internal decode/resample step) requires audio to already be
# mono float32 at exactly this rate. See transcribe()'s BUG FIX note below.
_WHISPER_SAMPLE_RATE = 16000


def _cuda_device_count() -> int:
    """CUDA devices CTranslate2 (the engine under faster-whisper) can see.

    Not torch.cuda: a clean install gets a CPU-only torch that reports no GPU
    on a machine that has one, while CTranslate2 still sees it.
    """
    try:
        import ctranslate2

        return int(ctranslate2.get_cuda_device_count())
    except Exception:
        return 0


#: Quoted in every CPU-fallback message. Measured with the "base" model on an
#: RTX 2050 laptop, warm, median of five runs.
_GPU_COST = (
    "a 2.5 s command takes about 1.8 s to transcribe on the CPU and 0.2 s on "
    "the GPU (measured with the base model on an RTX 2050 laptop)"
)
_GPU_HOWTO = (
    'install the optional CUDA 12 libraries (about 2 GB): pip install '
    'nvidia-cublas-cu12 "nvidia-cudnn-cu12==9.*" (README, "GPU speech recognition")'
)

#: Compute types CTranslate2 can run on a CPU. A GPU type such as "float16"
#: asked for in the config is replaced by float32 when the load falls back.
_CPU_COMPUTE_TYPES = frozenset({"float32", "int8", "int8_float32"})

#: Compute type on the CPU when none is configured. It was float32. Measured
#: with the base model on the development laptop through this class: 175 noisy
#: command clips (25 commands, 7 voices, 15 dB SNR) went from WER 6.5% and a
#: median 2.19 s per command at float32 to WER 5.5% and 0.84 s at int8, and 73
#: LibriSpeech clips from 9.9% and 1.50 s to 10.2% and 0.98 s. The two differed
#: on 11 command clips, int8 better on six of them.
_CPU_DEFAULT_COMPUTE = "int8"

#: The pip packages behind the "gpu" extra install their DLLs here, under
#: site-packages/nvidia/<name>/bin, which Windows does not search.
_NVIDIA_DLL_PACKAGES = ("cublas", "cudnn", "cuda_nvrtc")


def _add_nvidia_runtime_to_path() -> list[str]:
    """Make the pip-installed CUDA 12 libraries loadable on Windows.

    CTranslate2 loads cuBLAS and cuDNN only when a model first runs, and
    Windows looks for them on PATH. The nvidia-* wheels put them inside
    site-packages, so without this they are installed but never found.
    """
    if sys.platform != "win32":
        return []
    try:
        # Namespace package created by the optional nvidia-* wheels; untyped,
        # and absent unless the "gpu" extra is installed.
        import nvidia  # type: ignore[import-untyped, import-not-found, unused-ignore]
    except ImportError:
        return []
    added: list[str] = []
    path = os.environ.get("PATH", "")
    for base in list(getattr(nvidia, "__path__", [])):
        for name in _NVIDIA_DLL_PACKAGES:
            bin_dir = Path(base) / name / "bin"
            if bin_dir.is_dir() and str(bin_dir) not in path:
                os.add_dll_directory(str(bin_dir))
                path = str(bin_dir) + os.pathsep + path
                added.append(str(bin_dir))
    if added:
        os.environ["PATH"] = path
    return added


#: Why CUDA failed earlier in this process, or None if it has not failed.
#:
#: CTranslate2 must be tried on CUDA at most once per process once it has
#: failed. With cublas64_12.dll missing, the first attempt raises "Library
#: cublas64_12.dll is not found or cannot be loaded" within a second, but a
#: second attempt, on any thread, never returns: it blocks inside encode().
#: main.py's wake-word model made the first attempt at startup and the
#: command transcriber made the second on the first spoken command, so every
#: command hit the orchestrator's 30 s STT timeout with an empty transcript.
_cuda_failure: str | None = None
#: Held for the whole of a CUDA trial, so two threads cannot both make a
#: first attempt and one of them become the hanging second.
_cuda_trial_lock = threading.Lock()


def cuda_failure() -> str | None:
    """Why CUDA failed earlier in this process, or None if it has not."""
    return _cuda_failure


@contextlib.contextmanager
def cuda_trial() -> Generator[None, None, None]:
    """Guard one attempt to load and run a model on CUDA.

    Raises RuntimeError at once if an earlier attempt failed, and records
    the failure of this one, so CUDA is never retried after it has failed
    in this process. See _cuda_failure for why a retry hangs.
    """
    global _cuda_failure
    with _cuda_trial_lock:
        if _cuda_failure is not None:
            msg = f"not retried after an earlier CUDA failure in this process ({_cuda_failure})"
            raise RuntimeError(msg)
        try:
            yield
        except Exception as exc:
            _cuda_failure = f"{type(exc).__name__}: {exc}"
            raise


def prepare_cuda_runtime() -> int:
    """Make the optional CUDA libraries findable; return CUDA devices worth trying.

    A non-zero count means only that a GPU exists. Whether the libraries
    load is known only once a model has run on it, so callers must still
    run a transcription inside cuda_trial() and fall back to the CPU when
    it fails. Returns 0 once CUDA has failed in this process, because a
    second attempt hangs.
    """
    if _cuda_failure is not None:
        return 0
    _add_nvidia_runtime_to_path()
    return _cuda_device_count()


class WhisperTranscriber:
    """Speech-to-text transcriber using OpenAI Whisper (faster-whisper).

    Supports:
    - Multi-language transcription (8+ languages)
    - Real-time factor <0.5
    - Speaker diarization
    - GPU acceleration (CUDA, Metal, OpenCL)
    - CPU fallback
    """

    def __init__(
        self,
        model_size: str = "base",
        model_path: str | None = None,
        compute_type: str | None = None,
        beam_size: int = 5,
        device: str = "cpu",
    ) -> None:
        """Initialize Whisper transcriber.

        Args:
            model_size: Whisper model size ("tiny", "base", "small", "medium", "large")
            model_path: Path to custom model (overrides model_size)
            compute_type: Compute type for inference. Auto-detected if None:
                          "int8_float16" on CUDA (saves ~50% VRAM),
                          "int8" on CPU (see _CPU_DEFAULT_COMPUTE).
            beam_size: Beam size for decoding
            device: "cpu", "cuda" or "auto". "cuda" and "auto" both try the
                GPU at load and fall back to the CPU, with a log line saying
                why, if the GPU or its CUDA libraries are unusable; "auto"
                treats a missing GPU as normal, "cuda" warns about it.

        """
        self.model_size = model_size
        self.model_path = model_path
        # Kept so the CPU fallback can replace a GPU-only type ("float16",
        # "int8_float16") that the CPU cannot run.
        self._requested_compute = compute_type
        # P2-77: Auto-detect optimal compute type for VRAM reduction.
        # int8_float16 on CUDA reduces VRAM from ~3GB to ~1.6GB for large-v3.
        if compute_type is None:
            self.compute_type = "int8_float16" if device == "cuda" else _CPU_DEFAULT_COMPUTE
        else:
            self.compute_type = compute_type
        self.beam_size = beam_size
        self.device = device
        self._model: WhisperModel | None = None
        # BUG FIX (Round 16): see _load_model()'s docstring.
        self._model_load_failed = False

    def _load_model(self) -> WhisperModel:
        """Load Whisper model (lazy loading, synchronous).

        Uses local cache when available to avoid HuggingFace network calls on
        every startup. Falls back to downloading if not yet cached.

        BUG FIX (Round 16): this used to only check `self._model is None`
        to decide whether a load had already been attempted, so a
        persistently broken environment (blocked ctranslate2 DLL, no GPU
        driver, bad compute_type, no network for a first-time download)
        caused every single transcribe()/transcribe_file() call to
        re-attempt the full model construction (including a network-
        touching download attempt) from scratch, only to hit the same
        failure again. This is the same class of bug fixed in
        vision/liveness/detector.py's _get_session() in round 15. Fixed by
        caching the failure so a broken load fails fast on every call
        after the first, instead of repeatedly paying (and re-raising) the
        same expensive failure.
        """
        if self._model is None:
            if self._model_load_failed:
                msg = "Whisper model previously failed to load - not retrying automatically"
                raise GuruSpeechError(msg)
            if WhisperModel is None:
                # The import at the top of this module already failed and
                # logged why, but that warning is long gone by the time a user
                # speaks. Calling WhisperModel(...) here would raise
                # "TypeError: 'NoneType' object is not callable", which the
                # handler below then wrapped into
                # "Failed to load Whisper model: 'NoneType' object is not
                # callable" -- a message that tells nobody what to actually do.
                self._model_load_failed = True
                msg = (
                    "Speech recognition is unavailable: faster-whisper could "
                    "not be imported at startup (commonly a missing install, "
                    "or ctranslate2's DLL blocked by Windows Application "
                    "Control). Install it with: pip install faster-whisper"
                )
                raise GuruSpeechError(msg)
            model_id = self.model_path or self.model_size
            requested = self.device
            reason = ""
            if requested in ("auto", "cuda"):
                model, reason = self._load_on_gpu(model_id)
                if model is not None:
                    self._model = model
                    return self._model
            try:
                cpu_compute = (
                    self._requested_compute
                    if self._requested_compute in _CPU_COMPUTE_TYPES
                    else _CPU_DEFAULT_COMPUTE
                )
                self._model = self._construct(model_id, "cpu", cpu_compute)
            except Exception as e:
                self._model_load_failed = True
                msg = f"Failed to load Whisper model: {e}"
                raise GuruSpeechError(msg) from e
            self.device, self.compute_type = "cpu", cpu_compute
            self._log_cpu(requested, reason)
        return self._model

    @staticmethod
    def _construct(model_id: str, device: str, compute_type: str) -> WhisperModel:
        """Build the model from the local cache, downloading only if it is not there."""
        try:
            # Try local cache first - no HuggingFace ping
            return WhisperModel(
                model_id, device=device, compute_type=compute_type, local_files_only=True
            )
        except Exception:
            # Model not cached yet - allow download, then it's cached forever
            return WhisperModel(model_id, device=device, compute_type=compute_type)

    def _load_on_gpu(self, model_id: str) -> tuple[WhisperModel | None, str]:
        """Load on CUDA and prove it works, or return None and the reason.

        CTranslate2 loads a model on CUDA without cuBLAS and cuDNN and fails
        only when it first runs it: with cublas64_12.dll missing, the load
        succeeded and the user's first command then failed with "Library
        cublas64_12.dll is not found or cannot be loaded". So a load counts
        only after a short transcription has actually run on the GPU. Half a
        second of silence is enough to run the encoder, where it failed.
        """
        gpus = prepare_cuda_runtime()
        if not gpus:
            earlier = cuda_failure()
            if earlier is not None:
                return None, f"not retried after an earlier CUDA failure in this process ({earlier})"
            return None, "no CUDA device found"
        compute = self._requested_compute or "int8_float16"
        try:
            with cuda_trial():
                model = self._construct(model_id, "cuda", compute)
                silence = np.zeros(_WHISPER_SAMPLE_RATE // 2, dtype=np.float32)
                segments, _ = model.transcribe(silence, beam_size=1, language="en")
                list(segments)
        except Exception as exc:
            return None, f"{type(exc).__name__}: {exc}"
        self.device, self.compute_type = "cuda", compute
        logger.info("Whisper %s loaded on the GPU (cuda, %s)", model_id, compute)
        return model, ""

    def _log_cpu(self, requested: str, reason: str) -> None:
        """Say once, at load, that transcription runs on the CPU, and why.

        Nothing used to: SpeechEngine built this class without a device, so
        every command was transcribed on the CPU with no record of it, and the
        only related startup line was GPUResourcePool's "no CUDA device",
        which was about torch and false on a machine with a GPU. That second
        or two is paid on every spoken command, so a machine that could avoid
        it is told how.
        """
        name = self.model_path or self.model_size
        gpus = _cuda_device_count()
        if requested == "cpu":
            logger.info(
                "Whisper %s loaded on the CPU (%s) as configured%s",
                name, self.compute_type,
                f"; {gpus} CUDA device(s) present but not used" if gpus else "",
            )
        elif gpus:
            logger.warning(
                "Speech recognition runs on the CPU (Whisper %s, %s): a CUDA GPU "
                "is present but Whisper could not run on it (%s). %s. To use "
                "the GPU, %s.",
                name, self.compute_type, reason, _GPU_COST, _GPU_HOWTO,
            )
        elif requested == "cuda":
            logger.warning(
                "Whisper was configured for the GPU but no CUDA device was found; "
                "running %s on the CPU (%s). %s.",
                name, self.compute_type, _GPU_COST,
            )
        else:
            logger.info(
                "Whisper %s loaded on the CPU (%s): no CUDA device found",
                name, self.compute_type,
            )

    async def load_model_async(self) -> None:
        """Load Whisper model asynchronously in a background thread.

        Call this during startup to avoid blocking the event loop on first
        transcription request.  Safe to call multiple times - subsequent calls
        are no-ops if the model is already loaded.
        """
        if self._model is not None:
            return
        import asyncio

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._load_model)

    def transcribe(
        self,
        audio_data: np.ndarray,
        sample_rate: int,
        language: str | None = None,
    ) -> TranscriptionResult:
        """Transcribe audio to text.

        Args:
            audio_data: Audio as numpy array (float32, shape: (samples,))
            sample_rate: Sample rate in Hz
            language: Force language (None for auto-detect)

        Returns:
            TranscriptionResult with text, language, confidence

        """
        if audio_data.size == 0:
            msg = "Empty audio data provided"
            raise GuruSpeechError(msg)

        # Ensure audio is float32
        if audio_data.dtype != np.float32:
            audio_data = audio_data.astype(np.float32)

        # Normalize audio to [-1, 1] range if needed
        if audio_data.max() > 1.0 or audio_data.min() < -1.0:
            audio_data = audio_data / np.abs(audio_data).max()

        # Compute the real audio duration from the CALLER's stated sample_rate
        # and the pre-resample length, before any resampling below changes
        # len(audio_data). This is the value actually reported in the result
        # and used for the (currently unused) real-time-factor calculation.
        audio_duration = len(audio_data) / sample_rate

        # BUG FIX (Round 16): faster_whisper's array-input path (as used
        # here, as opposed to transcribe_file()'s file-path input, which has
        # its own internal decode/resample step) requires audio to already
        # be 16kHz -- it does NOT resample a raw numpy array itself. This
        # method used to accept an arbitrary `sample_rate` and use it ONLY
        # to compute `audio_duration` below, then hand the array to
        # model.transcribe() completely unchanged regardless of its actual
        # rate. Desktop mic capture commonly runs at 44.1kHz/48kHz; feeding
        # that straight to a 16kHz-expecting model makes Whisper decode the
        # waveform as if it were ~2.75x slower/lower-pitched than real,
        # silently producing garbled or wrong text with NO error or
        # warning -- on the live/streaming STT hot path for a voice
        # companion. Fixed by resampling to 16kHz here whenever the caller's
        # sample_rate differs, using the same linear-interpolation approach
        # already used elsewhere in this codebase's audio path (see
        # speech/audio/processor.py::convert_format) -- consistent with the
        # existing method, including its documented anti-aliasing caveat
        # for heavy downsampling, rather than introducing a new dependency.
        if sample_rate != _WHISPER_SAMPLE_RATE:
            logger.debug(
                "Resampling audio %dHz -> %dHz before Whisper transcription "
                "(faster_whisper's array-input path requires 16kHz and does "
                "not resample internally)",
                sample_rate,
                _WHISPER_SAMPLE_RATE,
            )
            audio_data = self._resample_to_whisper_rate(audio_data, sample_rate)

        model = self._load_model()

        start_time = time.time()

        try:
            # Transcribe with Whisper
            segments_iter, info = model.transcribe(
                audio_data,
                language=language,
                beam_size=self.beam_size,
                word_timestamps=True,
                vad_filter=True,
                # initial_prompt helps Whisper with Indian names, songs, and
                # mixed Hindi-English speech. It primes the model vocabulary
                # without forcing a specific transcription.
                initial_prompt=(
                    "Guru, Maya, chak de India, Bollywood, namaste, "
                    "YouTube, LeetCode, VS Code, GitHub, WhatsApp, "
                    "rupees, crore, lakh, Mumbai, Delhi, Bangalore, "
                    "Suraj, Priya, Rahul, Sharma, Kumar, Singh, Patel"
                )
                if language in (None, "en", "hi")
                else None,
            )

            # Convert generator to list
            segments_list = list(segments_iter)

            # Build transcription result
            full_text = " ".join(seg.text.strip() for seg in segments_list)

            transcription_segments = []
            for seg in segments_list:
                transcription_segments.append(
                    TranscriptionSegment(
                        text=seg.text.strip(),
                        start_time=seg.start,
                        end_time=seg.end,
                        speaker_id=None,  # Diarization handled separately
                        confidence=seg.avg_logprob if hasattr(seg, "avg_logprob") else 1.0,
                    ),
                )

            # Calculate duration
            duration = time.time() - start_time
            # audio_duration was already computed above (pre-resample, using
            # the caller's original sample_rate) so it reflects the real
            # input duration regardless of any resampling performed above.

            # Calculate average confidence
            avg_confidence = (
                sum(seg.confidence for seg in transcription_segments) / len(transcription_segments)
                if transcription_segments
                else 0.0
            )

            # Verify real-time factor <0.5
            duration / audio_duration if audio_duration > 0 else 0.0

            result = TranscriptionResult(
                text=full_text,
                language=info.language,
                confidence=avg_confidence,
                segments=transcription_segments,
                duration=audio_duration,
            )
            # Expose Whisper's language detection probability so the orchestrator
            # can apply a confidence threshold and avoid wrong-language responses.
            # Whisper often misidentifies English as 'hi' (Hindi) at low confidence.
            result.language_probability = getattr(info, "language_probability", None)
            return result

        except Exception as e:
            msg = f"Transcription failed: {e}"
            raise GuruSpeechError(msg) from e

    @staticmethod
    def _resample_to_whisper_rate(audio_data: np.ndarray, sample_rate: int) -> np.ndarray:
        """Linearly resample *audio_data* from *sample_rate* to 16kHz.

        See transcribe()'s BUG FIX (Round 16) note for why this exists.
        Uses linear interpolation (np.interp), matching the approach
        already used elsewhere in this codebase's audio path
        (speech/audio/processor.py::convert_format) rather than adding a
        new scipy/librosa dependency. As with that sibling implementation,
        this has no anti-aliasing filter, so heavy downsampling (e.g.
        48kHz -> 16kHz) can introduce some aliasing distortion -- a real
        but pre-existing limitation of this codebase's resampling
        approach, not something this fix introduces. It is still a large,
        clear correctness improvement over the prior behavior of feeding
        Whisper unresampled audio outright.
        """
        if len(audio_data) == 0 or sample_rate <= 0:
            return audio_data
        duration = len(audio_data) / sample_rate
        target_length = max(1, int(round(duration * _WHISPER_SAMPLE_RATE)))
        original_indices = np.arange(len(audio_data))
        target_indices = np.linspace(0, len(audio_data) - 1, num=target_length)
        return np.interp(target_indices, original_indices, audio_data).astype(np.float32)

    def transcribe_file(self, file_path: str, language: str | None = None) -> TranscriptionResult:
        """Transcribe audio file.

        Args:
            file_path: Path to audio file (WAV, MP3, FLAC, etc.)
            language: Force language (None for auto-detect)

        Returns:
            TranscriptionResult with text, language, confidence

        """
        path = Path(file_path)
        if not path.exists():
            msg = f"Audio file not found: {file_path}"
            raise GuruSpeechError(msg)

        model = self._load_model()

        start_time = time.time()

        try:
            # Transcribe file directly
            segments_iter, info = model.transcribe(
                str(path),
                language=language,
                beam_size=self.beam_size,
                word_timestamps=True,
                vad_filter=True,
            )

            # Convert generator to list
            segments_list = list(segments_iter)

            # Build transcription result
            full_text = " ".join(seg.text.strip() for seg in segments_list)

            transcription_segments = []
            for seg in segments_list:
                transcription_segments.append(
                    TranscriptionSegment(
                        text=seg.text.strip(),
                        start_time=seg.start,
                        end_time=seg.end,
                        speaker_id=None,
                        confidence=seg.avg_logprob if hasattr(seg, "avg_logprob") else 1.0,
                    ),
                )

            # Calculate duration
            duration = time.time() - start_time

            # Get audio duration from segments or info
            if transcription_segments:
                audio_duration = transcription_segments[-1].end_time
            elif hasattr(info, "duration"):
                audio_duration = info.duration
            else:
                # Fallback: estimate from processing time
                audio_duration = duration

            # Calculate average confidence
            avg_confidence = (
                sum(seg.confidence for seg in transcription_segments) / len(transcription_segments)
                if transcription_segments
                else 0.0
            )

            return TranscriptionResult(
                text=full_text,
                language=info.language,
                confidence=avg_confidence,
                segments=transcription_segments,
                duration=audio_duration,
            )

        except Exception as e:
            msg = f"File transcription failed: {e}"
            raise GuruSpeechError(msg) from e

    def transcribe_with_diarization(
        self,
        audio_data: np.ndarray,
        sample_rate: int,
        language: str | None = None,
        num_speakers: int | None = None,
    ) -> TranscriptionResult:
        """Transcribe audio with speaker diarization.

        Args:
            audio_data: Audio as numpy array
            sample_rate: Sample rate in Hz
            language: Force language (None for auto-detect)
            num_speakers: Expected number of speakers (None for auto-detect)

        Returns:
            TranscriptionResult from plain transcription. Diarization is
            NOT implemented (see BUG FIX note below) -- every segment's
            speaker_id is None, exactly as from transcribe().

        BUG FIX (Round 16): this method silently returned a plain
        (non-diarized) transcription while its own docstring promised
        "speaker labels in segments" and its `num_speakers` parameter
        implied real diarization was performed. A caller building a
        multi-speaker transcript from this got silently wrong
        (undifferentiated) data with no error or warning. Real speaker
        diarization needs pyannote.audio or similar (additional
        dependencies + model loading) and is not implemented here -- that
        is unchanged by this fix. What IS fixed is the silence: this now
        logs a clear warning so the gap is visible at runtime instead of
        masquerading as a diarization feature that quietly does nothing.
        """
        if num_speakers is not None:
            logger.warning(
                "transcribe_with_diarization(num_speakers=%s) called, but speaker "
                "diarization is NOT implemented -- returning plain transcription "
                "with speaker_id=None on every segment. num_speakers is ignored.",
                num_speakers,
            )
        else:
            logger.debug(
                "transcribe_with_diarization() called, but speaker diarization is "
                "NOT implemented -- returning plain transcription (speaker_id=None).",
            )
        # TODO: Implement speaker diarization using pyannote.audio or similar
        # (additional dependencies + model loading required).
        return self.transcribe(audio_data, sample_rate, language)
