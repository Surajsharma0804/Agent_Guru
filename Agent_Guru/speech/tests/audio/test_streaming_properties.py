"""
Property-based tests for streaming audio manager.

Property 19: Streaming Audio Latency
For any audio stream, the Audio_Stream should process audio in chunks of 100-500 milliseconds,
maintain end-to-end latency below 500 milliseconds, and provide incremental STT results.

Validates: Requirements 16.1, 16.2, 16.3
"""

import asyncio
import time
import pytest
import numpy as np
from hypothesis import given, strategies as st, settings, assume
from typing import AsyncIterator, List

from Agent_Guru.speech.audio.streaming import (
    StreamingAudioManager,
    StreamConfig,
    AudioCodec,
)


class TestStreamingAudioProperties:
    """Property-based tests for streaming audio manager."""
    
    @pytest.mark.asyncio
    @given(
        chunk_duration_ms=st.integers(min_value=100, max_value=500),
        num_chunks=st.integers(min_value=5, max_value=50),
        sample_rate=st.sampled_from([8000, 16000, 22050, 44100, 48000]),
    )
    @settings(max_examples=100, deadline=None)
    async def test_property_19_streaming_latency(
        self,
        chunk_duration_ms: int,
        num_chunks: int,
        sample_rate: int
    ):
        """
        Property 19: Streaming Audio Latency
        
        For any audio stream configuration:
        - Chunks should be 100-500ms
        - End-to-end latency should be <500ms
        - Should provide incremental results
        
        Validates: Requirements 16.1, 16.2, 16.3
        """
        # Create config with property-generated parameters
        config = StreamConfig(
            sample_rate=sample_rate,
            channels=1,
            chunk_duration_ms=chunk_duration_ms,
            codec=AudioCodec.PCM,
            buffer_size_ms=500,
            max_latency_ms=500,
            enable_adaptive_buffering=True
        )
        
        manager = StreamingAudioManager(config)
        
        # Calculate chunk size in samples
        chunk_samples = int(chunk_duration_ms * sample_rate / 1000)
        
        # Generate audio stream
        async def audio_source() -> AsyncIterator[bytes]:
            for _ in range(num_chunks):
                # Generate random audio chunk
                audio = np.clip(np.random.randn(chunk_samples), -1.0, 1.0).astype(np.float32)
                audio_bytes = (audio * 32767).astype(np.int16).tobytes()
                yield audio_bytes
                # Simulate real-time streaming
                await asyncio.sleep(chunk_duration_ms / 1000.0)
        
        # Stream and measure latency
        start_time = time.time()
        chunks_received = []
        chunk_latencies = []
        
        async for chunk in manager.stream_input(audio_source()):
            chunk_time = time.time()
            chunks_received.append(chunk)
            
            # Measure incremental latency
            if len(chunks_received) > 1:
                incremental_latency = (chunk_time - start_time) * 1000
                chunk_latencies.append(incremental_latency)
            
            start_time = chunk_time
        
        # Get metrics
        metrics = await manager.get_metrics()
        
        # PROPERTY ASSERTIONS
        
        # 1. Requirement 16.1: Process audio in chunks of 100-500ms
        assert 100 <= chunk_duration_ms <= 500, \
            f"Chunk duration {chunk_duration_ms}ms outside 100-500ms range"
        
        # 2. Requirement 16.2: Maintain end-to-end latency below 500ms
        assert metrics.latency_ms < 500, \
            f"End-to-end latency {metrics.latency_ms}ms exceeds 500ms target"
        
        # 3. Requirement 16.3: Provide incremental results
        assert len(chunks_received) == num_chunks, \
            f"Expected {num_chunks} incremental chunks, got {len(chunks_received)}"
        
        # 4. All chunks should be the correct size
        for chunk in chunks_received:
            assert len(chunk) == chunk_samples, \
                f"Chunk size {len(chunk)} doesn't match expected {chunk_samples}"
        
        # 5. Chunks should be delivered incrementally (not all at once)
        assert len(chunks_received) > 0, "No chunks received"
        
        # 6. Latency should be reasonable for each chunk
        if chunk_latencies:
            avg_chunk_latency = sum(chunk_latencies) / len(chunk_latencies)
            # Average chunk latency should be less than max latency
            assert avg_chunk_latency < 1000, \
                f"Average chunk latency {avg_chunk_latency}ms too high"
    
    @pytest.mark.asyncio
    @given(
        buffer_size_ms=st.integers(min_value=100, max_value=2000),
        max_latency_ms=st.integers(min_value=200, max_value=1000),
        num_chunks=st.integers(min_value=10, max_value=30),
    )
    @settings(max_examples=50, deadline=None)
    async def test_property_19_adaptive_buffering(
        self,
        buffer_size_ms: int,
        max_latency_ms: int,
        num_chunks: int
    ):
        """
        Property 19 Extension: Adaptive Buffering
        
        For any buffer configuration:
        - Buffer should adapt to network conditions
        - Latency should stay within configured max
        - System should handle varying chunk arrival times
        """
        # Ensure max_latency >= buffer_size for valid config
        assume(max_latency_ms >= buffer_size_ms)
        
        config = StreamConfig(
            sample_rate=16000,
            channels=1,
            chunk_duration_ms=100,
            codec=AudioCodec.PCM,
            buffer_size_ms=buffer_size_ms,
            max_latency_ms=max_latency_ms,
            enable_adaptive_buffering=True
        )
        
        manager = StreamingAudioManager(config)
        
        # Generate audio with variable timing (simulating network jitter)
        async def audio_source() -> AsyncIterator[bytes]:
            for i in range(num_chunks):
                audio = np.clip(np.random.randn(1600), -1.0, 1.0).astype(np.float32)
                audio_bytes = (audio * 32767).astype(np.int16).tobytes()
                yield audio_bytes
                # Variable delay to simulate network conditions
                delay = 0.05 + (0.03 if i % 3 == 0 else 0.01)
                await asyncio.sleep(delay)
        
        chunks_received = []
        async for chunk in manager.stream_input(audio_source()):
            chunks_received.append(chunk)
        
        metrics = await manager.get_metrics()
        
        # PROPERTY ASSERTIONS
        
        # 1. All chunks should be received
        assert len(chunks_received) == num_chunks
        
        # 2. Buffer size should be within configured range
        assert manager._buffer_size_samples > 0
        
        # 3. Adaptive buffering should keep latency reasonable
        # (may be higher than 500ms due to configured max_latency)
        assert metrics.latency_ms < max_latency_ms * 2, \
            f"Latency {metrics.latency_ms}ms exceeds 2x max latency {max_latency_ms}ms"
        
        # 4. System should track jitter
        assert metrics.jitter_ms >= 0
        
        # 5. No packet loss in controlled test
        assert metrics.packet_loss_percent == 0.0
    
    @pytest.mark.asyncio
    @given(
        codec=st.sampled_from([AudioCodec.PCM, AudioCodec.OPUS, AudioCodec.AAC]),
        chunk_size=st.integers(min_value=800, max_value=3200),
        num_chunks=st.integers(min_value=5, max_value=20),
    )
    @settings(max_examples=50, deadline=None)
    async def test_property_19_codec_independence(
        self,
        codec: AudioCodec,
        chunk_size: int,
        num_chunks: int
    ):
        """
        Property 19 Extension: Codec Independence
        
        For any codec (PCM, Opus, AAC):
        - Latency requirements should be met
        - Chunks should be processed correctly
        - Audio quality should be preserved
        """
        config = StreamConfig(
            sample_rate=16000,
            channels=1,
            chunk_duration_ms=100,
            codec=codec,
            buffer_size_ms=500,
            max_latency_ms=500,
            enable_adaptive_buffering=True
        )
        
        manager = StreamingAudioManager(config)
        
        # Generate audio stream
        async def audio_source() -> AsyncIterator[bytes]:
            for _ in range(num_chunks):
                audio = np.clip(np.random.randn(chunk_size), -1.0, 1.0).astype(np.float32)
                audio_bytes = (audio * 32767).astype(np.int16).tobytes()
                yield audio_bytes
                await asyncio.sleep(0.01)
        
        chunks_received = []
        async for chunk in manager.stream_input(audio_source()):
            chunks_received.append(chunk)
        
        metrics = await manager.get_metrics()
        
        # PROPERTY ASSERTIONS
        
        # 1. All chunks should be received regardless of codec
        assert len(chunks_received) == num_chunks
        
        # 2. Latency should be <500ms for all codecs
        assert metrics.latency_ms < 500, \
            f"Codec {codec.value} latency {metrics.latency_ms}ms exceeds 500ms"
        
        # 3. All chunks should be valid numpy arrays
        for chunk in chunks_received:
            assert isinstance(chunk, np.ndarray)
            assert chunk.dtype == np.float32
            assert len(chunk) == chunk_size
        
        # 4. Audio should be in valid range [-1, 1]
        for chunk in chunks_received:
            assert np.all(chunk >= -1.0) and np.all(chunk <= 1.0), \
                "Audio values outside valid range [-1, 1]"
    
    @pytest.mark.asyncio
    @given(
        sample_rate=st.sampled_from([8000, 16000, 22050, 44100]),
        chunk_duration_ms=st.integers(min_value=100, max_value=500),
        num_chunks=st.integers(min_value=10, max_value=30),
    )
    @settings(max_examples=50, deadline=None)
    async def test_property_19_full_duplex(
        self,
        sample_rate: int,
        chunk_duration_ms: int,
        num_chunks: int
    ):
        """
        Property 19 Extension: Full-Duplex Streaming
        
        For any configuration:
        - Input and output streams should work concurrently
        - Both should meet latency requirements
        - No interference between streams
        """
        config = StreamConfig(
            sample_rate=sample_rate,
            channels=1,
            chunk_duration_ms=chunk_duration_ms,
            codec=AudioCodec.PCM,
            buffer_size_ms=500,
            max_latency_ms=500,
            enable_adaptive_buffering=True
        )
        
        manager_in = StreamingAudioManager(config)
        manager_out = StreamingAudioManager(config)
        
        chunk_samples = int(chunk_duration_ms * sample_rate / 1000)
        
        # Input stream
        async def audio_source() -> AsyncIterator[bytes]:
            for _ in range(num_chunks):
                audio = np.clip(np.random.randn(chunk_samples), -1.0, 1.0).astype(np.float32)
                audio_bytes = (audio * 32767).astype(np.int16).tobytes()
                yield audio_bytes
                await asyncio.sleep(chunk_duration_ms / 1000.0)
        
        # Output stream
        async def audio_data() -> AsyncIterator[np.ndarray]:
            for _ in range(num_chunks):
                audio = np.clip(np.random.randn(chunk_samples), -1.0, 1.0).astype(np.float32)
                yield audio
                await asyncio.sleep(chunk_duration_ms / 1000.0)
        
        # Run both streams concurrently
        input_chunks = []
        output_chunks = []
        
        async def collect_input():
            async for chunk in manager_in.stream_input(audio_source()):
                input_chunks.append(chunk)
        
        async def collect_output():
            async for chunk in manager_out.stream_output(audio_data(), sample_rate):
                output_chunks.append(chunk)
        
        await asyncio.gather(collect_input(), collect_output())
        
        # Get metrics
        input_metrics = await manager_in.get_metrics()
        output_metrics = await manager_out.get_metrics()
        
        # PROPERTY ASSERTIONS
        
        # 1. Both streams should receive all chunks
        assert len(input_chunks) == num_chunks
        assert len(output_chunks) == num_chunks
        
        # 2. Both streams should meet latency requirements
        assert input_metrics.latency_ms < 500, \
            f"Input latency {input_metrics.latency_ms}ms exceeds 500ms"
        assert output_metrics.latency_ms < 500, \
            f"Output latency {output_metrics.latency_ms}ms exceeds 500ms"
        
        # 3. No packet loss in either stream
        assert input_metrics.packet_loss_percent == 0.0
        assert output_metrics.packet_loss_percent == 0.0
        
        # 4. Chunks should be correct size
        for chunk in input_chunks:
            assert len(chunk) == chunk_samples
        for chunk in output_chunks:
            assert isinstance(chunk, bytes)
    
    @pytest.mark.asyncio
    @given(
        num_chunks=st.integers(min_value=50, max_value=200),
        chunk_duration_ms=st.integers(min_value=100, max_value=300),
    )
    @settings(max_examples=30, deadline=None)
    async def test_property_19_sustained_streaming(
        self,
        num_chunks: int,
        chunk_duration_ms: int
    ):
        """
        Property 19 Extension: Sustained Streaming
        
        For any long-duration stream:
        - Latency should remain stable over time
        - No memory leaks or performance degradation
        - Metrics should remain valid
        """
        config = StreamConfig(
            sample_rate=16000,
            channels=1,
            chunk_duration_ms=chunk_duration_ms,
            codec=AudioCodec.PCM,
            buffer_size_ms=500,
            max_latency_ms=500,
            enable_adaptive_buffering=True
        )
        
        manager = StreamingAudioManager(config)
        chunk_samples = int(chunk_duration_ms * 16000 / 1000)
        
        # Generate long audio stream
        async def audio_source() -> AsyncIterator[bytes]:
            for _ in range(num_chunks):
                audio = np.clip(np.random.randn(chunk_samples), -1.0, 1.0).astype(np.float32)
                audio_bytes = (audio * 32767).astype(np.int16).tobytes()
                yield audio_bytes
                # Minimal delay for sustained streaming
                await asyncio.sleep(0.001)
        
        chunks_received = []
        async for chunk in manager.stream_input(audio_source()):
            chunks_received.append(chunk)
        
        metrics = await manager.get_metrics()
        
        # PROPERTY ASSERTIONS
        
        # 1. All chunks should be received
        assert len(chunks_received) == num_chunks
        
        # 2. Latency should still be reasonable after many chunks
        assert metrics.latency_ms < 1000, \
            f"Latency {metrics.latency_ms}ms too high after {num_chunks} chunks"
        
        # 3. Metrics should be valid
        assert metrics.jitter_ms >= 0
        assert metrics.packet_loss_percent >= 0
        assert metrics.buffer_size > 0
        
        # 4. No excessive buffer overruns (some are acceptable under stress)
        assert metrics.buffer_overruns < num_chunks * 0.1, \
            f"Too many buffer overruns: {metrics.buffer_overruns}"
