//! SHA-512 Implementation (FIPS 180-4)
//! Self-contained, no dependencies.

use super::secure_memory::Zeroize;

const BLOCK_LEN: usize = 128;
const STATE_LEN: usize = 8;
const K: [u64; 80] = [
    0x428a2f98d728ae22, 0x7137449123ef65cd, 0xb5c0fbcfec4d3b2f, 0xe9b5dba58189dbbc,
    0x3956c25bf348b538, 0x59f111f1b605d019, 0x923f82a4af194f9b, 0xab1c5ed5da6d8118,
    0xd807aa98a3030242, 0x12835b0145706fbe, 0x243185be4ee4b28c, 0x550c7dc3d5ffb4e2,
    0x72be5d74f27b896f, 0x80deb1fe3b1696b1, 0x9bdc06a725c71235, 0xc19bf174cf692694,
    0xe49b69c19ef14ad2, 0xefbe4786384f25e3, 0x0fc19dc68b8cd5b5, 0x240ca1cc77ac9c65,
    0x2de92c6f592b0275, 0x4a7484aa6ea6e483, 0x5cb0a9dcbd41fbd4, 0x76f988da831153b5,
    0x983e5152ee66dfab, 0xa831c66d2db43210, 0xb00327c898fb213f, 0xbf597fc7beef0ee4,
    0xc6e00bf33da88fc2, 0xd5a79147930aa725, 0x06ca6351e003826f, 0x142929670a0e6e70,
    0x27b70a8546d22ffc, 0x2e1b21385c26c926, 0x4d2c6dfc5ac42aed, 0x53380d139d95b3df,
    0x650a73548baf63de, 0x766a0abb3c77b2a8, 0x81c2c92e47edaee6, 0x92722c851482353b,
    0xa2bfe8a14cf10364, 0xa81a664bbc423001, 0xc24b8b70d0f89791, 0xc76c51a30654be30,
    0xd192e819d6ef5218, 0xd69906245565a910, 0xf40e35855771202a, 0x106aa07032bbd1b8,
    0x19a4c116b8d2d0c8, 0x1e376c085141ab53, 0x2748774cdf8eeb99, 0x34b0bcb5e19b48a8,
    0x391c0cb3c5c95a63, 0x4ed8aa4ae3418acb, 0x5b9cca4f7763e373, 0x682e6ff3d6b2b8a3,
    0x748f82ee5defb2fc, 0x78a5636f43172f60, 0x84c87814a1f0ab72, 0x8cc702081a6439ec,
    0x90befffa23631e28, 0xa4506cebde82bde9, 0xbef9a3f7b2c67915, 0xc67178f2e372532b,
    0xca273eceea26619c, 0xd186b8c721c0c207, 0xeada7dd6cde0eb1e, 0xf57d4f7fee6ed178,
    0x06f067aa72176fba, 0x0a637dc5a2c898a6, 0x113f9804bef90dae, 0x1b710b35131c471b,
    0x28db77f523047d84, 0x32caab7b40c72493, 0x3c9ebe0a15ca9050, 0x431d67c49c100d4c,
    0x4cc5d4becb3e42b6, 0x597f299cfc657e2a, 0x5fcb6fab3ad6faec, 0x6c44198c4a475817,
];

pub struct Sha512 {
    state: [u64; STATE_LEN],
    completed_data_blocks: u64,
    pending: [u8; BLOCK_LEN],
    pending_len: usize,
}

impl Sha512 {
    pub fn new() -> Self {
        Self {
            state: [
                0x6a09e667f3bcc908, 0xbb67ae8584caa73b, 0x3c6ef372fe94f82b, 0xa54ff53a5f1d36f1,
                0x510e527fade682d1, 0x9b05688c2b3e6c1f, 0x1f83d9abfb41bd6b, 0x5be0cd19137e2179,
            ],
            completed_data_blocks: 0,
            pending: [0u8; BLOCK_LEN],
            pending_len: 0,
        }
    }

    pub fn update(&mut self, data: &[u8]) {
        let mut offset = 0;
        let len = data.len();

        while offset < len {
            let space = BLOCK_LEN - self.pending_len;
            let copy_len = std::cmp::min(space, len - offset);
            
            self.pending[self.pending_len..self.pending_len + copy_len]
                .copy_from_slice(&data[offset..offset + copy_len]);
            
            self.pending_len += copy_len;
            offset += copy_len;

            if self.pending_len == BLOCK_LEN {
                let block = self.pending;
                self.process_block(&block);
                self.completed_data_blocks += 1;
                self.pending_len = 0;
            }
        }
    }

    pub fn finalize(mut self) -> [u8; 64] {
        // Padding
        let bits = (self.completed_data_blocks * BLOCK_LEN as u64 + self.pending_len as u64) * 8;
        
        self.pending[self.pending_len] = 0x80;
        self.pending_len += 1;

        if self.pending_len > BLOCK_LEN - 16 {
            // Not enough space for length, pad this block and process
            for i in self.pending_len..BLOCK_LEN {
                self.pending[i] = 0;
            }
            let block = self.pending;
            self.process_block(&block);
            self.pending = [0u8; BLOCK_LEN];
            self.pending_len = 0;
        }

        // Pad with zeros until the last 16 bytes
        for i in self.pending_len..BLOCK_LEN - 16 {
            self.pending[i] = 0;
        }

        // Write length (Big Endian)
        let len_bytes = bits.to_be_bytes(); // u64 is enough for now (u128 is spec but u64 covers practical)
        // Upper 64 bits are likely 0 unless data is > 2^64 bits (2 exabytes)
        // Formal spec requires 128 bit length.
        let high_len: u64 = 0;
        self.pending[BLOCK_LEN - 16..BLOCK_LEN - 8].copy_from_slice(&high_len.to_be_bytes());
        self.pending[BLOCK_LEN - 8..].copy_from_slice(&len_bytes);

        let block = self.pending;
        self.process_block(&block);

        let mut out = [0u8; 64];
        for (i, v) in self.state.iter().enumerate() {
            out[i * 8..(i + 1) * 8].copy_from_slice(&v.to_be_bytes());
        }
        
        // Zeroize state before returning? 
        // Logic says `self` is consumed, so we should zeroize it in Drop if it was sensitive, 
        // but here it's a hash function.
        out
    }

    fn process_block(&mut self, block: &[u8; BLOCK_LEN]) {
        let mut w = [0u64; 80];

        // Prepare message schedule
        for i in 0..16 {
            w[i] = u64::from_be_bytes(block[i * 8..(i + 1) * 8].try_into().unwrap());
        }
        for i in 16..80 {
            let s0 = w[i - 15].rotate_right(1) ^ w[i - 15].rotate_right(8) ^ (w[i - 15] >> 7);
            let s1 = w[i - 2].rotate_right(19) ^ w[i - 2].rotate_right(61) ^ (w[i - 2] >> 6);
            w[i] = w[i - 16].wrapping_add(s0).wrapping_add(w[i - 7]).wrapping_add(s1);
        }

        let mut a = self.state[0];
        let mut b = self.state[1];
        let mut c = self.state[2];
        let mut d = self.state[3];
        let mut e = self.state[4];
        let mut f = self.state[5];
        let mut g = self.state[6];
        let mut h = self.state[7];

        for i in 0..80 {
            let s1 = e.rotate_right(14) ^ e.rotate_right(18) ^ e.rotate_right(41);
            let ch = (e & f) ^ (!e & g);
            let temp1 = h.wrapping_add(s1).wrapping_add(ch).wrapping_add(K[i]).wrapping_add(w[i]);
            let s0 = a.rotate_right(28) ^ a.rotate_right(34) ^ a.rotate_right(39);
            let maj = (a & b) ^ (a & c) ^ (b & c);
            let temp2 = s0.wrapping_add(maj);

            h = g;
            g = f;
            f = e;
            e = d.wrapping_add(temp1);
            d = c;
            c = b;
            b = a;
            a = temp1.wrapping_add(temp2);
        }

        self.state[0] = self.state[0].wrapping_add(a);
        self.state[1] = self.state[1].wrapping_add(b);
        self.state[2] = self.state[2].wrapping_add(c);
        self.state[3] = self.state[3].wrapping_add(d);
        self.state[4] = self.state[4].wrapping_add(e);
        self.state[5] = self.state[5].wrapping_add(f);
        self.state[6] = self.state[6].wrapping_add(g);
        self.state[7] = self.state[7].wrapping_add(h);
        
        // Zeroize stack
        w.zeroize();
    }
}

impl Drop for Sha512 {
    fn drop(&mut self) {
        self.state.zeroize();
        self.pending.zeroize();
    }
}
