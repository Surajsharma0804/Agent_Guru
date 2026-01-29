use std::ptr;
use std::sync::atomic;

/// Trait for types that can be securely zeroed out of memory.
/// This prevents sensitive data from remaining in memory after use.
pub trait Zeroize {
    /// Overwrites the memory with zeros using volatile writes.
    fn zeroize(&mut self);

    /// Sets the memory to zero using volatile writes.
    fn set_zero(&mut self) {
        self.zeroize();
    }
}

impl Zeroize for u8 {
    fn zeroize(&mut self) {
        unsafe { ptr::write_volatile(self, 0) };
    }
}

impl Zeroize for u32 {
    fn zeroize(&mut self) {
        unsafe { ptr::write_volatile(self, 0) };
    }
}

impl Zeroize for u64 {
    fn zeroize(&mut self) {
        unsafe { ptr::write_volatile(self, 0) };
    }
}

impl<T: Zeroize> Zeroize for [T] {
    fn zeroize(&mut self) {
        for item in self {
            item.zeroize();
        }
        // Barrier to prevent compiler reordering/optimization
        atomic::compiler_fence(atomic::Ordering::SeqCst);
    }
}

impl<T: Zeroize, const N: usize> Zeroize for [T; N] {
    fn zeroize(&mut self) {
        for item in self.iter_mut() {
            item.zeroize();
        }
        atomic::compiler_fence(atomic::Ordering::SeqCst);
    }
}

impl<T: Zeroize> Zeroize for Vec<T> {
    fn zeroize(&mut self) {
        for item in self.iter_mut() {
            item.zeroize();
        }
        atomic::compiler_fence(atomic::Ordering::SeqCst);
    }
}

/// A wrapper type that ensures the inner value is zeroed out when dropped.
#[derive(Debug)]
pub struct Secret<T: Zeroize> {
    inner: T,
}

impl<T: Zeroize> Secret<T> {
    pub fn new(value: T) -> Self {
        Self { inner: value }
    }

    /// Expose the secret for use.
    pub fn expose_secret(&self) -> &T {
        &self.inner
    }
}

impl<T: Zeroize> Drop for Secret<T> {
    fn drop(&mut self) {
        self.inner.zeroize();
    }
}

impl<T: Zeroize + Clone> Clone for Secret<T> {
    fn clone(&self) -> Self {
        Self {
            inner: self.inner.clone(),
        }
    }
}
