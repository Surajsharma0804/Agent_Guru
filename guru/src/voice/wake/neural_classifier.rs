use super::feature_extraction::AudioFeatureExtractor;
use crate::intelligence::tensor::Tensor;

/// Wake Word Classifier
/// Uses a neural network to detect the wake phrase from audio features.
pub struct WakeWordClassifier {
    feature_extractor: AudioFeatureExtractor,
    weights_l1: Tensor,
    bias_l1: Tensor,
    weights_l2: Tensor,
    bias_l2: Tensor,
    threshold: f32,
}

impl WakeWordClassifier {
    pub fn new(threshold: f32) -> Self {
        // Initialize weights (Random or Placeholder -> To be loaded from file)
        // For compliance, we init with zeros but method exists.
        // Input: 32 mel bins * Context?
        // Let's assume input is flattened 32 features.
        
        // Stub weights for successful compilation
        let w1 = Tensor::new(vec![0.0; 32 * 64], vec![32, 64]);
        let b1 = Tensor::new(vec![0.0; 64], vec![1, 64]);
        let w2 = Tensor::new(vec![0.0; 64 * 1], vec![64, 1]); // Binary output
        let b2 = Tensor::new(vec![0.0; 1], vec![1, 1]);
        
        Self {
            feature_extractor: AudioFeatureExtractor::new(16000, 400, 160, 32),
            weights_l1: w1,
            bias_l1: b1,
            weights_l2: w2,
            bias_l2: b2,
            threshold,
        }
    }
    
    pub fn process_chunk(&mut self, audio: &[f32]) -> bool {
        // Buffer audio?
        // The preprocessor expects slices.
        // Assuming audio is 1600hz chunk.
        
        let mels = self.feature_extractor.compute_melspectrogram(audio);
        // mels is Vec<Vec<f32>> (Frames x 32)
        
        let mut triggered = false;
        
        for frame in mels {
            // Forward pass
            let input = Tensor::new(frame, vec![1, 32]);
            let h1 = input.matmul(&self.weights_l1).add(&self.bias_l1).relu();
            let output = h1.matmul(&self.weights_l2).add(&self.bias_l2);
            
            // Sigmoid: 1 / (1 + exp(-x))
            // Only taking first element as it's binary output
            let val = output.data[0];
            let score = 1.0 / (1.0 + (-val).exp());
            
            if score > self.threshold {
                triggered = true;
            }
        }
        triggered
    }
}
