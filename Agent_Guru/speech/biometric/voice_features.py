"""Voice biometric feature extraction for authentication.

This module extracts voice biometric features that are passed to the
guru-security-cryptography system for authentication. It does NOT perform
authentication itself.
"""

import logging

import numpy as np
from scipy.signal import butter, filtfilt

from Agent_Guru.speech.exceptions import VoiceBiometricError
from Agent_Guru.speech.models import VoiceFeatures

logger = logging.getLogger(__name__)

# Per-coefficient divisors that bring librosa's MFCCs onto an O(1) scale.
# Index 0 is the log-energy term and runs an order of magnitude larger than
# the rest, so it gets its own divisor rather than swamping them.
_MFCC_SCALE = np.concatenate([[500.0], np.full(127, 100.0)])


class VoiceFeatureExtractor:
    """Extracts voice biometric features for security system.

    This component extracts features from voice audio that can be used
    for biometric authentication. The actual authentication is performed
    by the guru-security-cryptography system.

    Features extracted include:
    - MFCC (Mel-Frequency Cepstral Coefficients)
    - Pitch characteristics
    - Formant frequencies
    - Speaking rate
    - Energy distribution
    """

    def __init__(self, model_path: str | None = None) -> None:
        """Initialize voice feature extractor.

        Args:
            model_path: Path to feature extraction model (optional)

        """
        self.model_path = model_path
        self.n_mfcc = 20  # Number of MFCC coefficients
        self.n_fft = 2048
        self.hop_length = 512

    async def extract_features(self, audio: np.ndarray, sample_rate: int) -> VoiceFeatures:
        """Extract voice biometric features from audio.

        Features are passed to guru-security-cryptography for authentication.
        This method does NOT perform authentication.

        Args:
            audio: Audio data as numpy array
            sample_rate: Sample rate in Hz

        Returns:
            VoiceFeatures with feature vector and metadata

        Raises:
            VoiceBiometricError: If feature extraction fails

        """
        try:
            # Validate input
            if len(audio) == 0:
                msg = "Audio data is empty"
                raise VoiceBiometricError(msg)

            if sample_rate <= 0:
                msg = f"Invalid sample rate: {sample_rate}"
                raise VoiceBiometricError(msg)

            # librosa is an optional extra, imported here and not at module
            # scope. At module scope its absence broke `import
            # Agent_Guru.speech.biometric` and, because speech/engine.py
            # imports this module at load time, SpeechEngine as well: a
            # machine without librosa could not start speech at all, and five
            # test files failed to even collect. Imported here, a missing
            # librosa surfaces as the VoiceBiometricError this method already
            # promises, naming the module, only on the path that needs it.
            # It comes after the input checks so a bad argument is still
            # reported as itself rather than as a missing package.
            import librosa

            # Ensure audio is float32
            if audio.dtype != np.float32:
                audio = audio.astype(np.float32)

            # Normalize audio
            if np.max(np.abs(audio)) > 0:
                audio = audio / np.max(np.abs(audio))

            # Extract features
            features = []

            # Adjust n_fft and hop_length for short audio to prevent warnings
            audio_length = len(audio)
            n_fft_adjusted = min(self.n_fft, audio_length)
            if n_fft_adjusted < 2:
                n_fft_adjusted = 2
            else:
                # Round down to nearest power of 2
                n_fft_adjusted = 2 ** int(np.log2(n_fft_adjusted))

            hop_length_adjusted = min(self.hop_length, n_fft_adjusted // 4)
            hop_length_adjusted = max(hop_length_adjusted, 1)

            # Suppress librosa warnings for short audio
            import warnings

            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", message="n_fft=.*is too large")
                warnings.filterwarnings("ignore", category=UserWarning, module="librosa")

                # PERFORMANCE: compute the magnitude STFT ONCE and feed it to
                # every consumer below.
                #
                # librosa.feature.mfcc(y=...), librosa.piptrack(y=...),
                # spectral_centroid(y=...) and spectral_rolloff(y=...) each run
                # their own STFT internally when handed a waveform. Profiling this
                # function on 10 s of 16 kHz audio showed librosa._spectrogram
                # entered 4x per call, 0.101 s of a 0.185 s total - 55% of the
                # work was three redundant transforms of the same samples.
                #
                # Passing S= to each one is bit-for-bit identical (verified:
                # max|diff| == 0.0 for all five outputs), because these are
                # exactly the spectrograms librosa would have computed itself:
                # magnitude for piptrack/centroid/rolloff, power (S**2) for the
                # mel filterbank behind MFCC.
                #
                # Measured: 37.90 ms -> 24.18 ms per call (1.57x).
                stft_magnitude = np.abs(
                    librosa.stft(
                        y=audio,
                        n_fft=n_fft_adjusted,
                        hop_length=hop_length_adjusted,
                    ),
                )

                # 1. MFCC features (primary biometric features)
                mel_power = librosa.feature.melspectrogram(
                    S=stft_magnitude**2,
                    sr=sample_rate,
                    n_fft=n_fft_adjusted,
                    hop_length=hop_length_adjusted,
                )
                mfcc = librosa.feature.mfcc(
                    S=librosa.power_to_db(mel_power),
                    n_mfcc=self.n_mfcc,
                )
            # Use mean and std of MFCCs
            mfcc_mean = np.mean(mfcc, axis=1)
            mfcc_std = np.std(mfcc, axis=1)
            # MFCC-0 carries overall log-energy and is an order of magnitude
            # larger than the rest; scaled separately so it does not swamp the
            # coefficients that actually characterise a voice.
            features.extend(mfcc_mean / _MFCC_SCALE[: len(mfcc_mean)])
            features.extend(mfcc_std / _MFCC_SCALE[: len(mfcc_std)])

            # 2. Pitch features
            pitches, magnitudes = librosa.piptrack(
                S=stft_magnitude,
                sr=sample_rate,
                n_fft=n_fft_adjusted,
                hop_length=hop_length_adjusted,
            )
            # Extract pitch statistics. Vectorised - this was a per-frame
            # Python loop doing an argmax and a list append for every STFT
            # frame of every enrolment and every authentication attempt.
            peak_bins = magnitudes.argmax(axis=0)
            frame_pitches = pitches[peak_bins, np.arange(pitches.shape[1])]
            pitch_values = frame_pitches[frame_pitches > 0]

            if pitch_values.size:
                pitch_mean = np.mean(pitch_values)
                pitch_std = np.std(pitch_values)
                pitch_min = np.min(pitch_values)
                pitch_max = np.max(pitch_values)
            else:
                pitch_mean = pitch_std = pitch_min = pitch_max = 0.0

            # Hz values are divided by Nyquist so they land in [0, 1] like
            # every other component -- see the note above feature_vector.
            nyquist = sample_rate / 2.0
            features.extend(
                [
                    pitch_mean / nyquist,
                    pitch_std / nyquist,
                    pitch_min / nyquist,
                    pitch_max / nyquist,
                ],
            )

            # 3. Spectral features
            spectral_centroid = librosa.feature.spectral_centroid(
                S=stft_magnitude,
                sr=sample_rate,
                n_fft=n_fft_adjusted,
                hop_length=hop_length_adjusted,
            )
            spectral_rolloff = librosa.feature.spectral_rolloff(
                S=stft_magnitude,
                sr=sample_rate,
                n_fft=n_fft_adjusted,
                hop_length=hop_length_adjusted,
            )

            features.append(np.mean(spectral_centroid) / nyquist)
            features.append(np.std(spectral_centroid) / nyquist)
            features.append(np.mean(spectral_rolloff) / nyquist)
            features.append(np.std(spectral_rolloff) / nyquist)

            # 4. Zero crossing rate (speaking style)
            zcr = librosa.feature.zero_crossing_rate(
                audio,
                frame_length=n_fft_adjusted,
                hop_length=hop_length_adjusted,
            )
            features.append(np.mean(zcr))
            features.append(np.std(zcr))

            # 5. Energy features
            rms = librosa.feature.rms(
                y=audio,
                frame_length=n_fft_adjusted,
                hop_length=hop_length_adjusted,
            )
            features.append(np.mean(rms))
            features.append(np.std(rms))

            # End of warnings suppression context
            # Convert to numpy array
            feature_vector = np.array(features, dtype=np.float32)

            # SECURITY FIX: L2-normalise the assembled vector.
            #
            # These 52 components were previously concatenated in their raw,
            # wildly different units: MFCCs O(1-100), pitch and spectral
            # values in HERTZ (O(100-7000)), ZCR and RMS O(0.01). Two
            # Hz-valued components dominated completely -- spectral-rolloff
            # mean alone measured 6806, 59% of the vector's total L1 mass --
            # and they barely move between speakers.
            #
            # VoiceAuthenticator compares templates with COSINE SIMILARITY
            # against a 0.97 biometric threshold. With the vector dominated by
            # two near-constant components, every pair of voices scored
            # ~0.9998, so the threshold separated nobody from anybody.
            # Measured against the real authenticator before this fix:
            # enrol a 105 Hz speaker, then authenticate a 210 Hz speaker --
            # an octave apart, plainly a different person -- and it passed
            # with similarity 0.999857. Every impostor passed. Raising the
            # threshold could not help: there was no margin left to raise it
            # into, and the ordering was not even reliable.
            #
            # The discriminative information was present all along: z-scoring
            # the same vectors separated 90 Hz from 210 Hz at -0.78. It was
            # simply invisible to cosine. Scaling each group into comparable
            # units (above) and normalising here makes the whole vector count.
            #
            # Profiles are held in memory and rebuilt per process
            # (VoiceAuthenticator._profiles), so no stored template is
            # invalidated by the change in numerics.
            norm = float(np.linalg.norm(feature_vector))
            if norm > 0.0:
                feature_vector = (feature_vector / norm).astype(np.float32)

            # Compute quality score
            quality_score = self.compute_quality_score(audio, sample_rate)

            # Compute duration
            duration = len(audio) / sample_rate

            # Liveness detection - required by BiometricAuthenticator (Req 12)
            is_live, liveness_score = self.detect_liveness(audio, sample_rate)

            return VoiceFeatures(
                feature_vector=feature_vector,
                sample_rate=sample_rate,
                duration=duration,
                quality_score=quality_score,
                liveness_score=liveness_score,
                is_live=is_live,
            )

        except Exception as e:
            if isinstance(e, VoiceBiometricError):
                raise
            msg = f"Feature extraction failed: {e!s}"
            raise VoiceBiometricError(msg) from e

    def compute_quality_score(self, audio: np.ndarray, sample_rate: int | None = None) -> float:
        """Compute quality score for voice sample.

        Considers SNR, duration, and voice activity.

        Args:
            audio: Audio data as numpy array
            sample_rate: Sample rate in Hz (optional, used for duration check)

        Returns:
            Quality score between 0.0 and 1.0

        """
        try:
            if len(audio) == 0:
                return 0.0

            # Ensure audio is float
            if audio.dtype != np.float32:
                audio = audio.astype(np.float32)

            scores = []

            # 1. SNR estimation (signal-to-noise ratio)
            # Use energy-based approach
            energy = np.sum(audio**2) / len(audio)
            if energy > 0:
                # Estimate noise from low-energy frames
                frame_size = 512
                frame_energies = []
                for i in range(0, len(audio) - frame_size, frame_size):
                    frame = audio[i : i + frame_size]
                    frame_energy = np.sum(frame**2) / len(frame)
                    frame_energies.append(frame_energy)

                if frame_energies:
                    # Assume bottom 20% of frames are noise
                    sorted_energies = sorted(frame_energies)
                    noise_threshold = int(len(sorted_energies) * 0.2)
                    if noise_threshold > 0:
                        noise_energy = np.mean(sorted_energies[:noise_threshold])
                        if noise_energy > 0:
                            snr = 10 * np.log10(energy / noise_energy)
                            # Map SNR to 0-1 (assume 0dB = 0.0, 30dB+ = 1.0)
                            snr_score = np.clip(snr / 30.0, 0.0, 1.0)
                            scores.append(snr_score)

            # 2. Duration check (if sample_rate provided)
            if sample_rate is not None:
                duration = len(audio) / sample_rate
                # Optimal duration: 1-5 seconds
                if duration < 0.5:
                    duration_score = duration / 0.5
                elif duration > 5.0:
                    duration_score = max(0.5, 1.0 - (duration - 5.0) / 10.0)
                else:
                    duration_score = 1.0
                scores.append(duration_score)

            # 3. Voice activity (non-silence ratio)
            # Use energy threshold
            threshold = np.max(np.abs(audio)) * 0.1
            voice_frames = np.sum(np.abs(audio) > threshold)
            voice_ratio = voice_frames / len(audio)
            # Optimal: 50-90% voice activity
            if voice_ratio < 0.3:
                voice_score = voice_ratio / 0.3
            elif voice_ratio > 0.95:
                voice_score = 0.8  # Too much activity might be noise
            else:
                voice_score = 1.0
            scores.append(voice_score)

            # 4. Clipping detection
            max_val = np.max(np.abs(audio))
            if max_val >= 0.99:
                clipping_score = 0.5  # Penalize clipping
            else:
                clipping_score = 1.0
            scores.append(clipping_score)

            # Return average of all scores
            if scores:
                return float(np.mean(scores))
            return 0.5  # Default moderate quality

        except Exception:
            # This runs on the voice-biometric path. Returning a neutral 0.5
            # silently made a CRASH indistinguishable from a genuine
            # "moderate quality" measurement, both to the caller and in the
            # logs - so a systematic failure of quality scoring would have
            # looked exactly like a room full of mediocre microphones. The
            # fallback value is unchanged; it is now traceable.
            logger.exception("Voice quality scoring failed; returning neutral 0.5")
            return 0.5  # Return moderate quality on error

    def detect_liveness(self, audio: np.ndarray, sample_rate: int) -> tuple[bool, float]:
        """Detect if audio is from a live speaker (anti-spoofing).

        Detects recorded or synthesized voice attempts.

        Args:
            audio: Audio data as numpy array
            sample_rate: Sample rate in Hz

        Returns:
            Tuple of (is_live, confidence)
            - is_live: True if audio appears to be from live speaker
            - confidence: Confidence score between 0.0 and 1.0

        """
        try:
            if len(audio) == 0:
                return False, 0.0

            # Lazy for the reason given in extract_features, and after the
            # empty check so empty input keeps its definite 0.0 verdict. A
            # missing librosa lands in the except below and fails closed.
            import librosa

            # Ensure audio is float32
            if audio.dtype != np.float32:
                audio = audio.astype(np.float32)

            liveness_scores = []

            # 1. High-frequency content analysis
            # Recorded/synthesized audio often lacks high-frequency content
            # Apply high-pass filter
            nyquist = sample_rate / 2
            cutoff = 4000  # 4kHz
            if cutoff < nyquist:
                b, a = butter(4, cutoff / nyquist, btype="high")
                high_freq = filtfilt(b, a, audio)

                # Compare energy in high frequencies
                high_energy = np.sum(high_freq**2)
                total_energy = np.sum(audio**2)

                if total_energy > 0:
                    high_ratio = high_energy / total_energy
                    # Live speech typically has 5-20% energy in high frequencies
                    if 0.05 <= high_ratio <= 0.30:
                        liveness_scores.append(1.0)
                    elif high_ratio < 0.02:
                        liveness_scores.append(0.3)  # Likely recorded/synthesized
                    else:
                        liveness_scores.append(0.7)

            # 2. Spectral flux (naturalness of transitions)
            # Synthesized speech has more uniform transitions
            # Adjust n_fft for short audio
            audio_length = len(audio)
            n_fft_flux = min(self.n_fft, audio_length)
            n_fft_flux = 2 if n_fft_flux < 2 else 2 ** int(np.log2(n_fft_flux))

            hop_length_flux = min(self.hop_length, n_fft_flux // 4)
            hop_length_flux = max(hop_length_flux, 1)

            import warnings

            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", message="n_fft=.*is too large")
                warnings.filterwarnings("ignore", category=UserWarning, module="librosa")

                spec = np.abs(librosa.stft(audio, n_fft=n_fft_flux, hop_length=hop_length_flux))
            spectral_flux = np.sum(np.diff(spec, axis=1) ** 2, axis=0)
            flux_variance = np.var(spectral_flux)

            # Natural speech has higher variance in spectral flux
            # Normalize by mean to get coefficient of variation
            flux_mean = np.mean(spectral_flux)
            if flux_mean > 0:
                flux_cv = np.sqrt(flux_variance) / flux_mean
                # Higher CV indicates more natural speech
                flux_score = np.clip(flux_cv / 2.0, 0.0, 1.0)
                liveness_scores.append(flux_score)

            # 3. Pitch naturalness
            # Synthesized speech often has too-regular pitch
            pitches, magnitudes = librosa.piptrack(
                y=audio,
                sr=sample_rate,
                n_fft=n_fft_flux,
                hop_length=hop_length_flux,
            )

            pitch_values = []
            for t in range(pitches.shape[1]):
                index = magnitudes[:, t].argmax()
                pitch = pitches[index, t]
                if pitch > 0:
                    pitch_values.append(pitch)

            if len(pitch_values) > 10:
                # Check pitch variation
                pitch_std = np.std(pitch_values)
                pitch_mean = np.mean(pitch_values)
                if pitch_mean > 0:
                    pitch_cv = pitch_std / pitch_mean
                    # Natural speech has CV around 0.05-0.4
                    # More lenient range to accommodate various voice types
                    if 0.02 <= pitch_cv <= 0.5:
                        liveness_scores.append(0.8)
                    elif pitch_cv < 0.01:
                        liveness_scores.append(0.3)  # Too regular
                    else:
                        liveness_scores.append(0.6)

            # Calculate overall liveness
            if liveness_scores:
                confidence = float(np.mean(liveness_scores))
                is_live = confidence >= 0.55  # Slightly lower threshold for better sensitivity

                return is_live, confidence
            return False, 0.5  # Uncertain

        except Exception:
            # Anti-spoofing. A liveness check that fails silently and reports
            # "uncertain" is exactly the state an attacker would try to
            # induce, and with no log there was nothing to notice it by. The
            # returned verdict is unchanged - fail closed, is_live=False - but
            # the failure is now recorded.
            logger.exception("Liveness detection failed; reporting not-live/uncertain")
            return False, 0.5  # Return uncertain on error
