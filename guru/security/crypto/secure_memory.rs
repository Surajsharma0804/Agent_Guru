use std::ptr;
use std::sync::atomic::{compiler_fence, Ordering};

/// Trait for types that can be securely zeroized.
pub trait Zeroize {
    /// Zeroizes the memory of the object using volatile writes.
    fn zeroize(&mut self);
}

impl Zeroize for u8 {
    fn zeroize(&mut self) {
        unsafe { ptr::write_volatile(self, 0) };
    }
}

impl<const N: usize> Zeroize for [u8; N] {
    fn zeroize(&mut self) {
        for byte in self.iter_mut() {
            unsafe { ptr::write_volatile(byte, 0) };
        }
        compiler_fence(Ordering::SeqCst);
    }
}

impl Zeroize for Vec<u8> {
    fn zeroize(&mut self) {
        for byte in self.iter_mut() {
            unsafe { ptr::write_volatile(byte, 0) };
        }
        compiler_fence(Ordering::SeqCst);
    }
}

/// A wrapper that ensures the contained value is zeroized on Drop.
pub struct Secret<T: Zeroize> {
    inner: Option<T>,
}

impl<T: Zeroize> Secret<T> {
    pub fn new(value: T) -> Self {
        Self { inner: Some(value) }
    }

    pub fn expose_secret(&self) -> &T {
        self.inner.as_ref().unwrap()
    }

    pub fn expose_secret_mut(&mut self) -> &mut T {
        self.inner.as_mut().unwrap()
    }
}

impl<T: Zeroize> Drop for Secret<T> {
    fn drop(&mut self) {
        if let Some(ref mut inner) = self.inner {
            inner.zeroize();
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_zeroize_array() {
        let mut arr = [0x42u8; 32];
        arr.zeroize();
        assert_eq!(arr, [0u8; 32]);
    }
}
