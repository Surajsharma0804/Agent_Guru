use crate::intelligence::tensor::Tensor;
use std::f32::consts::PI;

pub struct ModelDimensions {
    pub n_mels: usize,
    pub n_audio_ctx: usize,
    pub n_audio_state: usize,
    pub n_audio_head: usize,
    pub n_audio_layer: usize,
    pub n_vocab: usize,
    pub n_text_ctx: usize,
    pub n_text_state: usize,
    pub n_text_head: usize,
    pub n_text_layer: usize,
}

pub struct LayerNorm {
    weight: Tensor,
    bias: Tensor,
}

impl LayerNorm {
    pub fn new(n_state: usize) -> Self {
        Self {
            weight: Tensor::new(vec![1.0f32; n_state], vec![n_state]),
            bias: Tensor::new(vec![0.0f32; n_state], vec![n_state]),
        }
    }

    pub fn forward(&self, x: &Tensor) -> Tensor {
        // Normalization: (x - mean) / sqrt(var + eps) * weight + bias
        // Native tensor ops required: mean, basic arithmetic.
        // For "Best" quality with limited tensor lib, we do element-wise manual loop if ops missing.
        // Tensor lib has `add`, `mul` (elementwise), but no broadcasting.
        // We will implement a manual loop for LayerNorm to be safe and correct.
        
        // Assume x is [Batch, Seq, State] or [Seq, State]. Last dim is State.
        let shape = &x.shape;
        let last_dim = shape[shape.len()-1];
        assert_eq!(last_dim, self.weight.shape[0]);
        
        let mut out_data = Vec::with_capacity(x.data.len());
        let chunk_size = last_dim;
        
        for chunk in x.data.chunks(chunk_size) {
            let mean = chunk.iter().sum::<f32>() / chunk_size as f32;
            let var = chunk.iter().map(|v| (v - mean).powi(2)).sum::<f32>() / chunk_size as f32;
            let std_dev = (var + 1e-5).sqrt();
            
            for (i, &val) in chunk.iter().enumerate() {
                let norm = (val - mean) / std_dev;
                let scale = self.weight.data[i];
                let shift = self.bias.data[i];
                out_data.push(norm * scale + shift);
            }
        }
        
        Tensor::new(out_data, shape.clone())
    }
}

pub struct Linear {
    weight: Tensor,
    bias: Option<Tensor>,
}

impl Linear {
    pub fn new(in_features: usize, out_features: usize, bias: bool) -> Self {
        // Weight shape: [Out, In]
        // Bias shape: [Out]
        Self {
            weight: Tensor::zeros(vec![out_features, in_features]),
            bias: if bias { Some(Tensor::zeros(vec![out_features])) } else { None },
        }
    }

    pub fn forward(&self, x: &Tensor) -> Tensor {
        // x @ weight.T + bias
        // x: [..., In]
        // weight: [Out, In] -> T -> [In, Out]
        // result: [..., Out]
        
        // Tensor lib matmul expects 2D. We might need to reshape or loop.
        // For simplicity/robustness:
        // Treat x as [N, In] (flatten all but last).
        let in_features = self.weight.shape[1];
        let out_features = self.weight.shape[0];
        
        assert_eq!(x.shape.last(), Some(&in_features));
        
        // Reshape x to [Rows, In]
        let num_rows = x.data.len() / in_features;
        let x_2d = Tensor::new(x.data.clone(), vec![num_rows, in_features]);
        
        // Weight Transpose: [In, Out]
        let w_t = self.weight.transpose();
        
        // MatMul: [Rows, In] @ [In, Out] -> [Rows, Out]
        let mut out = x_2d.matmul(&w_t);
        
        // Add Bias
        if let Some(ref b) = self.bias {
             // Broadcast bias [Out] to [Rows, Out] manually
             for i in 0..num_rows {
                 for j in 0..out_features {
                     out.data[i * out_features + j] += b.data[j];
                 }
             }
        }
        
        // Restore shape
        let mut new_shape = x.shape.clone();
        *new_shape.last_mut().unwrap() = out_features;
        out.shape = new_shape;
        out
    }
}

pub struct MultiHeadAttention {
    n_head: usize,
    query: Linear,
    key: Linear,
    value: Linear,
    out: Linear,
}

impl MultiHeadAttention {
    pub fn new(n_state: usize, n_head: usize) -> Self {
        Self {
            n_head,
            query: Linear::new(n_state, n_state, true),
            key: Linear::new(n_state, n_state, false),
            value: Linear::new(n_state, n_state, true),
            out: Linear::new(n_state, n_state, true),
        }
    }

    pub fn forward(&self, x: &Tensor, xa: Option<&Tensor>, mask: Option<&Tensor>) -> Tensor {
        // q, k, v projections
        // x: [1, Seq, State]
        let q = self.query.forward(x);
        
        let k = if let Some(context) = xa {
            self.key.forward(context)
        } else {
            self.key.forward(x)
        };
        
        let v = if let Some(context) = xa {
            self.value.forward(context)
        } else {
            self.value.forward(x)
        };
        
        // Split heads (Manual loop over heads)
        // State = Head * Dim
        let dim_per_head = q.shape.last().unwrap() / self.n_head;
        let seq_len = q.shape[q.shape.len()-2]; 
        // Assume batch=1
        
        // Result buffer
        let mut heads_out = Vec::new();
        
        for h in 0..self.n_head {
            // Extract Q_h, K_h, V_h
            // Slice the last dimension
            let q_h = self.extract_head(&q, h, dim_per_head);
            let k_h = self.extract_head(&k, h, dim_per_head);
            let v_h = self.extract_head(&v, h, dim_per_head);
            
            // Attention scores: Q @ K.T
            let mut scores = q_h.matmul(&k_h.transpose());
            
            // Scale
            let scale = (dim_per_head as f32).powf(-0.5);
            for val in scores.data.iter_mut() {
                *val *= scale;
            }
            
            // Mask (if provided) - naive sub -inf
            if let Some(m) = mask {
                // TODO: Apply mask (add -inf)
            }
            
            // Softmax
            let weights = scores.softmax(1);
            
            // Weighted sum: W @ V
            let context = weights.matmul(&v_h);
            heads_out.push(context);
        }
        
        // Merge heads (Concatenate last dim)
        let merged = self.merge_heads(heads_out, seq_len, dim_per_head);
        
        // Output projection
        self.out.forward(&merged)
    }
    
    fn extract_head(&self, t: &Tensor, head_idx: usize, dim: usize) -> Tensor {
        // [Seq, State] -> [Seq, Dim]
        let seq_len = t.shape[t.shape.len()-2];
        let state_dim = t.shape.last().unwrap();
        let start = head_idx * dim;
        
        let mut data = Vec::with_capacity(seq_len * dim);
        for i in 0..seq_len {
            let row_start = i * state_dim;
            for j in 0..dim {
                data.push(t.data[row_start + start + j]);
            }
        }
        Tensor::new(data, vec![seq_len, dim])
    }
    
    fn merge_heads(&self, heads: Vec<Tensor>, seq_len: usize, dim: usize) -> Tensor {
        let n_head = heads.len();
        let total_dim = n_head * dim;
        let mut data = vec![0.0; seq_len * total_dim];
        
        for h in 0..n_head {
             let head_data = &heads[h].data;
             for i in 0..seq_len {
                 let row_start = i * total_dim;
                 let head_start = h * dim;
                 for j in 0..dim {
                     data[row_start + head_start + j] = head_data[i * dim + j];
                 }
             }
        }
        Tensor::new(data, vec![1, seq_len, total_dim])
    }
}

pub struct ResidualAttentionBlock {
    attn: MultiHeadAttention,
    attn_ln: LayerNorm,
    cross_attn: Option<MultiHeadAttention>,
    cross_attn_ln: Option<LayerNorm>,
    mlp_ln: LayerNorm,
    mlp_linear1: Linear,
    mlp_linear2: Linear,
}

impl ResidualAttentionBlock {
    pub fn new(n_state: usize, n_head: usize, cross_attention: bool) -> Self {
        let n_mlp = n_state * 4;
        Self {
            attn: MultiHeadAttention::new(n_state, n_head),
            attn_ln: LayerNorm::new(n_state),
            cross_attn: if cross_attention { Some(MultiHeadAttention::new(n_state, n_head)) } else { None },
            cross_attn_ln: if cross_attention { Some(LayerNorm::new(n_state)) } else { None },
            mlp_ln: LayerNorm::new(n_state),
            mlp_linear1: Linear::new(n_state, n_mlp, true),
            mlp_linear2: Linear::new(n_mlp, n_state, true),
        }
    }

    pub fn forward(&self, x: &Tensor, xa: Option<&Tensor>, mask: Option<&Tensor>) -> Tensor {
        // x = x + attn(ln(x))
        let ln_x = self.attn_ln.forward(x);
        let attn_out = self.attn.forward(&ln_x, None, mask); // Mask?
        let mut x = x.add(&attn_out);
        
        // if cross: x = x + cross_attn(ln(x), xa)
        if let Some(ref cross) = self.cross_attn {
             if let Some(ref context) = xa {
                 let ln_x_cross = self.cross_attn_ln.as_ref().unwrap().forward(&x);
                 let cross_out = cross.forward(&ln_x_cross, Some(context), None);
                 x = x.add(&cross_out);
             }
        }
        
        // x = x + mlp(ln(x))
        let ln_mlp = self.mlp_ln.forward(&x);
        let h = self.mlp_linear1.forward(&ln_mlp).gelu();
        let h2 = self.mlp_linear2.forward(&h);
        x.add(&h2)
    }
}

pub struct AudioEncoder {
    conv1_w: Tensor,
    conv1_b: Tensor,
    conv2_w: Tensor,
    conv2_b: Tensor,
    positional_embedding: Tensor,
    blocks: Vec<ResidualAttentionBlock>,
    ln_post: LayerNorm,
}

impl AudioEncoder {
    pub fn new(dims: &ModelDimensions) -> Self {
        Self {
            conv1_w: Tensor::zeros(vec![dims.n_audio_state, dims.n_mels, 3]), // Stub shape
            conv1_b: Tensor::zeros(vec![dims.n_audio_state]),
            conv2_w: Tensor::zeros(vec![dims.n_audio_state, dims.n_audio_state, 3]),
            conv2_b: Tensor::zeros(vec![dims.n_audio_state]),
            positional_embedding: Tensor::zeros(vec![dims.n_audio_ctx, dims.n_audio_state]),
            blocks: (0..dims.n_audio_layer).map(|_| ResidualAttentionBlock::new(dims.n_audio_state, dims.n_audio_head, false)).collect(),
            ln_post: LayerNorm::new(dims.n_audio_state),
        }
    }

    pub fn forward(&self, mel: &Tensor) -> Tensor {
        // x = gelu(conv1(mel))
        // x = gelu(conv2(x))
        // x = x + pos_embed
        // blocks
        // ln_post
        mel.clone()
    }
}

pub struct TextDecoder {
    token_embedding: Tensor,
    positional_embedding: Tensor,
    blocks: Vec<ResidualAttentionBlock>,
    ln: LayerNorm,
}

impl TextDecoder {
    pub fn new(dims: &ModelDimensions) -> Self {
        Self {
            token_embedding: Tensor::zeros(vec![dims.n_vocab, dims.n_text_state]),
            positional_embedding: Tensor::zeros(vec![dims.n_text_ctx, dims.n_text_state]),
            blocks: (0..dims.n_text_layer).map(|_| ResidualAttentionBlock::new(dims.n_text_state, dims.n_text_head, true)).collect(),
            ln: LayerNorm::new(dims.n_text_state),
        }
    }

    pub fn forward(&self, tokens: &Tensor, audio_features: &Tensor) -> Tensor {
        // x = embed(tokens) + pos_embed
        // tokens: [1, Seq] (Batch=1)
        
        let seq_len = tokens.shape[1];
        let n_state = self.token_embedding.shape[1];
        
        // 1. Embedding Lookup
        let mut x_data = Vec::with_capacity(seq_len * n_state);
        let vocab_size = self.token_embedding.shape[0];
        let embed_data = &self.token_embedding.data;
        
        for &t_val in &tokens.data {
             let token_id = t_val as usize;
             if token_id >= vocab_size {
                 // Safe fallback (unk) or panic? Panic for now to catch bugs.
                 panic!("Token ID out of bounds");
             }
             let start = token_id * n_state;
             // Append embedding vector
             x_data.extend_from_slice(&embed_data[start..start + n_state]);
        }
        
        let mut x = Tensor::new(x_data, vec![1, seq_len, n_state]);
        
        // 2. Positional Embedding (Add)
        // pos_embed: [Ctx, State]
        // We take first seq_len positions
        // Broadcasst? No, it's 1:1 add to [1, Seq, State] (broadcasting batch)
        let pos_data = &self.positional_embedding.data;
        for i in 0..seq_len {
            let row_start = i * n_state;
            for j in 0..n_state {
                x.data[i * n_state + j] += pos_data[row_start + j];
            }
        }
        
        // 3. Blocks
        for block in &self.blocks {
            x = block.forward(&x, Some(audio_features), None); // Mask?
            // Mask is needed for causal attention. 
            // Stub mask for now (impl later if needed for precise functionality)
        }
        
        // 4. Layer Norm
        x = self.ln.forward(&x);
        
        // 5. Output Projection (Logits)
        // logits = x @ embed.T
        // x: [1, Seq, State]
        // embed.T: [State, Vocab]
        // result: [1, Seq, Vocab]
        
        // Reshape x to [Seq, State] for 2D matmul
        let x_2d = Tensor::new(x.data.clone(), vec![seq_len, n_state]);
        let logits_2d = x_2d.matmul(&self.token_embedding.transpose());
        
        // Reshape back
        Tensor::new(logits_2d.data, vec![1, seq_len, vocab_size])
    }
}

pub struct Whisper {
    encoder: AudioEncoder,
    decoder: TextDecoder,
}

impl Whisper {
    pub fn new(dims: ModelDimensions) -> Self {
        Self {
            encoder: AudioEncoder::new(&dims),
            decoder: TextDecoder::new(&dims),
        }
    }

    pub fn embed_audio(&self, mel: &Tensor) -> Tensor {
        self.encoder.forward(mel)
    }

    pub fn logits(&self, tokens: &Tensor, audio_features: &Tensor) -> Tensor {
        self.decoder.forward(tokens, audio_features)
    }
}
