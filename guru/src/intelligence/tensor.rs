use std::f32::consts::PI;

/// Sovereign Tensor Engine
/// A minimal, dependency-free tensor library for inference.
#[derive(Debug, Clone)]
pub struct Tensor {
    pub data: Vec<f32>,
    pub shape: Vec<usize>,
}

impl Tensor {
    pub fn new(data: Vec<f32>, shape: Vec<usize>) -> Self {
        // Assert data len matches shape product
        let len: usize = shape.iter().product();
        assert_eq!(data.len(), len, "Data length does not match shape product");
        Self { data, shape }
    }

    pub fn zeros(shape: Vec<usize>) -> Self {
        let len: usize = shape.iter().product();
        Self::new(vec![0.0; len], shape)
    }

    pub fn shape(&self) -> &[usize] {
        &self.shape
    }

    // --- Basic Ops ---

    pub fn add(&self, other: &Self) -> Self {
        // Naive broadcasting not supported yet vs strict matching
        assert_eq!(self.shape, other.shape, "Shapes must match for add");
        let data: Vec<f32> = self.data.iter().zip(&other.data).map(|(a, b)| a + b).collect();
        Self::new(data, self.shape.clone())
    }

    pub fn mul(&self, other: &Self) -> Self {
        // Element-wise multiplication
        assert_eq!(self.shape, other.shape, "Shapes must match for mul");
        let data: Vec<f32> = self.data.iter().zip(&other.data).map(|(a, b)| a * b).collect();
        Self::new(data, self.shape.clone())
    }

    pub fn matmul(&self, other: &Self) -> Self {
        // Support 2D matmul for now (Batching later)
        // A(M, K) @ B(K, N) -> C(M, N)
        assert_eq!(self.shape.len(), 2);
        assert_eq!(other.shape.len(), 2);
        let m = self.shape[0];
        let k_dim = self.shape[1];
        let n = other.shape[1];
        assert_eq!(k_dim, other.shape[0], "Dim mismatch for matmul");

        let mut out = vec![0.0; m * n];
        
        // Naive O(N^3)
        for i in 0..m {
            for j in 0..n {
                let mut sum = 0.0;
                for k in 0..k_dim {
                    sum += self.data[i * k_dim + k] * other.data[k * n + j];
                }
                out[i * n + j] = sum;
            }
        }
        
        Self::new(out, vec![m, n])
    }

    pub fn transpose(&self) -> Self {
        // Only 2D transpose for now
        assert_eq!(self.shape.len(), 2);
        let rows = self.shape[0];
        let cols = self.shape[1];
        
        let mut out = vec![0.0; self.data.len()];
        for i in 0..rows {
            for j in 0..cols {
                out[j * rows + i] = self.data[i * cols + j];
            }
        }
        Self::new(out, vec![cols, rows])
    }

    // --- Activations & Norm ---

    pub fn gelu(&self) -> Self {
        // Approx: 0.5 * x * (1 + tanh(sqrt(2/pi) * (x + 0.044715 * x^3)))
        let sqrt_2_over_pi = (2.0f32 / PI).sqrt();
        let data: Vec<f32> = self.data.iter().map(|&x| {
            let val = sqrt_2_over_pi * (x + 0.044715f32 * x.powi(3));
            0.5f32 * x * (1.0f32 + val.tanh())
        }).collect();
        Self::new(data, self.shape.clone())
    }
    
    pub fn sigmoid(&self) -> Self {
        let data: Vec<f32> = self.data.iter().map(|&x| {
            1.0f32 / (1.0f32 + (-x).exp())
        }).collect();
        Self::new(data, self.shape.clone())
    }

    pub fn tanh(&self) -> Self {
        let data: Vec<f32> = self.data.iter().map(|&x| x.tanh()).collect();
        Self::new(data, self.shape.clone())
    }
    
    // Quick helper for RELU (legacy support)
    pub fn relu(&self) -> Self {
        let data: Vec<f32> = self.data.iter().map(|&x| if x > 0.0f32 { x } else { 0.0f32 }).collect();
        Self::new(data, self.shape.clone())
    }

    pub fn softmax(&self, dim: usize) -> Self {
        // Naive softmax along last dim usually
        // Assume 2D [Batch, Class] and dim=1
        assert_eq!(dim, 1); 
        assert_eq!(self.shape.len(), 2);
        
        let rows = self.shape[0];
        let cols = self.shape[1];
        
        let mut out = vec![0.0f32; self.data.len()];
        
        for i in 0..rows {
            let row_start = i * cols;
            let row_end = row_start + cols;
            let row_slice = &self.data[row_start..row_end];
            
            let max_val = row_slice.iter().fold(std::f32::NEG_INFINITY, |a, &b| a.max(b));
            let mut sum_exp = 0.0f32;
            for (j, &val) in row_slice.iter().enumerate() {
                let e = (val - max_val).exp();
                out[row_start + j] = e;
                sum_exp += e;
            }
            for j in 0..cols {
                out[row_start + j] /= sum_exp;
            }
        }
        
        Self::new(out, self.shape.clone())
    }

    // Stateful LSTM Cell
    // Returns (h_next, c_next)
    pub fn lstm_cell(&self, 
        h_prev: &Tensor, 
        c_prev: &Tensor, 
        w_ih: &Tensor, 
        w_hh: &Tensor, 
        bias_ih: Option<&Tensor>, 
        bias_hh: Option<&Tensor>
    ) -> (Tensor, Tensor) {
        // self is input [Batch, In] (or [1, In])
        
        // 1. Compute gates: x @ W_ih.T + h @ W_hh.T + b
        // W shape typically [4*Hidden, In]
        
        let gates_x = self.matmul(&w_ih.transpose()); // [Batch, 4*H]
        let gates_h = h_prev.matmul(&w_hh.transpose()); // [Batch, 4*H]
        
        let mut gates = gates_x.add(&gates_h);
        
        if let Some(b) = bias_ih {
            // Broadcast add
            // Assuming gates is [1, 4*H]
             for i in 0..gates.data.len() {
                 gates.data[i] += b.data[i % b.data.len()];
             }
        }
        if let Some(b) = bias_hh {
             for i in 0..gates.data.len() {
                 gates.data[i] += b.data[i % b.data.len()];
             }
        }
        
        // 2. Split gates (i, f, g, o)
        // Hidden size = Total / 4
        let hidden_size = gates.shape.last().unwrap() / 4;
        let batch_size = gates.shape[0];
        
        // We construct c_new, h_new directly to avoid allocations of intermediate gate tensors if possible.
        // But for clarity, let's just loop over batch/hidden.
        
        let mut h_next_data = Vec::with_capacity(batch_size * hidden_size);
        let mut c_next_data = Vec::with_capacity(batch_size * hidden_size);
        
        let g_data = &gates.data;
        let c_prev_data = &c_prev.data;
        
        for b in 0..batch_size {
            let base = b * 4 * hidden_size;
            let c_base = b * hidden_size;
            
            for k in 0..hidden_size {
                let i_val = g_data[base + k];
                let f_val = g_data[base + hidden_size + k];
                let g_val = g_data[base + 2*hidden_size + k];
                let o_val = g_data[base + 3*hidden_size + k];
                
                // Sigmoid for i, f, o
                let i_sig = 1.0f32 / (1.0f32 + (-i_val).exp());
                let f_sig = 1.0f32 / (1.0f32 + (-f_val).exp());
                let o_sig = 1.0f32 / (1.0f32 + (-o_val).exp());
                
                // Tanh for g
                let g_tanh = g_val.tanh();
                
                let c_old = c_prev_data[c_base + k];
                
                let c_new = f_sig * c_old + i_sig * g_tanh;
                let h_new = o_sig * c_new.tanh();
                
                c_next_data.push(c_new);
                h_next_data.push(h_new);
            }
        }
        
        (
            Tensor::new(h_next_data, vec![batch_size, hidden_size]),
            Tensor::new(c_next_data, vec![batch_size, hidden_size])
        )
    }

    pub fn pad_to(&self, target_len: usize) -> Tensor {
        // Assume [Seq, Dim]
        // Pad dim 0
        let current = self.shape[0];
        if current >= target_len {
            // Truncate? Or return clone.
            return self.clone(); // TODO: Slice
        }
        let dim = self.shape[1];
        let mut newdata = self.data.clone();
        newdata.resize(target_len * dim, 0.0f32);
        Tensor::new(newdata, vec![target_len, dim])
    }
}
