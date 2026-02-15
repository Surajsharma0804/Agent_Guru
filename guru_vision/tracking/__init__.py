"""
GuruVision Face Tracking Module

Provides face tracking across video frames with stable tracking IDs.
"""

from .tracker import FaceTracker, Track, KalmanFilter

__all__ = ['FaceTracker', 'Track', 'KalmanFilter']
