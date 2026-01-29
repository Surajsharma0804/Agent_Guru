use crate::voice::wake::feature_extraction::AudioFeatureExtractor;

pub struct AudioProcessor {
    extractor: AudioFeatureExtractor,
    n_samples: usize,
}

impl Default for AudioProcessor {
    fn default() -> Self {
        Self::new()
    }
}

impl AudioProcessor {
    pub fn new() -> Self {
        // Whisper defaults
        Self {
            extractor: AudioFeatureExtractor::new(16000, 400, 160, 80),
            n_samples: 16000 * 30, // 30 seconds
        }
    }

    pub fn process(&self, audio: &[f32]) -> crate::intelligence::tensor::Tensor {
        // 1. Pad or Trim to 30s
        let mut padded = audio.to_vec();
        if padded.len() > self.n_samples {
            padded.truncate(self.n_samples);
        } else if padded.len() < self.n_samples {
            padded.resize(self.n_samples, 0.0);
        }

        // 2. Compute Mel Spectrogram
        // Returns Vec<Vec<f32>> [Frames, n_mels]
        let mels = self.extractor.compute_melspectrogram(&padded);
        
        // 3. Flatten and Normalize
        // Whisper: (log_spec + 4.0) / 4.0
        // And clamp range.
        
        // Transpose to [n_mels, n_frames] as expected by Conv1d
        let n_frames = mels.len();
        let n_mels = 80;
        
        let mut max_log_spec = -1e20f32; // Simulating global max tracker if needed (per sample)
        
        // First pass to get log spec and max
        let mut log_mels = vec![0.0; n_frames * n_mels];
        
        for (i, frame) in mels.iter().enumerate() {
            for (j, &val) in frame.iter().enumerate() {
                let log_val = val.max(1e-10f32).log10();
                log_mels[j * n_frames + i] = log_val; // Transposed layout for Tensor [Mels, Frames]
                if log_val > max_log_spec {
                    max_log_spec = log_val;
                }
            }
        }
        
        // Second pass normalize
        for val in log_mels.iter_mut() {
            *val = val.max(max_log_spec - 8.0f32);
            *val = (*val + 4.0f32) / 4.0f32;
        }

        use crate::intelligence::tensor::Tensor;
        Tensor::new(log_mels, vec![1, n_mels, n_frames]) // Batch=1, Channels=80, Len=3000
    }
}
