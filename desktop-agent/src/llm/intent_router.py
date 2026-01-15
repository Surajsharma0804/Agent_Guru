"""
Intent Router with LLM Restriction

Production-grade intent routing system that enforces deterministic-first guarantee
and restricts LLM usage to genuine ambiguity only.

Requirement 31.3: Only invoke LLM for ambiguous targets, vague pronouns, or clarification
"""

import logging
from typing import Optional

from .intent import StructuredIntent
from .intent_pre_filter import IntentPreFilter, PreFilterResult, RoutingDecision
from .intent_logging import IntentPreFilterLogger
from .adapter import LLMAdapter
from .exceptions import IntentValidationError


class IntentRouter:
    """
    Production-grade intent router with deterministic-first guarantee.
    
    Enforces Requirement 31.3: LLM only for genuine ambiguity
    """
    
    def __init__(
        self, 
        pre_filter: Optional[IntentPreFilter] = None,
        llm_adapter: Optional[LLMAdapter] = None,
        logger: Optional[IntentPreFilterLogger] = None
    ):
        self.logger = logging.getLogger(__name__)
        
        # Initialize components
        self.pre_filter = pre_filter or IntentPreFilter()
        self.llm_adapter = llm_adapter
        self.intent_logger = logger or IntentPreFilterLogger()
        
        # Statistics
        self._total_routes = 0
        self._deterministic_routes = 0
        self._llm_routes = 0
        self._ambiguous_routes = 0
        
        self.logger.info("Intent router initialized with deterministic-first guarantee")
        
    def route_intent(
        self, 
        command_text: str,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> StructuredIntent:
        """
        Route command to appropriate processing path.
        
        Enforces Requirement 31.3: LLM only for genuine ambiguity
        
        Args:
            command_text: User command text
            session_id: Optional session ID
            user_id: Optional user ID
            
        Returns:
            StructuredIntent ready for execution
            
        Raises:
            IntentValidationError: If intent cannot be determined
        """
        
        self._total_routes += 1
        
        # Step 1: Pre-filter classification (deterministic routing)
        pre_filter_result = self.pre_filter.classify(command_text)
        
        # Log the decision (Requirement 31.4)
        self.intent_logger.log_decision(
            command_text, 
            pre_filter_result,
            session_id=session_id,
            user_id=user_id
        )
        
        # Step 2: Route based on decision
        if pre_filter_result.routing_decision == RoutingDecision.DETERMINISTIC:
            # Deterministic route: bypass LLM (Requirement 31.1, 31.2)
            self._deterministic_routes += 1
            
            if pre_filter_result.intent is None:
                raise IntentValidationError(
                    "Deterministic routing failed: no intent created",
                    validation_errors=["Pre-filter returned deterministic decision but no intent"],
                    raw_response=command_text
                )
                
            self.logger.info(
                f"DETERMINISTIC ROUTE: {pre_filter_result.intent.intent_type.value} "
                f"(bypassed LLM, confidence: {pre_filter_result.confidence:.2f})"
            )
            
            return pre_filter_result.intent
            
        elif pre_filter_result.routing_decision == RoutingDecision.AMBIGUOUS:
            # Ambiguous route: requires LLM clarification (Requirement 31.3)
            self._ambiguous_routes += 1
            
            if not self.llm_adapter:
                raise IntentValidationError(
                    "LLM required for ambiguous command but no LLM adapter available",
                    validation_errors=[f"Ambiguity: {pre_filter_result.ambiguity_reason}"],
                    raw_response=command_text
                )
                
            self.logger.info(
                f"AMBIGUOUS ROUTE: Invoking LLM for clarification "
                f"(reason: {pre_filter_result.ambiguity_reason})"
            )
            
            # Invoke LLM with explicit ambiguity context
            return self._invoke_llm_for_ambiguity(
                command_text, 
                pre_filter_result,
                session_id=session_id
            )
            
        elif pre_filter_result.routing_decision == RoutingDecision.LLM_REQUIRED:
            # LLM required route: no deterministic pattern matched
            self._llm_routes += 1
            
            if not self.llm_adapter:
                raise IntentValidationError(
                    "LLM required but no LLM adapter available",
                    validation_errors=["No deterministic pattern matched"],
                    raw_response=command_text
                )
                
            self.logger.info(
                f"LLM REQUIRED ROUTE: No deterministic pattern matched "
                f"(confidence: {pre_filter_result.confidence:.2f})"
            )
            
            # Invoke LLM for intent extraction
            return self._invoke_llm_for_intent(
                command_text,
                session_id=session_id
            )
            
        else:
            raise IntentValidationError(
                f"Unknown routing decision: {pre_filter_result.routing_decision}",
                validation_errors=["Invalid routing decision"],
                raw_response=command_text
            )
            
    def _invoke_llm_for_ambiguity(
        self, 
        command_text: str, 
        pre_filter_result: PreFilterResult,
        session_id: Optional[str] = None
    ) -> StructuredIntent:
        """
        Invoke LLM specifically for ambiguity resolution.
        
        Requirement 31.3: LLM only for ambiguous targets, vague pronouns, or clarification
        """
        
        # Build prompt with ambiguity context
        prompt = self._build_ambiguity_resolution_prompt(command_text, pre_filter_result)
        
        # Invoke LLM
        try:
            llm_response = self.llm_adapter.generate_intent(
                prompt=prompt,
                context={'ambiguity_reason': pre_filter_result.ambiguity_reason}
            )
            
            # Mark as LLM-processed
            llm_response.bypass_llm = False
            
            self.logger.info(
                f"LLM resolved ambiguity: {llm_response.intent_type.value} "
                f"(confidence: {llm_response.confidence:.2f})"
            )
            
            return llm_response
            
        except Exception as e:
            self.logger.error(f"LLM ambiguity resolution failed: {e}")
            raise IntentValidationError(
                f"Failed to resolve ambiguity: {str(e)}",
                validation_errors=[str(e)],
                raw_response=command_text
            )
            
    def _invoke_llm_for_intent(
        self, 
        command_text: str,
        session_id: Optional[str] = None
    ) -> StructuredIntent:
        """
        Invoke LLM for general intent extraction.
        
        Used when no deterministic pattern matches.
        """
        
        # Build standard intent extraction prompt
        prompt = self._build_intent_extraction_prompt(command_text)
        
        # Invoke LLM
        try:
            llm_response = self.llm_adapter.generate_intent(
                prompt=prompt,
                context={'session_id': session_id}
            )
            
            # Mark as LLM-processed
            llm_response.bypass_llm = False
            
            self.logger.info(
                f"LLM extracted intent: {llm_response.intent_type.value} "
                f"(confidence: {llm_response.confidence:.2f})"
            )
            
            return llm_response
            
        except Exception as e:
            self.logger.error(f"LLM intent extraction failed: {e}")
            raise IntentValidationError(
                f"Failed to extract intent: {str(e)}",
                validation_errors=[str(e)],
                raw_response=command_text
            )
            
    def _build_ambiguity_resolution_prompt(
        self, 
        command_text: str, 
        pre_filter_result: PreFilterResult
    ) -> str:
        """Build prompt for ambiguity resolution."""
        
        return f"""Resolve the following ambiguous command:

Command: {command_text}

Ambiguity Detected: {pre_filter_result.ambiguity_reason}

Please clarify the intent and extract structured parameters.
Return a JSON object with:
- intent_type: The type of action (launch_app, type_text, etc.)
- parameters: Dictionary of extracted parameters
- confidence: Confidence score (0.0 to 1.0)

Focus on resolving the ambiguity: {pre_filter_result.ambiguity_reason}
"""
        
    def _build_intent_extraction_prompt(self, command_text: str) -> str:
        """Build prompt for general intent extraction."""
        
        return f"""Extract the intent from the following command:

Command: {command_text}

Return a JSON object with:
- intent_type: The type of action (launch_app, type_text, close_app, etc.)
- parameters: Dictionary of extracted parameters
- confidence: Confidence score (0.0 to 1.0)

Be precise and extract all relevant parameters.
"""
        
    def should_invoke_llm(self, pre_filter_result: PreFilterResult) -> bool:
        """
        Explicit check: should LLM be invoked?
        
        Requirement 31.3: Only invoke LLM for ambiguous targets, vague pronouns, or clarification
        
        Returns:
            True if LLM should be invoked, False otherwise
        """
        
        # LLM should be invoked ONLY if:
        # 1. Routing decision is AMBIGUOUS (vague pronouns, ambiguous targets)
        # 2. Routing decision is LLM_REQUIRED (no deterministic pattern matched)
        
        # LLM should NOT be invoked if:
        # 1. Routing decision is DETERMINISTIC (high confidence, complete parameters)
        
        if pre_filter_result.routing_decision == RoutingDecision.DETERMINISTIC:
            return False
            
        if pre_filter_result.routing_decision in [RoutingDecision.AMBIGUOUS, RoutingDecision.LLM_REQUIRED]:
            return True
            
        return False
        
    def get_routing_statistics(self) -> dict:
        """Get routing statistics."""
        
        total = max(1, self._total_routes)  # Avoid division by zero
        
        stats = {
            'total_routes': self._total_routes,
            'deterministic_routes': self._deterministic_routes,
            'llm_routes': self._llm_routes,
            'ambiguous_routes': self._ambiguous_routes,
            'deterministic_rate': self._deterministic_routes / total,
            'llm_rate': self._llm_routes / total,
            'ambiguous_rate': self._ambiguous_routes / total
        }
        
        # Add pre-filter statistics
        stats['prefilter_stats'] = self.pre_filter.get_statistics()
        
        return stats
        
    def log_statistics(self):
        """Log current routing statistics."""
        
        stats = self.get_routing_statistics()
        
        self.logger.info(
            f"Routing Statistics: "
            f"Total: {stats['total_routes']}, "
            f"Deterministic: {stats['deterministic_routes']} ({stats['deterministic_rate']:.1%}), "
            f"LLM: {stats['llm_routes']} ({stats['llm_rate']:.1%}), "
            f"Ambiguous: {stats['ambiguous_routes']} ({stats['ambiguous_rate']:.1%})"
        )
        
        # Log pre-filter statistics
        self.intent_logger.log_bypass_statistics(stats['prefilter_stats'])
        
    def reset_statistics(self):
        """Reset routing statistics."""
        
        self._total_routes = 0
        self._deterministic_routes = 0
        self._llm_routes = 0
        self._ambiguous_routes = 0
        
        self.pre_filter.reset_statistics()
        
        self.logger.info("Reset routing statistics")
        
    def generate_report(self) -> str:
        """Generate comprehensive routing report."""
        
        stats = self.get_routing_statistics()
        
        report_lines = [
            "=" * 80,
            "INTENT ROUTING REPORT",
            "=" * 80,
            "",
            "ROUTING STATISTICS:",
            "-" * 80,
            f"  Total Routes: {stats['total_routes']}",
            f"  Deterministic Routes: {stats['deterministic_routes']} ({stats['deterministic_rate']:.1%})",
            f"  LLM Routes: {stats['llm_routes']} ({stats['llm_rate']:.1%})",
            f"  Ambiguous Routes: {stats['ambiguous_routes']} ({stats['ambiguous_rate']:.1%})",
            "",
            "PRE-FILTER BYPASS STATISTICS:",
            "-" * 80
        ]
        
        prefilter_stats = stats['prefilter_stats']
        report_lines.extend([
            f"  Total Commands: {prefilter_stats.get('total_commands', 0)}",
            f"  Bypassed Commands: {prefilter_stats.get('bypassed_commands', 0)}",
            f"  Bypass Rate: {prefilter_stats.get('bypass_rate', 0.0):.1%}",
            f"  Recent Bypass Rate: {prefilter_stats.get('recent_bypass_rate', 0.0):.1%}",
            f"  Target Bypass Rate: {prefilter_stats.get('target_bypass_rate', 0.0):.1%}",
            ""
        ])
        
        # Add pre-filter detailed report
        report_lines.append(self.intent_logger.generate_report())
        
        return "\n".join(report_lines)
