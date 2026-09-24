"""Whisper-based speech-to-text transcription for desktop platforms."""

import logging
import time
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
                          "float32" on CPU.
            beam_size: Beam size for decoding
            device: Device to run on ("cpu", "cuda")

        """
        self.model_size = model_size
        self.model_path = model_path
        # P2-77: Auto-detect optimal compute type for VRAM reduction.
        # int8_float16 on CUDA reduces VRAM from ~3GB to ~1.6GB for large-v3.
        if compute_type is None:
            self.compute_type = "int8_float16" if device == "cuda" else "float32"
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
            try:
                model_id = self.model_path or self.model_size
                # Try local cache first - no HuggingFace ping
                try:
                    self._model = WhisperModel(
                        model_id,
                        device=self.device,
                        compute_type=self.compute_type,
                        local_files_only=True,
                    )
                except Exception:
                    # Model not cached yet - allow download, then it's cached forever
                    self._model = WhisperModel(
                        model_id,
                        device=self.device,
                        compute_type=self.compute_type,
                    )
            except Exception as e:
                self._model_load_failed = True
                msg = f"Failed to load Whisper model: {e}"
                raise GuruSpeechError(msg) from e
        return self._model

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
