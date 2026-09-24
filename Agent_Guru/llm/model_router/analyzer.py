"""Module: Agent_Guru.llm.model_router.analyzer
Purpose: Task Analyzer - extracts task features and requirements.

Uses keyword pattern matching and heuristics for fast, dependency-free analysis.
"""

from __future__ import annotations

import re

from Agent_Guru.llm.model_router.models import (
    ModelCapability,
    TaskAnalysis,
    TaskSpecification,
    TaskType,
)

# Keyword patterns for task type classification
_TASK_PATTERNS: dict[TaskType, list] = {
    TaskType.CODE_GENERATION: [
        r"\bwrite\b.*\b(code|function|class|script|program)\b",
        r"\bimplement\b",
        r"\bcreate\b.*\b(function|method|class|module)\b",
        r"\bgenerate\b.*\bcode\b",
        r"\bcode\b.*\bfor\b",
    ],
    TaskType.CODE_REVIEW: [
        r"\breview\b.*\bcode\b",
        r"\bcheck\b.*\bcode\b",
        r"\bfind\b.*\b(bug|issue|error)\b",
        r"\brefactor\b",
        r"\boptimize\b.*\bcode\b",
    ],
    TaskType.REASONING: [
        r"\bwhy\b.*\b(is|are|does|do)\b",
        r"\bexplain\b.*\b(why|how|what)\b",
        r"\banalyze\b",
        r"\breason\b",
        r"\bthink\b.*\bthrough\b",
        r"\bstep.by.step\b",
    ],
    TaskType.DATA_ANALYSIS: [
        r"\banalyze\b.*\bdata\b",
        r"\bstatistic\b",
        r"\bcalculate\b",
        r"\bcompute\b",
        r"\bplot\b",
        r"\bchart\b",
        r"\bdataset\b",
        r"\bcsv\b",
    ],
    TaskType.CREATIVE_WRITING: [
        r"\bwrite\b.*\b(story|poem|essay|article|blog)\b",
        r"\bcreative\b",
        r"\bfiction\b",
        r"\bnarrative\b",
        r"\bcharacter\b",
    ],
    TaskType.SUMMARIZATION: [
        r"\bsummariz",
        r"\bsummar",
        r"\btldr\b",
        r"\bbrief\b.*\bsummary\b",
        r"\bkey\b.*\bpoints\b",
        r"\bsummar(y|ize|ise)\b",
    ],
    TaskType.TRANSLATION: [
        r"\btranslat\b",
        r"\bin\b.*\blanguage\b",
        r"\bfrom\b.*\bto\b.*\b(english|spanish|french|german|chinese|japanese)\b",
    ],
}

# Task type → required capabilities mapping
_TASK_CAPABILITIES: dict[TaskType, set[ModelCapability]] = {
    TaskType.CODE_GENERATION: {ModelCapability.CODE_GENERATION},
    TaskType.CODE_REVIEW: {ModelCapability.CODE_GENERATION, ModelCapability.REASONING},
    TaskType.REASONING: {ModelCapability.REASONING},
    TaskType.DATA_ANALYSIS: {ModelCapability.DATA_ANALYSIS, ModelCapability.REASONING},
    TaskType.CREATIVE_WRITING: {ModelCapability.CREATIVE_WRITING},
    TaskType.CONVERSATION: {ModelCapability.CONVERSATION},
    TaskType.SUMMARIZATION: {ModelCapability.CONVERSATION},
    TaskType.TRANSLATION: {ModelCapability.CONVERSATION},
}

# Tokens per word estimate (rough approximation)
_TOKENS_PER_WORD = 1.3


class TaskAnalyzer:
    """Analyzes task specifications to extract routing requirements.

    All operations are O(n) in content length with no external dependencies.
    """

    def analyze(self, spec: TaskSpecification) -> TaskAnalysis:
        """Analyze a task specification.

        Args:
            spec: Task specification to analyze.

        Returns:
            TaskAnalysis with extracted features.

        """
        task_type = self._classify_task_type(spec.content)
        complexity = self._estimate_complexity(spec.content, task_type)
        input_tokens, output_tokens = self._estimate_tokens(spec.content, task_type)
        capabilities = set(spec.required_capabilities)
        capabilities.update(_TASK_CAPABILITIES.get(task_type, set()))

        return TaskAnalysis(
            task_type=task_type,
            complexity=complexity,
            domain=self._detect_domain(spec.content),
            estimated_input_tokens=input_tokens,
            estimated_output_tokens=output_tokens,
            required_capabilities=capabilities,
            latency_constraint_ms=spec.max_latency_ms,
            cost_constraint=spec.max_cost,
        )

    def _classify_task_type(self, content: str) -> TaskType:
        """Classify task type using keyword pattern matching.

        Returns the task type with the most pattern matches.
        Falls back to CONVERSATION if no patterns match.
        """
        content_lower = content.lower()
        scores: dict[TaskType, int] = {}

        for task_type, patterns in _TASK_PATTERNS.items():
            score = sum(1 for p in patterns if re.search(p, content_lower))
            if score > 0:
                scores[task_type] = score

        if not scores:
            return TaskType.CONVERSATION

        return max(scores, key=lambda t: scores[t])

    def _estimate_complexity(self, content: str, task_type: TaskType) -> str:
        """Estimate task complexity based on content length and task type."""
        word_count = len(content.split())

        # Base complexity from word count
        if word_count < 20:
            base = "low"
        elif word_count < 100:
            base = "medium"
        else:
            base = "high"

        # Reasoning and data analysis are inherently more complex
        if task_type in (TaskType.REASONING, TaskType.DATA_ANALYSIS, TaskType.CODE_REVIEW):
            if base == "low":
                return "medium"
            return "high"

        return base

    def _estimate_tokens(self, content: str, task_type: TaskType) -> tuple[int, int]:
        """Estimate input and output token counts."""
        word_count = len(content.split())
        input_tokens = max(1, int(word_count * _TOKENS_PER_WORD))

        # Output multipliers by task type
        output_multipliers = {
            TaskType.CODE_GENERATION: 3.0,
            TaskType.CODE_REVIEW: 2.0,
            TaskType.REASONING: 2.5,
            TaskType.DATA_ANALYSIS: 2.0,
            TaskType.CREATIVE_WRITING: 4.0,
            TaskType.CONVERSATION: 1.5,
            TaskType.SUMMARIZATION: 0.5,
            TaskType.TRANSLATION: 1.1,
        }
        multiplier = output_multipliers.get(task_type, 1.5)
        output_tokens = max(1, int(input_tokens * multiplier))

        return input_tokens, output_tokens

    def _detect_domain(self, content: str) -> str:
        """Detect the domain of the task from content keywords."""
        content_lower = content.lower()
        domain_keywords = {
            "programming": ["python", "javascript", "java", "code", "function", "class", "api"],
            "mathematics": ["calculate", "equation", "formula", "math", "algebra", "calculus"],
            "science": ["biology", "chemistry", "physics", "experiment", "hypothesis"],
            "business": ["revenue", "profit", "market", "strategy", "customer", "sales"],
            "creative": ["story", "poem", "creative", "fiction", "character", "plot"],
        }
        for domain, keywords in domain_keywords.items():
            if any(kw in content_lower for kw in keywords):
                return domain
        return "general"
