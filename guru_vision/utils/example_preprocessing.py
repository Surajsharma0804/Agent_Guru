"""
Example usage of preprocessing utilities for GuruVision.

This script demonstrates how to use the low-light enhancement and preprocessing
functions in various scenarios.
"""

import cv2
import numpy as np
import time
from guru_vision.utils import enhance_low_light, check_brightness, preprocess_frame


def example_basic_enhancement():
    """Example 1: Basic low-light enhancement."""
    print("=" * 60)
    print("Example 1: Basic Low-Light Enhancement")
    print("=" * 60)
    
    # Create a synthetic dark image
    dark_image = np.ones((480, 640, 3), dtype=np.uint8) * 30
    
    # Add some structure to make it more realistic
    cv2.rectangle(dark_image, (100, 100), (300, 300), (50, 50, 50), -1)
    cv2.circle(dark_image, (450, 240), 80, (40, 40, 40), -1)
    
    print(f"Original brightness: {check_brightness(dark_image):.2f}")
    
    # Apply enhancement
    start_time = time.time()
    enhanced, was_enhanced = enhance_low_light(dark_image)
    processing_time = (time.time() - start_time) * 1000
    
    print(f"Enhancement applied: {was_enhanced}")
    print(f"Enhanced brightness: {check_brightness(enhanced):.2f}")
    print(f"Processing time: {processing_time:.2f}ms")
    print()


def example_brightness_threshold():
    """Example 2: Testing different brightness thresholds."""
    print("=" * 60)
    print("Example 2: Brightness Threshold Testing")
    print("=" * 60)
    
    # Create images with different brightness levels
    brightness_levels = [20, 40, 60, 80, 100, 150]
    
    for brightness in brightness_levels:
        frame = np.ones((100, 100, 3), dtype=np.uint8) * brightness
        
        # Test with default threshold (50)
        _, enhanced_50 = enhance_low_light(frame, brightness_threshold=50.0)
        
        # Test with higher threshold (70)
        _, enhanced_70 = enhance_low_light(frame, brightness_threshold=70.0)
        
        print(f"Brightness {brightness:3d}: "
              f"Enhanced (threshold=50): {enhanced_50}, "
              f"Enhanced (threshold=70): {enhanced_70}")
    print()


def example_color_vs_grayscale():
    """Example 3: Enhancement on color vs grayscale images."""
    print("=" * 60)
    print("Example 3: Color vs Grayscale Enhancement")
    print("=" * 60)
    
    # Create dark color image
    dark_color = np.ones((200, 200, 3), dtype=np.uint8)
    dark_color[:, :, 0] = 30  # Blue channel
    dark_color[:, :, 1] = 35  # Green channel
    dark_color[:, :, 2] = 40  # Red channel
    
    # Create dark grayscale image
    dark_gray = np.ones((200, 200), dtype=np.uint8) * 30
    
    # Enhance both
    enhanced_color, _ = enhance_low_light(dark_color)
    enhanced_gray, _ = enhance_low_light(dark_gray)
    
    print(f"Color image - Original: {check_brightness(dark_color):.2f}, "
          f"Enhanced: {check_brightness(enhanced_color):.2f}")
    print(f"Grayscale image - Original: {check_brightness(dark_gray):.2f}, "
          f"Enhanced: {check_brightness(enhanced_gray):.2f}")
    print(f"Color image shape: {enhanced_color.shape}")
    print(f"Grayscale image shape: {enhanced_gray.shape}")
    print()


def example_preprocessing_pipeline():
    """Example 4: Complete preprocessing pipeline with metadata."""
    print("=" * 60)
    print("Example 4: Complete Preprocessing Pipeline")
    print("=" * 60)
    
    # Create a dark image
    dark_frame = np.ones((480, 640, 3), dtype=np.uint8) * 35
    
    # Apply preprocessing with enhancement enabled
    processed, metadata = preprocess_frame(
        dark_frame,
        enable_low_light_enhancement=True,
        brightness_threshold=50.0
    )
    
    print("Preprocessing Results:")
    print(f"  Low-light enhanced: {metadata['low_light_enhanced']}")
    print(f"  Original brightness: {metadata['original_brightness']:.2f}")
    if metadata['low_light_enhanced']:
        print(f"  Enhanced brightness: {metadata['enhanced_brightness']:.2f}")
        improvement = metadata['enhanced_brightness'] - metadata['original_brightness']
        print(f"  Brightness improvement: +{improvement:.2f}")
    print()


def example_performance_benchmark():
    """Example 5: Performance benchmarking."""
    print("=" * 60)
    print("Example 5: Performance Benchmark")
    print("=" * 60)
    
    # Test different image sizes
    sizes = [(320, 240), (640, 480), (1280, 720), (1920, 1080)]
    
    for width, height in sizes:
        dark_frame = np.ones((height, width, 3), dtype=np.uint8) * 30
        
        # Measure processing time
        times = []
        for _ in range(10):
            start = time.time()
            enhance_low_light(dark_frame)
            times.append((time.time() - start) * 1000)
        
        avg_time = np.mean(times)
        std_time = np.std(times)
        
        print(f"{width}x{height}: {avg_time:.2f}ms ± {std_time:.2f}ms")
    print()


def example_real_world_scenario():
    """Example 6: Simulated real-world video processing."""
    print("=" * 60)
    print("Example 6: Real-World Video Processing Simulation")
    print("=" * 60)
    
    # Simulate processing 100 frames with varying brightness
    num_frames = 100
    enhancement_count = 0
    total_time = 0
    
    print("Processing 100 frames with varying brightness...")
    
    for i in range(num_frames):
        # Simulate varying lighting conditions
        brightness = 30 + (i % 50)  # Varies from 30 to 79
        frame = np.ones((480, 640, 3), dtype=np.uint8) * brightness
        
        start = time.time()
        processed, metadata = preprocess_frame(frame)
        processing_time = (time.time() - start) * 1000
        
        total_time += processing_time
        if metadata['low_light_enhanced']:
            enhancement_count += 1
    
    avg_time = total_time / num_frames
    enhancement_rate = (enhancement_count / num_frames) * 100
    
    print(f"Results:")
    print(f"  Total frames: {num_frames}")
    print(f"  Frames enhanced: {enhancement_count} ({enhancement_rate:.1f}%)")
    print(f"  Average processing time: {avg_time:.2f}ms per frame")
    print(f"  Estimated FPS: {1000/avg_time:.1f}")
    print()


def example_custom_clahe_parameters():
    """Example 7: Custom CLAHE parameters."""
    print("=" * 60)
    print("Example 7: Custom CLAHE Parameters")
    print("=" * 60)
    
    dark_frame = np.ones((480, 640, 3), dtype=np.uint8) * 30
    
    # Test different clip limits
    clip_limits = [1.0, 2.0, 3.0, 4.0]
    
    print("Testing different clip limits:")
    for clip_limit in clip_limits:
        enhanced, _ = enhance_low_light(
            dark_frame,
            clip_limit=clip_limit,
            tile_grid_size=(8, 8)
        )
        brightness = check_brightness(enhanced)
        print(f"  Clip limit {clip_limit}: Enhanced brightness = {brightness:.2f}")
    
    print("\nTesting different tile grid sizes:")
    # Test different tile sizes
    tile_sizes = [(4, 4), (8, 8), (16, 16)]
    
    for tile_size in tile_sizes:
        enhanced, _ = enhance_low_light(
            dark_frame,
            clip_limit=2.0,
            tile_grid_size=tile_size
        )
        brightness = check_brightness(enhanced)
        print(f"  Tile size {tile_size}: Enhanced brightness = {brightness:.2f}")
    print()


def example_edge_cases():
    """Example 8: Edge case handling."""
    print("=" * 60)
    print("Example 8: Edge Case Handling")
    print("=" * 60)
    
    # Test empty frame
    empty_frame = np.array([])
    result, enhanced = enhance_low_light(empty_frame)
    print(f"Empty frame: Enhanced = {enhanced}")
    
    # Test None frame
    result, enhanced = enhance_low_light(None)
    print(f"None frame: Enhanced = {enhanced}")
    
    # Test very small frame
    tiny_frame = np.ones((10, 10, 3), dtype=np.uint8) * 30
    result, enhanced = enhance_low_light(tiny_frame)
    print(f"Tiny frame (10x10): Enhanced = {enhanced}")
    
    # Test very bright frame
    bright_frame = np.ones((100, 100, 3), dtype=np.uint8) * 250
    result, enhanced = enhance_low_light(bright_frame)
    print(f"Very bright frame (brightness=250): Enhanced = {enhanced}")
    
    # Test frame at exact threshold
    threshold_frame = np.ones((100, 100, 3), dtype=np.uint8) * 50
    result, enhanced = enhance_low_light(threshold_frame, brightness_threshold=50.0)
    print(f"Frame at threshold (brightness=50): Enhanced = {enhanced}")
    print()


def main():
    """Run all examples."""
    print("\n" + "=" * 60)
    print("GuruVision Preprocessing Utilities - Examples")
    print("=" * 60 + "\n")
    
    example_basic_enhancement()
    example_brightness_threshold()
    example_color_vs_grayscale()
    example_preprocessing_pipeline()
    example_performance_benchmark()
    example_real_world_scenario()
    example_custom_clahe_parameters()
    example_edge_cases()
    
    print("=" * 60)
    print("All examples completed successfully!")
    print("=" * 60)


if __name__ == '__main__':
    main()
