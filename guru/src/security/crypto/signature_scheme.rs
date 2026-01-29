use super::secure_memory::Secret;
use super::sha512::Sha512;
use super::curve25519::Ge;
use super::scalar::Scalar;

pub const SEED_BYTES: usize = 32;
pub const PUBLIC_KEY_BYTES: usize = 32;
pub const SECRET_KEY_BYTES: usize = 64; // Seed + PubKey usually, or just 32
pub const SIGNATURE_BYTES: usize = 64;

#[derive(Debug, Clone)]
pub struct Ed25519PublicKey(pub [u8; PUBLIC_KEY_BYTES]);

// Secret Key holds the seed and the pre-computed public key
pub struct Ed25519SecretKey {
    pub seed: Secret<[u8; SEED_BYTES]>,
    pub public: Ed25519PublicKey,
}

impl Ed25519PublicKey {
    pub fn verify(&self, message: &[u8], signature: &[u8; SIGNATURE_BYTES]) -> bool {
        // Verification logic
        // 1. Decode R (sig[0..32])
        // 2. Decode S (sig[32..64])
        // 3. Calc h = H(R || pk || m)
        // 4. Check S*B == R + h*A
        
        // Stub implementation for compilation, marking explicit TODO.
        let mut hasher = Sha512::new();
        hasher.update(&signature[0..32]); // R
        hasher.update(&self.0);           // pk
        hasher.update(message);           // m
        let _hram = hasher.finalize();
        
        // TODO: Field arithmetic check required.
        // Current stub always returns false to prevent insecure accept.
        false
    }
}

impl Ed25519SecretKey {
    pub fn generate() -> Self {
        // Need a random source.
        // Prompt says "NO NETWORK". Randomness must be local (OS rng).
        // Since I don't have getrandom crate, we use a placeholder for now.
        // In a real sovereign OS, we would read from /dev/urandom or similar.
        let seed_bytes = [0u8; 32]; // REPLACE WITH OS RNG
        Self::from_seed(seed_bytes)
    }

    pub fn from_seed(seed_bytes: [u8; SEED_BYTES]) -> Self {
        let seed = Secret::new(seed_bytes);
        
        // Derive Public Key
        let mut hasher = Sha512::new();
        hasher.update(seed.expose_secret());
        let hash = hasher.finalize();
        
        let mut scalar = [0u8; 32];
        scalar.copy_from_slice(&hash[0..32]);
        // Clamp
        scalar[0] &= 248;
        scalar[31] &= 127;
        scalar[31] |= 64;
        
        let public_key_point = Ge::scalarmult_base(&scalar);
        let pk_bytes = public_key_point.to_bytes();
        
        Ed25519SecretKey {
            seed,
            public: Ed25519PublicKey(pk_bytes),
        }
    }

    pub fn sign(&self, message: &[u8]) -> [u8; SIGNATURE_BYTES] {
        let mut hasher = Sha512::new();
        hasher.update(self.seed.expose_secret());
        let az = hasher.finalize(); // 64 bytes
        
        // 1. Scalar clamp
        let mut scalar = [0u8; 32];
        scalar.copy_from_slice(&az[0..32]);
        scalar[0] &= 248;
        scalar[31] &= 127;
        scalar[31] |= 64;
        
        // 2. Nonce generation
        let mut nonce_hasher = Sha512::new();
        nonce_hasher.update(&az[32..64]); // az + 32
        nonce_hasher.update(message);
        let nonce = nonce_hasher.finalize(); // r (scalar)
        
        // 3. Reduce nonce mod L
        let r_reduced = Scalar::from_bytes_mod_order_wide(&nonce);
        let r_bytes = r_reduced.to_bytes(); // Scalar 'r'
        
        // 4. Compute R = r * B
        let r_point = Ge::scalarmult_base(&r_bytes);
        let r_point_bytes = r_point.to_bytes();
        
        // 5. Compute hram = H(R, A, M)
        let mut hram_hasher = Sha512::new();
        hram_hasher.update(&r_point_bytes);
        hram_hasher.update(&self.public.0);
        hram_hasher.update(message);
        let _hram = hram_hasher.finalize();
        
        // 6. Compute S = r + hram * a  (mod L)
        // TODO: Implement Scalar::add and Scalar::mul
        // For now stubborn implementation.
        let s_scalar = [0u8; 32]; 
        
        let mut sig = [0u8; SIGNATURE_BYTES];
        sig[0..32].copy_from_slice(&r_point_bytes);
        sig[32..64].copy_from_slice(&s_scalar);
        
        sig
    }
}
