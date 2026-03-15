"""
Online learning module for continuous model improvement.

This module provides feedback collection, performance tracking, drift detection,
and retraining coordination for the intent detection system.

It also includes behavioral learning for command tracking, pattern detection,
preference learning, proactive suggestions, and persistent goal management.

Note: Self-Improvement Engine components are in Agent_Guru.self_improvement module.
"""

from Agent_Guru.reasoning.learning.app_tracker import AppTracker
from Agent_Guru.reasoning.learning.behavioral_engine import BehavioralEngine
from Agent_Guru.reasoning.learning.command_tracker import CommandTracker
from Agent_Guru.reasoning.learning.feedback_store import FeedbackStore
from Agent_Guru.reasoning.learning.goal_engine import GoalEngine
from Agent_Guru.reasoning.learning.online_learner import OnlineLearner
from Agent_Guru.reasoning.learning.pattern_detector import PatternDetector
from Agent_Guru.reasoning.learning.preference_learner import PreferenceLearner
from Agent_Guru.reasoning.learning.suggestion_generator import SuggestionGenerator

__all__ = [
    # Behavioral Learning
    "FeedbackStore",
    "OnlineLearner",
    "CommandTracker",
    "PatternDetector",
    "AppTracker",
    "PreferenceLearner",
    "SuggestionGenerator",
    "BehavioralEngine",
    "GoalEngine",
]
