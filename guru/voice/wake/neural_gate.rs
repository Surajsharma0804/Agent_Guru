use std::collections::VecDeque;

const PREDICTION_BUFFER_SIZE: usize = 30;
const WARMUP_FRAMES: usize = 5;

pub struct NeuralGate {
    prediction_buffer: VecDeque<f32>,
    frame_count: usize,
    last_detection_time: Option<std::time::Instant>,
}

impl NeuralGate {
    pub fn new() -> Self {
        Self {
            prediction_buffer: VecDeque::with_capacity(PREDICTION_BUFFER_SIZE),
            frame_count: 0,
            last_detection_time: None,
        }
    }

    pub fn reset(&mut self) {
        self.prediction_buffer.clear();
        self.frame_count = 0;
        self.last_detection_time = None;
    }

    /// Apply confidence thresholding with patience
    pub fn apply_threshold(
        &mut self,
        score: f32,
        threshold: f32,
        patience: usize,
    ) -> f32 {
        self.prediction_buffer.push_back(score);
        if self.prediction_buffer.len() > PREDICTION_BUFFER_SIZE {
            self.prediction_buffer.pop_front();
        }

        self.frame_count += 1;

        // Warmup: zero predictions for first 5 frames
        if self.frame_count < WARMUP_FRAMES {
            return 0.0;
        }

        // Patience: require N consecutive frames above threshold
        if patience > 0 {
            let recent: Vec<f32> = self.prediction_buffer
                .iter()
                .rev()
                .take(patience)
                .copied()
                .collect();
            
            let above_threshold = recent.iter().filter(|&&s| s >= threshold).count();
            if above_threshold < patience {
                return 0.0;
            }
        }

        score
    }

    /// Apply debounce (suppress detections within time window)
    pub fn apply_debounce(
        &mut self,
        score: f32,
        threshold: f32,
        debounce_seconds: f32,
    ) -> f32 {
        if score >= threshold {
            if let Some(last_time) = self.last_detection_time {
                let elapsed = last_time.elapsed().as_secs_f32();
                if elapsed < debounce_seconds {
                    return 0.0;
                }
            }
            self.last_detection_time = Some(std::time::Instant::now());
        }
        score
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_warmup() {
        let mut gate = NeuralGate::new();
        for _ in 0..WARMUP_FRAMES {
            assert_eq!(gate.apply_threshold(0.9, 0.5, 0), 0.0);
        }
    }
}
