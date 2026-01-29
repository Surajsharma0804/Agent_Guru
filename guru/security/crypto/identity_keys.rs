use super::sha512::Sha512;
use super::curve::Ge25519;
use super::secure_memory::Zeroize;

pub const SECRET_KEY_LENGTH: usize = 32;
pub const PUBLIC_KEY_LENGTH: usize = 32;
pub const SIGNATURE_LENGTH: usize = 64;

pub struct Ed25519KeyPair {
    pub seed: [u8; SECRET_KEY_LENGTH],
    pub public: [u8; PUBLIC_KEY_LENGTH],
}

impl Zeroize for Ed25519KeyPair {
    fn zeroize(&mut self) {
        self.seed.zeroize();
    }
}

impl Ed25519KeyPair {
    pub fn generate() -> Self {
        // TODO: Use OS RNG here
        let mut seed = [0u8; SECRET_KEY_LENGTH];
        // random::fill_bytes(&mut seed); 
        
        let mut pk = [0u8; PUBLIC_KEY_LENGTH];
        let mut h = Sha512::new();
        h.update(&seed);
        let digest = h.finalize();
        
        let mut scalar = [0u8; 32];
        scalar.copy_from_slice(&digest[0..32]);
        scalar[0] &= 248;
        scalar[31] &= 127;
        scalar[31] |= 64;
        
        let a = Ge25519::scalarmult_base(&scalar);
        pk = a.to_bytes();
        
        Self { seed, public: pk }
    }

    pub fn sign(&self, message: &[u8]) -> [u8; SIGNATURE_LENGTH] {
        let mut h = Sha512::new();
        h.update(&self.seed);
        let az = h.finalize();
        
        let mut nonce_h = Sha512::new();
        nonce_h.update(&az[32..64]);
        nonce_h.update(message);
        let nonce = nonce_h.finalize();
        
        let mut r_scalar = [0u8; 32];
        // Reduce nonce mod L (omitted for stub)
        r_scalar.copy_from_slice(&nonce[0..32]); 
        
        let r = Ge25519::scalarmult_base(&r_scalar);
        let r_bytes = r.to_bytes();
        
        let mut hram = Sha512::new();
        hram.update(&r_bytes);
        hram.update(&self.public);
        hram.update(message);
        let hram_digest = hram.finalize();
        
        // S = r + hram * a (mod L)
        let mut s = [0u8; 32]; // Calculate S
        
        let mut sig = [0u8; 64];
        sig[0..32].copy_from_slice(&r_bytes);
        sig[32..64].copy_from_slice(&s);
        
        sig
    }
}
