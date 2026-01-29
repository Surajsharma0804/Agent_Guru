use crate::intelligence::tensor::Tensor;
use super::acoustic_model::Whisper;
use super::tokenizer::Tokenizer;

pub struct Decoder {
    model: Whisper,
    tokenizer: Tokenizer,
}

impl Decoder {
    pub fn new(model: Whisper, tokenizer: Tokenizer) -> Self {
        Self { model, tokenizer }
    }

    pub fn decode_greedy(&self, audio_features: &Tensor, max_tokens: usize) -> String {
        // 1. Encoder Forward
        let encoded = self.model.embed_audio(audio_features);

        // 2. Init tokens with SOT (Start of Transcript)
        // TODO: Get SOT ID from tokenizer (usually 50258)
        let mut tokens: Vec<usize> = vec![50258]; 

        for _ in 0..max_tokens {
            // Prepare input tensor [1, seq_len]
            // We need to convert Vec<usize> to Vec<f32> for Tensor (stub casting)
            let input_data: Vec<f32> = tokens.iter().map(|&x| x as f32).collect(); 
            let input = Tensor::new(input_data, vec![1, tokens.len()]);

            // Decoder Forward
            let logits = self.model.logits(&input, &encoded);
            
            // Logits shape: [1, seq_len, vocab_size]
            // We want last token logits
            let shape = logits.shape();
            let seq_len = shape[1];
            let vocab_size = shape[2];
            
            // Extract last row
            let start_idx = (seq_len - 1) * vocab_size;
            let last_logits = &logits.data[start_idx..start_idx + vocab_size];
            
            // Argmax
            let mut best_idx = 0;
            let mut max_val = std::f32::NEG_INFINITY;
            
            for (i, &val) in last_logits.iter().enumerate() {
                if val > max_val {
                    max_val = val;
                    best_idx = i;
                }
            }
            
            tokens.push(best_idx);
            
            // Check for EOT (End of Text) - usually 50257
            if best_idx == 50257 {
                break;
            }
        }
        
        self.tokenizer.decode(&tokens)
    }
}
