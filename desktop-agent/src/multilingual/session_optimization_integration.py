"""
Session-Based Performance Optimization Integration

IMPLEMENTS REQUIREMENTS 9.2, 9.5:
- 9.2: Create language context caching per session
- 9.5: Optimize repeated language detection and normalization

This module provides integration examples and utilities for session-based
performance optimization in the multilingual processing pipeline.
"""

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from .configuration import MultilingualConfig
from .intent_normalization import IntentNormalizationLayer
from .language_detection import LanguageDetectionEngine
from .performance_optimization import PerformanceOptimizationManager


class SessionOptimizedMultilingualProcessor:
    """
    Multilingual processor with integrated session-based optimization.
    
    This class demonstrates how to integrate session-based performance
    optimization into the multilingual processing pipeline.
    """
    
    def __init__(self, config: MultilingualConfig):
        self.logger = logging.getLogger(__name__)
        self.config = config
        
        # Initialize core components
        self.language_detector = LanguageDetectionEngine(config)
        self.intent_normalizer = IntentNormalizationLayer(config)
        
        # Initialize performance optimization
        self.perf_manager = PerformanceOptimizationManager(config)
        
        self.logger.info("Session-optimized multilingual processor initialized")
        
    def process_voice_command(self,
                              session_id: str,
                              audio_data: bytes,
                              mode: str = 'command') -> Dict[str, Any]:
        """
        Process voice command with session-based optimization.
        
        Args:
            session_id: Session identifier for context tracking
            audio_data: Raw audio data
            mode: Processing mode ('command' or 'dictation')
            
        Returns:
            Processing result with performance metrics
        """
        start_time = datetime.utcnow()
        
        # Step 1: Optimized language detection
        detection_result, detection_metrics = self.perf_manager.optimize_language_detection(
            session_id=session_id,
            audio_data=audio_data,
            detection_func=lambda audio: self.language_detector.detect_language(audio, session_id=session_id)
        )
        
        if not detection_result.success:
            return {
                'success': False,
                'error': detection_result.error,
                'metrics': detection_metrics
            }
            
        # Step 2: Optimized intent normalization (if command mode)
        if mode == 'command':
            # For this example, assume we have transcribed text
            # In production, this would come from speech-to-text
            transcribed_text = f"test command in {detection_result.language}"
            
            normalized_intent, normalization_metrics = self.perf_manager.optimize_intent_normalization(
                session_id=session_id,
                text=transcribed_text,
                language=detection_result.language,
                normalization_func=lambda text, lang: self.intent_normalizer.normalize_intent(text, lang, mode)
            )
            
            total_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            return {
                'success': True,
                'language': detection_result.language,
                'confidence': detection_result.confidence,
                'intent': normalized_intent,
                'mode': mode,
                'metrics': {
                    'total_time_ms': total_time_ms,
                    'detection': detection_metrics,
                    'normalization': normalization_metrics
                }
            }
        else:
            # Dictation mode - no normalization
            total_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            return {
                'success': True,
                'language': detection_result.language,
                'confidence': detection_result.confidence,
                'mode': mode,
                'metrics': {
                    'total_time_ms': total_time_ms,
                    'detection': detection_metrics
                }
            }
            
    def get_session_performance_report(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get comprehensive performance report for a session."""
        return self.perf_manager.get_session_statistics(session_id)
        
    def optimize_for_session_pattern(self, session_id: str):
        """
        Optimize processing based on observed session patterns.
        
        This method analyzes session usage patterns and adjusts
        optimization strategies accordingly.
        """
        session_stats = self.perf_manager.get_session_statistics(session_id)
        
        if not session_stats:
            return
            
        # Adaptive threshold adjustment based on performance
        if session_stats['cache_hit_rate'] > 80:
            # High cache hit rate - can be slightly more lenient with thresholds
            self.perf_manager.update_adaptive_threshold(
                session_id=session_id,
                threshold_type='detection_confidence',
                performance_metric=0.95
            )
        elif session_stats['cache_hit_rate'] < 40:
            # Low cache hit rate - be more strict to ensure quality
            self.perf_manager.update_adaptive_threshold(
                session_id=session_id,
                threshold_type='detection_confidence',
                performance_metric=0.70
            )
            
        self.logger.info(
            f"Optimized session {session_id}: "
            f"cache_hit_rate={session_stats['cache_hit_rate']:.1f}%, "
            f"avg_detection_time={session_stats['average_detection_time_ms']:.1f}ms"
        )
        
    def cleanup_session(self, session_id: str):
        """Clean up session-specific optimization data."""
        # Session cleanup is handled automatically by the performance manager
        # This method is provided for explicit cleanup if needed
        self.logger.info(f"Session {session_id} cleanup requested")
        
    def get_comprehensive_statistics(self) -> Dict[str, Any]:
        """Get comprehensive performance statistics across all sessions."""
        return self.perf_manager.get_comprehensive_statistics()
        
    def shutdown(self):
        """Shutdown processor and cleanup resources."""
        self.perf_manager.cleanup()
        self.logger.info("Session-optimized multilingual processor shutdown")


# Example usage and integration patterns
def example_session_optimization_workflow():
    """
    Example workflow demonstrating session-based optimization.
    
    This function shows how to use session-based optimization in a
    typical multilingual processing scenario.
    """
    # Create configuration
    config = MultilingualConfig(
        enabled_languages=['en', 'hi', 'ta'],
        primary_language='en',
        fallback_language='en',
        performance_monitoring=True
    )
    
    # Create processor
    processor = SessionOptimizedMultilingualProcessor(config)
    
    # Simulate a session with multiple commands
    session_id = "user_session_123"
    
    # Process multiple commands in the session
    for i in range(5):
        audio_data = b'\x00' * 1000  # Mock audio data
        
        result = processor.process_voice_command(
            session_id=session_id,
            audio_data=audio_data,
            mode='command'
        )
        
        print(f"Command {i+1}: {result['success']}, "
              f"Language: {result.get('language')}, "
              f"Cache hit: {result['metrics']['detection'].get('cache_hit', False)}")
        
    # Get session performance report
    processor.get_session_performance_report(session_id)
    
    # Optimize based on session patterns
    processor.optimize_for_session_pattern(session_id)
    
    # Get comprehensive statistics
    processor.get_comprehensive_statistics()
    
    # Cleanup
    processor.shutdown()


if __name__ == "__main__":
    # Run example workflow
    example_session_optimization_workflow()
