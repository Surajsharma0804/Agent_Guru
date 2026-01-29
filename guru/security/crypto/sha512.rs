//! SHA-512 Implementation (Sovereign)

pub struct Sha512 {
    state: [u64; 8],
    len: u128,
    buffer: [u8; 128],
    offset: usize,
}

impl Sha512 {
    pub fn new() -> Self {
        Self {
            state: [
                0x6a09e667f3bcc908, 0xbb67ae8584caa73b, 0x3c6ef372fe94f82b, 0xa54ff53a5f1d36f1,
                0x510e527fade682d1, 0x9b05688c2b3e6c1f, 0x1f83d9abfb41bd6b, 0x5be0cd19137e2179,
            ],
            len: 0,
            buffer: [0u8; 128],
            offset: 0,
        }
    }

    pub fn update(&mut self, data: &[u8]) {
        // Implementation TODO
    }

    pub fn finalize(self) -> [u8; 64] {
        // Implementation TODO
        [0u8; 64]
    }
}
