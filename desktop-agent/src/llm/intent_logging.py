"""
Intent Pre-Filter Logging and Monitoring

Comprehensive logging and monitoring system for intent pre-filter decisions,
LLM bypass tracking, and bypass rate monitoring.

Requirement 31.4: Log whether LLM was bypassed for each command
Requirement 31.5: Track bypass rate over rolling window of 100 commands
"""

import logging
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from .intent_pre_filter import PreFilterResult, RoutingDecision


class IntentPreFilterLogger:
    """
    Production-grade logger for intent pre-filter decisions.
    
    Logs all routing decisions with full context for audit and analysis.
    Requirement 31.4: Log whether LLM was bypassed for each command
    """
    
    def __init__(self, log_dir: Optional[Path] = None):
        self.logger = logging.getLogger(__name__)
        
        # Set up log directory
        if log_dir is None:
            log_dir = Path.home() / ".guru" / "logs" / "intent_prefilter"
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Log file paths
        self.decision_log_path = self.log_dir / "prefilter_decisions.jsonl"
        self.bypass_stats_path = self.log_dir / "bypass_statistics.json"
        self.alert_log_path = self.log_dir / "bypass_alerts.jsonl"
        
        self.logger.info(f"Intent pre-filter logger initialized: {self.log_dir}")
        
    def log_decision(
        self, 
        command_text: str, 
        result: PreFilterResult,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None
    ):
        """
        Log a routing decision.
        
        Requirement 31.4: Log whether LLM was bypassed for each command
        
        Args:
            command_text: Original command text
            result: Pre-filter result
            session_id: Optional session ID
            user_id: Optional user ID
        """
        
        log_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'event_type': 'PREFILTER_DECISION',
            'session_id': session_id,
            'user_id': user_id,
            'command_text': command_text,
            'routing_decision': result.routing_decision.value,
            'confidence': result.confidence,
            'bypass_llm': result.bypass_llm,  # Requirement 31.4
            'pattern_matched': result.pattern_matched,
            'parameters_extracted': result.parameters_extracted,
            'parameters_complete': result.parameters_complete,
            'ambiguity_reason': result.ambiguity_reason,
            'requires_clarification': result.requires_clarification,
            'processing_time_ms': result.processing_time_ms,
            'patterns_evaluated': result.patterns_evaluated,
            'success': result.success,
            'error': result.error,
            'warnings': result.warnings
        }
        
        # Add intent details if available
        if result.intent:
            log_entry['intent'] = {
                'intent_type': result.intent.intent_type.value,
                'parameters': result.intent.parameters,
                'confidence': result.intent.confidence,
                'risk_level': result.intent.risk_level
            }
            
        # Write to JSONL file
        try:
            with open(self.decision_log_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_entry) + '\n')
        except Exception as e:
            self.logger.error(f"Failed to write decision log: {e}")
            
        # Log to standard logger
        if result.bypass_llm:
            self.logger.info(
                f"LLM BYPASSED: {result.routing_decision.value} "
                f"(confidence: {result.confidence:.2f}, "
                f"pattern: {result.pattern_matched})"
            )
        else:
            self.logger.info(
                f"LLM REQUIRED: {result.routing_decision.value} "
                f"(confidence: {result.confidence:.2f})"
            )
            
    def log_bypass_statistics(self, statistics: Dict[str, Any]):
        """
        Log bypass statistics snapshot.
        
        Requirement 31.5: Track bypass rate over rolling window
        
        Args:
            statistics: Statistics dictionary from IntentPreFilter
        """
        
        stats_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'event_type': 'BYPASS_STATISTICS',
            **statistics
        }
        
        # Write to JSON file (overwrite with latest)
        try:
            with open(self.bypass_stats_path, 'w', encoding='utf-8') as f:
                json.dump(stats_entry, f, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to write bypass statistics: {e}")
            
        # Log summary
        self.logger.info(
            f"Bypass Statistics: "
            f"Total: {statistics['total_commands']}, "
            f"Bypassed: {statistics['bypassed_commands']}, "
            f"Bypass Rate: {statistics['bypass_rate']:.1%}, "
            f"Recent Rate: {statistics['recent_bypass_rate']:.1%}"
        )
        
    def log_bypass_rate_alert(
        self, 
        recent_rate: float, 
        threshold: float,
        target_rate: float,
        statistics: Dict[str, Any]
    ):
        """
        Log a low bypass rate alert.
        
        Requirement 31.5: Alert if bypass rate drops below 70%
        
        Args:
            recent_rate: Current recent bypass rate
            threshold: Alert threshold
            target_rate: Target bypass rate
            statistics: Full statistics dictionary
        """
        
        alert_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'event_type': 'LOW_BYPASS_RATE_ALERT',
            'severity': 'WARNING',
            'recent_bypass_rate': recent_rate,
            'alert_threshold': threshold,
            'target_bypass_rate': target_rate,
            'gap_from_target': target_rate - recent_rate,
            'statistics': statistics,
            'message': (
                f"Recent bypass rate ({recent_rate:.1%}) is below alert threshold ({threshold:.1%}). "
                f"Target is {target_rate:.1%}. Consider reviewing action patterns."
            )
        }
        
        # Write to alert log
        try:
            with open(self.alert_log_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(alert_entry) + '\n')
        except Exception as e:
            self.logger.error(f"Failed to write bypass alert: {e}")
            
        # Log to standard logger with WARNING level
        self.logger.warning(
            f"LOW BYPASS RATE ALERT: Recent rate {recent_rate:.1%} < threshold {threshold:.1%}. "
            f"Target: {target_rate:.1%}. Gap: {(target_rate - recent_rate):.1%}"
        )
        
    def get_recent_decisions(self, limit: int = 100) -> list:
        """
        Get recent routing decisions from log.
        
        Args:
            limit: Maximum number of decisions to return
            
        Returns:
            List of recent decision log entries
        """
        
        decisions = []
        
        try:
            if self.decision_log_path.exists():
                with open(self.decision_log_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    
                # Get last N lines
                recent_lines = lines[-limit:] if len(lines) > limit else lines
                
                for line in recent_lines:
                    try:
                        decisions.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
                        
        except Exception as e:
            self.logger.error(f"Failed to read decision log: {e}")
            
        return decisions
        
    def get_bypass_statistics(self) -> Optional[Dict[str, Any]]:
        """
        Get latest bypass statistics from log.
        
        Returns:
            Latest statistics dictionary or None if not available
        """
        
        try:
            if self.bypass_stats_path.exists():
                with open(self.bypass_stats_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            self.logger.error(f"Failed to read bypass statistics: {e}")
            
        return None
        
    def get_recent_alerts(self, limit: int = 10) -> list:
        """
        Get recent bypass rate alerts from log.
        
        Args:
            limit: Maximum number of alerts to return
            
        Returns:
            List of recent alert log entries
        """
        
        alerts = []
        
        try:
            if self.alert_log_path.exists():
                with open(self.alert_log_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    
                # Get last N lines
                recent_lines = lines[-limit:] if len(lines) > limit else lines
                
                for line in recent_lines:
                    try:
                        alerts.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
                        
        except Exception as e:
            self.logger.error(f"Failed to read alert log: {e}")
            
        return alerts
        
    def analyze_bypass_trends(self, window_size: int = 100) -> Dict[str, Any]:
        """
        Analyze bypass rate trends over recent decisions.
        
        Args:
            window_size: Number of recent decisions to analyze
            
        Returns:
            Dictionary with trend analysis
        """
        
        decisions = self.get_recent_decisions(window_size)
        
        if not decisions:
            return {
                'total_decisions': 0,
                'bypass_rate': 0.0,
                'trend': 'insufficient_data'
            }
            
        # Calculate bypass rate
        bypassed = sum(1 for d in decisions if d.get('bypass_llm', False))
        bypass_rate = bypassed / len(decisions)
        
        # Calculate trend (compare first half vs second half)
        mid_point = len(decisions) // 2
        first_half = decisions[:mid_point]
        second_half = decisions[mid_point:]
        
        first_half_bypassed = sum(1 for d in first_half if d.get('bypass_llm', False))
        second_half_bypassed = sum(1 for d in second_half if d.get('bypass_llm', False))
        
        first_half_rate = first_half_bypassed / len(first_half) if first_half else 0.0
        second_half_rate = second_half_bypassed / len(second_half) if second_half else 0.0
        
        rate_change = second_half_rate - first_half_rate
        
        if rate_change > 0.05:
            trend = 'improving'
        elif rate_change < -0.05:
            trend = 'declining'
        else:
            trend = 'stable'
            
        # Analyze routing decisions
        routing_counts = {}
        for decision in decisions:
            routing = decision.get('routing_decision', 'unknown')
            routing_counts[routing] = routing_counts.get(routing, 0) + 1
            
        return {
            'total_decisions': len(decisions),
            'bypass_rate': bypass_rate,
            'first_half_rate': first_half_rate,
            'second_half_rate': second_half_rate,
            'rate_change': rate_change,
            'trend': trend,
            'routing_distribution': routing_counts,
            'average_confidence': sum(d.get('confidence', 0.0) for d in decisions) / len(decisions),
            'average_processing_time_ms': sum(d.get('processing_time_ms', 0) for d in decisions) / len(decisions)
        }
        
    def generate_report(self) -> str:
        """
        Generate a comprehensive bypass rate report.
        
        Returns:
            Formatted report string
        """
        
        statistics = self.get_bypass_statistics()
        trends = self.analyze_bypass_trends()
        recent_alerts = self.get_recent_alerts(5)
        
        report_lines = [
            "=" * 80,
            "INTENT PRE-FILTER BYPASS RATE REPORT",
            "=" * 80,
            "",
            "CURRENT STATISTICS:",
            "-" * 80
        ]
        
        if statistics:
            report_lines.extend([
                f"  Total Commands: {statistics.get('total_commands', 0)}",
                f"  Bypassed Commands: {statistics.get('bypassed_commands', 0)}",
                f"  LLM Required Commands: {statistics.get('llm_required_commands', 0)}",
                f"  Ambiguous Commands: {statistics.get('ambiguous_commands', 0)}",
                f"  Overall Bypass Rate: {statistics.get('bypass_rate', 0.0):.1%}",
                f"  Recent Bypass Rate (100 commands): {statistics.get('recent_bypass_rate', 0.0):.1%}",
                f"  Target Bypass Rate: {statistics.get('target_bypass_rate', 0.0):.1%}",
                f"  Alert Threshold: {statistics.get('alert_bypass_threshold', 0.0):.1%}",
                f"  Average Processing Time: {statistics.get('average_processing_time_ms', 0.0):.2f}ms",
                ""
            ])
        else:
            report_lines.append("  No statistics available")
            report_lines.append("")
            
        report_lines.extend([
            "TREND ANALYSIS:",
            "-" * 80,
            f"  Trend: {trends.get('trend', 'unknown').upper()}",
            f"  First Half Rate: {trends.get('first_half_rate', 0.0):.1%}",
            f"  Second Half Rate: {trends.get('second_half_rate', 0.0):.1%}",
            f"  Rate Change: {trends.get('rate_change', 0.0):+.1%}",
            f"  Average Confidence: {trends.get('average_confidence', 0.0):.2f}",
            ""
        ])
        
        if recent_alerts:
            report_lines.extend([
                "RECENT ALERTS:",
                "-" * 80
            ])
            for alert in recent_alerts:
                report_lines.append(
                    f"  [{alert.get('timestamp', 'unknown')}] "
                    f"Rate: {alert.get('recent_bypass_rate', 0.0):.1%} "
                    f"(Gap: {alert.get('gap_from_target', 0.0):.1%})"
                )
            report_lines.append("")
        else:
            report_lines.extend([
                "RECENT ALERTS:",
                "-" * 80,
                "  No recent alerts",
                ""
            ])
            
        report_lines.extend([
            "ROUTING DISTRIBUTION:",
            "-" * 80
        ])
        
        routing_dist = trends.get('routing_distribution', {})
        for routing, count in routing_dist.items():
            percentage = (count / trends.get('total_decisions', 1)) * 100
            report_lines.append(f"  {routing}: {count} ({percentage:.1f}%)")
            
        report_lines.extend([
            "",
            "=" * 80
        ])
        
        return "\n".join(report_lines)
        
    def cleanup_old_logs(self, days_to_keep: int = 30):
        """
        Clean up old log files.
        
        Args:
            days_to_keep: Number of days of logs to keep
        """
        
        # This is a placeholder for log rotation/cleanup logic
        # In production, you would implement proper log rotation
        self.logger.info(f"Log cleanup: keeping last {days_to_keep} days")
