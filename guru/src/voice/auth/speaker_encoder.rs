//! Speaker Encoder
//! Extracts 256-d d-vectors from audio using LSTM.

use crate::intelligence::tensor::Tensor;



pub struct LSTMLayer {
    pub w_ih: Tensor,
    pub w_hh: Tensor,
    pub bias_ih: Option<Tensor>,
    pub bias_hh: Option<Tensor>,
    pub hidden_size: usize,
}

impl LSTMLayer {
    pub fn new(input_size: usize, hidden_size: usize) -> Self {
        // Gates: 4 * hidden
        Self {
            w_ih: Tensor::new(vec![0.0; 4 * hidden_size * input_size], vec![4 * hidden_size, input_size]), // Transpose logic in cell
            w_hh: Tensor::new(vec![0.0; 4 * hidden_size * hidden_size], vec![4 * hidden_size, hidden_size]),
            bias_ih: Some(Tensor::new(vec![0.0; 4 * hidden_size], vec![4 * hidden_size])),
            bias_hh: Some(Tensor::new(vec![0.0; 4 * hidden_size], vec![4 * hidden_size])),
            hidden_size,
        }
    }
    
    pub fn forward_sequence(&self, x: &Tensor) -> Tensor {
        // x: [Seq, Input] (Batch=1)
        let seq_len = x.shape[0];
        // let input_dim = x.shape[1];
        
        // Init states (zeros)
        // h, c: [1, Hidden]
        let mut h = Tensor::new(vec![0.0; self.hidden_size], vec![1, self.hidden_size]);
        let mut c = Tensor::new(vec![0.0; self.hidden_size], vec![1, self.hidden_size]);
        
        let mut outputs = Vec::with_capacity(seq_len * self.hidden_size);
        
        // Loop over seq
        // We need X sliced by row. `Tensor` assumes flat data.
        // We can optimize by pre-computing x @ W_ih.T for all time steps! (Speedup)
        // Gates_x = x @ W_ih.T -> [Seq, 4H]
        let gates_all = x.matmul(&self.w_ih.transpose());
        
        // Loop
        for t in 0..seq_len {
            // Extract gates_x[t]
            let row_start = t * 4 * self.hidden_size;
            let gates_x_t = Tensor::new(
                gates_all.data[row_start..row_start + 4 * self.hidden_size].to_vec(), 
                vec![1, 4 * self.hidden_size]
            );
            
            // LSTM Cell logic simplified (pre-computed x)
            // gates = gates_x_t + h @ W_hh.T + biases
            let gates_h = h.matmul(&self.w_hh.transpose());
            let mut gates = gates_x_t.add(&gates_h);
            
             // Add biases (broadcast)
            if let Some(ref b) = self.bias_ih {
                 for i in 0..gates.data.len() { gates.data[i] += b.data[i]; }
            }
            if let Some(ref b) = self.bias_hh {
                 for i in 0..gates.data.len() { gates.data[i] += b.data[i]; }
            }
            
            // Split and activation
            let (h_next, c_next) = self.compute_cell(&gates, &c);
            h = h_next;
            c = c_next;
            
            // Store h
            outputs.extend_from_slice(&h.data);
        }
        
        Tensor::new(outputs, vec![seq_len, self.hidden_size])
    }
    
    fn compute_cell(&self, gates: &Tensor, c_prev: &Tensor) -> (Tensor, Tensor) {
         // gates: [1, 4H]
         let g_data = &gates.data;
         let c_data = &c_prev.data;
         
         let hsize = self.hidden_size;
         let mut h_new = vec![0.0; hsize];
         let mut c_new = vec![0.0; hsize];
         
         for k in 0..hsize {
             let i_gate = 1.0 / (1.0 + (-g_data[k]).exp());
             let f_gate = 1.0 / (1.0 + (-g_data[hsize + k]).exp());
             let g_gate = g_data[2*hsize + k].tanh();
             let o_gate = 1.0 / (1.0 + (-g_data[3*hsize + k]).exp());
             
             let c_val = f_gate * c_data[k] + i_gate * g_gate;
             let h_val = o_gate * c_val.tanh();
             
             c_new[k] = c_val;
             h_new[k] = h_val;
         }
         
         (Tensor::new(h_new, vec![1, hsize]), Tensor::new(c_new, vec![1, hsize]))
    }
}

pub struct SpeakerEncoder {
    lstm1: LSTMLayer,
    lstm2: LSTMLayer,
    lstm3: LSTMLayer,
    projection: Tensor, // Linear [256, 256] -> [Hidden, Emb]
    projection_bias: Option<Tensor>,
}

impl Default for SpeakerEncoder {
    fn default() -> Self {
        Self::new()
    }
}

impl SpeakerEncoder {
    pub fn new() -> Self {
        // Hyperparams: Input 80, Hidden 256, Emb 256, Layers 3
        Self {
            lstm1: LSTMLayer::new(80, 256),
            lstm2: LSTMLayer::new(256, 256),
            lstm3: LSTMLayer::new(256, 256),
            projection: Tensor::new(vec![0.0; 256*256], vec![256, 256]), // [Out, In]
            projection_bias: Some(Tensor::new(vec![0.0; 256], vec![256])),
        }
    }
    
    pub fn embed(&self, mels: &Tensor) -> Tensor {
        // mels: [1, 80, Seq] -> Transpose to [Seq, 80] ?
        // AudioFeatureExtractor output is [n_mels, n_frames].
        // We need [Seq, Input].
        // So transpose.
        
        // Check shape: [Mel, Seq]
        // If 2D: [80, Seq].
        let x = if mels.shape[0] == 80 { mels.transpose() } else { mels.clone() };
        
        // LSTM 1
        let h1 = self.lstm1.forward_sequence(&x); // [Seq, 256]
        
        // LSTM 2
        let h2 = self.lstm2.forward_sequence(&h1);
        
        // LSTM 3
        let h3 = self.lstm3.forward_sequence(&h2);
        
        // Last frame? Or Mean?
        // Resemblyzer uses partials.
        // For simple verification, Last Frame of H3 is standard d-vector baseline.
        // Let's take Last Frame.
        let seq_len = h3.shape[0];
        let last_idx = (seq_len - 1) * 256;
        let last_frame_data = h3.data[last_idx .. last_idx+256].to_vec();
        let last_frame = Tensor::new(last_frame_data, vec![1, 256]); // [1, 256]
        
        // Linear Projection
        // last_frame [1, 256] @ proj.T [256, 256] + bias
        let mut emb = last_frame.matmul(&self.projection.transpose());
        if let Some(ref b) = self.projection_bias {
             for i in 0..256 {
                 emb.data[i] += b.data[i];
             }
        }
        
        // L2 Normalize
        let norm = emb.data.iter().map(|x| x*x).sum::<f32>().sqrt();
        let normalized = emb.data.iter().map(|x| x / (norm + 1e-6)).collect();
        
        Tensor::new(normalized, vec![256])
    }
}

