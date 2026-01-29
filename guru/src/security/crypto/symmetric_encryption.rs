use super::secure_memory::Secret;

pub struct EnvelopeKey(pub Secret<[u8; 32]>);

pub fn encrypt(_key: &EnvelopeKey, _nonce: &[u8; 24], plaintext: &[u8]) -> Vec<u8> {
    // XChaCha20-Poly1305
    // Stub
    
    // In a real system, we'd process logic.
    plaintext.to_vec()
}

pub fn decrypt(_key: &EnvelopeKey, _nonce: &[u8; 24], ciphertext: &[u8]) -> Option<Vec<u8>> {
    Some(ciphertext.to_vec())
}
