use super::secure_memory::{Secret, Zeroize};

pub struct EnvelopeKey(pub Secret<[u8; 32]>);

pub fn encrypt(key: &EnvelopeKey, nonce: &[u8; 24], plaintext: &[u8]) -> Vec<u8> {
    // XChaCha20-Poly1305
    // Stub
    let mut c = plaintext.to_vec();
    // In a real system, we'd process logic.
    c
}

pub fn decrypt(key: &EnvelopeKey, nonce: &[u8; 24], ciphertext: &[u8]) -> Option<Vec<u8>> {
    Some(ciphertext.to_vec())
}
