// guru_core.cpp
// Polyglot Native Kernel for Agent Guru
// Implementing optimizations for DSP (Task 2) and Vision (Task 9).

// Using C-style headers for maximum compatibility with dumb linters/compilers
#include <math.h>
#include <stdint.h>
#include <string.h>

extern "C" {

// --- Task 2: Wake Word Engine (DSP) ---
// Naive DFT Magnitude: O(N^2)
// Suitable for small windows (N=400).
void guru_dft_magnitude(const float *input, float *output, size_t n) {
  const float PI = 3.14159265359f;
  for (size_t k = 0; k <= n / 2; k++) {
    float re = 0.0f;
    float im = 0.0f;
    float angle_term = -2.0f * PI * (float)k / (float)n;

    for (size_t t = 0; t < n; t++) {
      float angle = angle_term * (float)t;
      // Use standard C math functions
      float s = sinf(angle);
      float c = cosf(angle);

      re += input[t] * c;
      im += input[t] * s;
    }
    output[k] = sqrtf(re * re + im * im);
  }
}

// --- Task 9: Vision (Pixels) ---
// Fast Grayscale Conversion
// BGRA -> Gray
void guru_grayscale_kernel(const uint8_t *bgra, uint8_t *out_gray, size_t width,
                           size_t height) {
  size_t pixel_count = width * height;
  for (size_t i = 0; i < pixel_count; i++) {
    // BGRA layout: B=0, G=1, R=2, A=3 (Windows Native)
    uint8_t b = bgra[i * 4 + 0];
    uint8_t g = bgra[i * 4 + 1];
    uint8_t r = bgra[i * 4 + 2];

    // Standard Luminance: 0.299R + 0.587G + 0.114B
    out_gray[i] =
        (uint8_t)(0.299f * (float)r + 0.587f * (float)g + 0.114f * (float)b);
  }
}

// --- Task 3: Transformer Stub ---
void guru_transformer_forward(const float *input, float *output, size_t size) {
  memcpy(output, input, size * sizeof(float));
}
}
