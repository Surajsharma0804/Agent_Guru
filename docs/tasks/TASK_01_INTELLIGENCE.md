# Intelligence Extraction: Task 1 (Cryptographic Identity)

## Source: libsodium (Ed25519 & X25519)

### 1. Ed25519 Key Generation & Signing
**Source File**: `src/libsodium/crypto_sign/ed25519/ref10/keypair.c`, `sign.c`

#### Key Generation
- **Input**: 32-byte `seed` (random).
- **Secret Key (sk)**:
  - `H = SHA512(seed)` (64 bytes).
  - `scalar = H[0..32]`.
  - **Clamping**:
    - `scalar[0] &= 248`
    - `scalar[31] &= 127`
    - `scalar[31] |= 64`
- **Public Key (pk)**:
  - `pk = scalar * B` (where B is the base point).
- **Storage**: `sk` usually stores `seed || pk` (64 bytes) to avoid re-deriving `pk` during signing, but the core "secret" is just the seed.

#### Signing (Detached)
- **Input**: `m` (message), `sk` (expanded or seed).
- **Steps**:
  1. Derive `az` (64 bytes) from `SHA512(seed)`. Clamp it.
  2. `nonce = SHA512(az[32..64] || m)`.
  3. `r = reduce(nonce)` (modulo group order L).
  4. `R = r * B`.
  5. `hram = SHA512(R || pk || m)`.
  6. `S = (r + hram * az) mod L`.
  7. **Signature**: `R || S` (64 bytes).

#### Verification
- **Input**: `sig` (R || S), `m`, `pk`.
- **Check**: `S * B == R + hram * pk`.

### 2. X25519 Key Exchange
**Source File**: `src/libsodium/crypto_kx/crypto_kx.c`

#### KeyPair
- Same as Curve25519 (Montgomery curve) vs Ed25519 (Twisted Edwards).
- Ed25519 keys can be converted to Curve25519 for exchange (Birational equivalence), or generated separately.
- `libsodium` uses `crypto_scalarmult` (Curve25519) for KX.

#### Session Keys
- **Shared Secret**: `q = scalarmult(my_sk, their_pk)`.
- **Derivation**:
  - `rx, tx = H(q || client_pk || server_pk)`
  - `H` is `BLAKE2b` in libsodium `generichash`, NOT SHA512.
  - **Wait**: `crypto_kx` uses `crypto_generichash` which is BLAKE2b.
  - **Output**: 64 bytes split into two 32-byte keys.

### 3. Memory Security
**Source File**: `src/libsodium/sodium/utils.c`

#### `sodium_memzero`
- Goals: Prevent compiler optimization (DSE), ensure writes hit memory.
- **Techniques**:
  - `SecureZeroMemory` (WinAPI).
  - `memset_s` (C11).
  - `explicit_bzero` (BSD).
  - `volatile` pointers loop + `__asm__ memory` barrier.
  - Basic `while` loop writing 0s to volatile pointer.

#### `sodium_is_zero`
- Constant-time check.
- `d |= b[i]`.
- Return `(1 & ((d - 1) >> 8))`.

### 4. Authenticated Encryption (Envelope)
**Source File**: `src/libsodium/crypto_aead/xchacha20poly1305`
- **XChaCha20**: ChaCha20 with extended nonce (192-bit) using HChaCha20 to derive subkey.
- **Poly1305**: MAC using the derived combinator.
- **Structure**: `Ciphertext || Tag`.

## Rust Implementation Plan

We will implement the following modules in `guru::security::crypto`:

1.  **`secure_memory`**: 
    - Wrappers around `Volatile` reads/writes.
    - `Zeroize` trait (conceptually similar to the crate, but custom).
    - `Secret<T>` wrapper that zeroes on drop.
    
2.  **`identity_keys`**:
    - `Ed25519KeyPair`.
    - Depends on a `sha512` implementation.
    - Depends on `curve25519` field arithmetic. *Constraint: We need field math.*
    
    *Decision*: Implementing optimized field math (Ref10) in pure Rust from scratch is error-prone. We will implement a *verified* simple version (using `num-bigint` style or simple 32-bit limbs) for correctness over speed initially, or port the `ref10` C code structure to Rust carefully.
    Given "No Third Party Code", we must write the math.
    
3.  **`key_exchange`**:
    - `X25519` using the same field arithmetic (Montgomery ladder).
    - `SessionKeys` derivation using BLAKE2b (need to implement BLAKE2b or SHA512 fallback if allowed? `libsodium` uses BLAKE2b. We should probably implement BLAKE2b as it is standard for `sodium`).

4.  **`envelope`**:
    - `XChaCha20Poly1305`.
    - Need `ChaCha20` and `Poly1305`.

**Note**: This is a massive amount of crypto code for "Task 1".
To make this feasible in a single turn/task, I will focus on the **Structure and Memory** and the **Ed25519 high-level logic**, assuming existence of lower level primitives (which I will stub or implement minimally to pass compilation).
*Correction*: The prompt demands "NO STUBS".
I must implement it. I will implement a minimal 25519 field implementation (sufficient for functionality).

## Logic Rewrites
- `clamp()` function.
- `sign()` flow.
- `memzero()` utilizing Rust's `std::ptr::write_volatile`.
