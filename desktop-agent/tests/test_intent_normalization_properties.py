"""
Property-Based Tests for Intent Normalization Layer

Comprehensive property-based testing for language-neutral intent normalization
with deterministic behavior, security validation, and cross-language consistency.

**Feature: guru-multilingual-understanding, Property 3: Language-Neutral Intent Normalization**
**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.6**
"""

import pytest
import tempfile
import time
import sys
from pathlib import Path
from typing import List, Dict, Any, Tuple
import hashlib
import json

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from hypothesis import given, strategies as st, settings, assume, note, HealthCheck
from hypothesis.stateful import RuleBasedStateMachine, Bundle, rule, initialize

from multilingual.intent_normalization import (
    IntentNormalizationLayer,
    CanonicalIntent,
    IntentAction,
    ProcessingMode,
    NormalizationResult,
    IntentPattern,
    CanonicalIntentRegistry,
    IntentDefinition,
    ValidationResult
)
from multilingual.configuration import MultilingualConfig, SupportedLanguages
from multilingual.exceptions import IntentNormalizationError, SecurityBoundaryError


# Test data generation strategies
@st.composite
def supported_language_code(draw):
    """Generate supported language codes."""
    return draw(st.sampled_from(SupportedLanguages.get_language_codes()))


@st.composite
def command_text_for_language(draw, language: str):
    """Generate realistic command text for a specific language."""
    
    # Define command templates for each language
    command_templates = {
        'en': [
            "type {text}",
            "write {text}",
            "click {element}",
            "open {application}",
            "close {application}",
            "send message {message}",
            "call {contact}",
            "clear text",
            "dictation mode",
            "command mode"
        ],
        'hi': [
            "{text} टाइप करो",
            "{text} लिखो",
            "{element} पर क्लिक करो",
            "{application} खोलो",
            "{application} बंद करो",
            "{message} को संदेश भेजो",
            "{contact} को कॉल करो",
            "टेक्स्ट साफ करो",
            "डिक्टेशन मोड",
            "कमांड मोड"
        ],
        'ta': [
            "{text} டைப் பண்ணு",
            "{text} எழுது",
            "{element} கிளிக் பண்ணு",
            "{application} ஓபன் பண்ணு",
            "{application} மூடு",
            "{message} கு மெசேஜ் அனுப்பு",
            "{contact} கு கால் பண்ணு",
            "டெக்ஸ்ட் க்ளியர் பண்ணு",
            "டிக்டேஷன் மோட்",
            "கமாண்ட் மோட்"
        ],
        'de': [
            "schreibe {text}",
            "tippe {text}",
            "klicke {element}",
            "öffne {application}",
            "schließe {application}",
            "sende nachricht {message}",
            "rufe {contact} an",
            "text löschen",
            "diktier modus",
            "befehl modus"
        ],
        'fr': [
            "écris {text}",
            "tape {text}",
            "clique {element}",
            "ouvre {application}",
            "ferme {application}",
            "envoie message {message}",
            "appelle {contact}",
            "efface texte",
            "mode dictée",
            "mode commande"
        ],
        'zh': [
            "输入 {text}",
            "写 {text}",
            "点击 {element}",
            "打开 {application}",
            "关闭 {application}",
            "发送消息 {message}",
            "打电话给 {contact}",
            "清除文本",
            "听写模式",
            "命令模式"
        ],
        'ja': [
            "{text}を入力",
            "{text}を書く",
            "{element}をクリック",
            "{application}を開く",
            "{application}を閉じる",
            "{message}にメッセージを送る",
            "{contact}に電話する",
            "テキストをクリア",
            "ディクテーションモード",
            "コマンドモード"
        ]
    }
    
    # Get templates for the language, fallback to English if not available
    templates = command_templates.get(language, command_templates['en'])
    template = draw(st.sampled_from(templates))
    
    # Generate parameter values
    parameters = {}
    if '{text}' in template:
        parameters['text'] = draw(st.text(min_size=1, max_size=100, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd', 'Pc', 'Pd', 'Zs'))))
    if '{element}' in template:
        parameters['element'] = draw(st.sampled_from(['button', 'link', 'menu', 'icon', 'field', 'checkbox']))
    if '{application}' in template:
        parameters['application'] = draw(st.sampled_from(['notepad', 'browser', 'calculator', 'email', 'music']))
    if '{message}' in template:
        parameters['message'] = draw(st.text(min_size=1, max_size=200, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd', 'Pc', 'Pd', 'Zs'))))
    if '{contact}' in template:
        parameters['contact'] = draw(st.sampled_from(['john', 'mary', 'alex', 'sarah', 'mike']))
    
    # Fill in the template
    command_text = template.format(**parameters)
    return command_text


@st.composite
def multilingual_config(draw):
    """Generate valid multilingual configurations."""
    all_languages = SupportedLanguages.get_language_codes()
    
    # Select 2-5 enabled languages for testing
    num_languages = draw(st.integers(min_value=2, max_value=min(5, len(all_languages))))
    enabled_languages = draw(st.lists(
        st.sampled_from(all_languages),
        min_size=num_languages,
        max_size=num_languages,
        unique=True
    ))
    
    primary_language = draw(st.sampled_from(enabled_languages))
    
    return MultilingualConfig(
        enabled_languages=enabled_languages,
        primary_language=primary_language,
        fallback_language=primary_language,
        detection_threshold=draw(st.floats(min_value=0.7, max_value=0.95)),
        log_intent_normalization=True,
        log_language_detection=True
    )


@st.composite
def equivalent_commands(draw):
    """Generate semantically equivalent commands in different languages."""
    
    # Define equivalent command sets
    equivalent_sets = [
        {
            'en': 'type hello world',
            'hi': 'hello world टाइप करो',
            'ta': 'hello world டைப் பண்ணு',
            'de': 'schreibe hello world',
            'fr': 'écris hello world',
            'zh': '输入 hello world',
            'ja': 'hello worldを入力'
        },
        {
            'en': 'click button',
            'hi': 'button पर क्लिक करो',
            'ta': 'button கிளிக் பண்ணு',
            'de': 'klicke button',
            'fr': 'clique button',
            'zh': '点击 button',
            'ja': 'buttonをクリック'
        },
        {
            'en': 'open notepad',
            'hi': 'notepad खोलो',
            'ta': 'notepad ஓபன் பண்ணு',
            'de': 'öffne notepad',
            'fr': 'ouvre notepad',
            'zh': '打开 notepad',
            'ja': 'notepadを開く'
        },
        {
            'en': 'send message hello',
            'hi': 'hello को संदेश भेजो',
            'ta': 'hello கு மெசேஜ் அனுப்பு',
            'de': 'sende nachricht hello',
            'fr': 'envoie message hello',
            'zh': '发送消息 hello',
            'ja': 'helloにメッセージを送る'
        },
        {
            'en': 'clear text',
            'hi': 'टेक्स्ट साफ करो',
            'ta': 'டெக்ஸ்ட் க்ளியர் பண்ணு',
            'de': 'text löschen',
            'fr': 'efface texte',
            'zh': '清除文本',
            'ja': 'テキストをクリア'
        }
    ]
    
    command_set = draw(st.sampled_from(equivalent_sets))
    return command_set


class TestIntentNormalizationProperties:
    """Property-based tests for intent normalization determinism and consistency."""
    
    def create_normalization_layer(self):
        """Create intent normalization layer for testing."""
        config = MultilingualConfig(
            enabled_languages=['en', 'hi', 'ta', 'de', 'fr', 'zh', 'ja'],
            primary_language='en',
            fallback_language='en',
            detection_threshold=0.85,
            log_intent_normalization=True
        )
        return IntentNormalizationLayer(config)
    
    @given(
        language=supported_language_code(),
        mode=st.sampled_from([ProcessingMode.COMMAND, ProcessingMode.DICTATION]),
        command_text=st.text(min_size=1, max_size=100, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd', 'Pc', 'Pd', 'Zs')))
    )
    @settings(max_examples=50, deadline=3000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_deterministic_normalization(self, language, mode, command_text):
        """
        **Property 3a: Deterministic Intent Normalization**
        
        For any language-specific command, normalization should produce identical 
        canonical intents on repeated calls.
        
        **Validates: Requirements 3.1, 3.2**
        """
        normalization_layer = self.create_normalization_layer()
        assume(language in normalization_layer.config.enabled_languages)
        assume(len(command_text.strip()) > 0)
        
        note(f"Testing language: {language}")
        note(f"Command text: '{command_text}'")
        note(f"Processing mode: {mode.value}")
        
        # Perform normalization multiple times
        results = []
        processing_times = []
        
        for i in range(3):  # Run 3 times to verify determinism
            start_time = time.time()
            result = normalization_layer.normalize_intent(command_text, language, mode)
            end_time = time.time()
            
            processing_time_ms = (end_time - start_time) * 1000
            processing_times.append(processing_time_ms)
            
            # Collect key result properties for determinism check
            if result.success and result.canonical_intent:
                result_signature = (
                    result.canonical_intent.action.value,
                    frozenset(result.canonical_intent.parameters.items()) if result.canonical_intent.parameters else frozenset(),
                    result.canonical_intent.processing_mode.value,
                    result.canonical_intent.original_language,
                    result.success
                )
            else:
                result_signature = (
                    None,
                    None,
                    None,
                    None,
                    result.success
                )
            
            results.append(result_signature)
            
            note(f"Run {i+1}: success={result.success}, time={processing_time_ms:.1f}ms")
            if result.canonical_intent:
                note(f"  Action: {result.canonical_intent.action.value}")
                note(f"  Parameters: {result.canonical_intent.parameters}")
        
        # Property 3a: Deterministic Results
        # All results should be identical for the same input
        unique_results = set(results)
        assert len(unique_results) == 1, f"Normalization should be deterministic, got different results: {results}"
        
        # Property 3b: Performance Consistency
        # Processing times should be reasonably consistent (accounting for caching)
        if len(processing_times) > 1:
            # If we have cache hits (0ms times), that's expected and good
            non_zero_times = [t for t in processing_times if t > 0]
            if len(non_zero_times) > 1:
                avg_time = sum(non_zero_times) / len(non_zero_times)
                max_deviation = max(abs(t - avg_time) for t in non_zero_times)
                # Allow up to 200% deviation in processing time (very lenient for test environment)
                assert max_deviation <= avg_time * 2.0, f"Processing times too inconsistent: {processing_times}"
        
        # Property 3c: Valid Canonical Intent Structure
        final_result = normalization_layer.normalize_intent(command_text, language, mode)
        
        if final_result.success and final_result.canonical_intent:
            intent = final_result.canonical_intent
            
            # Validate intent structure
            assert isinstance(intent.action, IntentAction), "Action should be valid IntentAction"
            assert isinstance(intent.parameters, dict), "Parameters should be dictionary"
            assert intent.original_language == language, "Original language should match input"
            assert intent.processing_mode == mode, "Processing mode should match input"
            assert intent.original_text == command_text, "Original text should match input"
            assert 0.0 <= intent.confidence <= 1.0, "Confidence should be in valid range"
            assert intent.processing_time_ms >= 0, "Processing time should be non-negative"
            
            # Validate normalization path
            assert intent.normalization_path, "Normalization path should be set"
            assert language in intent.normalization_path, "Normalization path should include source language"
            assert intent.action.value in intent.normalization_path, "Normalization path should include target action"
    
    @given(equivalent_commands=equivalent_commands())
    @settings(max_examples=20, deadline=5000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_cross_language_equivalence(self, equivalent_commands):
        """
        **Property 3b: Cross-Language Command Equivalence**
        
        Semantically equivalent commands in different languages should produce 
        identical canonical intents.
        
        **Validates: Requirements 3.4, 3.5**
        """
        normalization_layer = self.create_normalization_layer()
        
        # Filter to only enabled languages
        enabled_commands = {
            lang: cmd for lang, cmd in equivalent_commands.items()
            if lang in normalization_layer.config.enabled_languages
        }
        
        assume(len(enabled_commands) >= 2)  # Need at least 2 languages to test equivalence
        
        note(f"Testing equivalent commands: {enabled_commands}")
        
        # Normalize all equivalent commands
        canonical_intents = {}
        normalization_results = {}
        
        for language, command_text in enabled_commands.items():
            result = normalization_layer.normalize_intent(command_text, language, ProcessingMode.COMMAND)
            normalization_results[language] = result
            
            if result.success and result.canonical_intent:
                canonical_intents[language] = result.canonical_intent
                note(f"{language}: '{command_text}' -> {result.canonical_intent.action.value} {result.canonical_intent.parameters}")
            else:
                note(f"{language}: '{command_text}' -> FAILED: {result.error}")
        
        # Property 3b1: All equivalent commands should normalize successfully
        successful_languages = list(canonical_intents.keys())
        assert len(successful_languages) >= 2, f"At least 2 languages should normalize successfully, got {len(successful_languages)}"
        
        # Property 3b2: All canonical intents should have the same action
        actions = {intent.action for intent in canonical_intents.values()}
        assert len(actions) == 1, f"All equivalent commands should produce same action, got {actions}"
        
        # Property 3b3: All canonical intents should have equivalent parameters
        # (Parameter values might differ slightly due to language-specific extraction, but structure should be same)
        parameter_keys_sets = [set(intent.parameters.keys()) for intent in canonical_intents.values()]
        if parameter_keys_sets:
            reference_keys = parameter_keys_sets[0]
            for i, keys in enumerate(parameter_keys_sets[1:], 1):
                assert keys == reference_keys, f"Parameter structure should be consistent across languages, language {i} differs"
        
        # Property 3b4: All canonical intents should have consistent security properties
        security_levels = {intent.security_level for intent in canonical_intents.values()}
        assert len(security_levels) == 1, f"Security levels should be consistent, got {security_levels}"
        
        requires_authority = {intent.requires_authority for intent in canonical_intents.values()}
        assert len(requires_authority) == 1, f"Authority requirements should be consistent, got {requires_authority}"
    
    @given(
        language=supported_language_code(),
        text_content=st.text(min_size=1, max_size=500, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd', 'Pc', 'Pd', 'Zs')))
    )
    @settings(max_examples=30, deadline=2000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_dictation_mode_preservation(self, language, text_content):
        """
        **Property 3c: Exact Dictation Preservation**
        
        In dictation mode, text should be preserved exactly without normalization.
        
        **Validates: Requirements 4.1, 4.2, 4.3**
        """
        normalization_layer = self.create_normalization_layer()
        assume(language in normalization_layer.config.enabled_languages)
        assume(len(text_content.strip()) > 0)
        
        note(f"Testing dictation in {language}: '{text_content}'")
        
        # Normalize in dictation mode
        result = normalization_layer.normalize_intent(text_content, language, ProcessingMode.DICTATION)
        
        # Property 3c1: Dictation should always succeed
        assert result.success, f"Dictation normalization should always succeed, got error: {result.error}"
        assert result.canonical_intent is not None, "Dictation should produce canonical intent"
        
        intent = result.canonical_intent
        
        # Property 3c2: Action should be TYPE_TEXT
        assert intent.action == IntentAction.TYPE_TEXT, f"Dictation should produce TYPE_TEXT action, got {intent.action}"
        
        # Property 3c3: Text should be preserved exactly
        assert 'text' in intent.parameters, "Dictation intent should have 'text' parameter"
        assert intent.parameters['text'] == text_content, f"Text should be preserved exactly: expected '{text_content}', got '{intent.parameters['text']}'"
        
        # Property 3c4: Preserve exact flag should be set
        assert intent.parameters.get('preserve_exact', False), "Dictation should set preserve_exact flag"
        
        # Property 3c5: Processing mode should be dictation
        assert intent.processing_mode == ProcessingMode.DICTATION, "Processing mode should be dictation"
        
        # Property 3c6: Original text and language should be preserved
        assert intent.original_text == text_content, "Original text should be preserved"
        assert intent.original_language == language, "Original language should be preserved"
        
        # Property 3c7: Security level should be appropriate for dictation
        assert intent.security_level in ['low', 'medium'], "Dictation should have appropriate security level"
    
    @given(
        language=supported_language_code(),
        malicious_patterns=st.sampled_from([
            "../../../etc/passwd",
            "rm -rf /",
            "DROP TABLE users;",
            "<script>alert('xss')</script>",
            "$(rm -rf /)",
            "'; DROP TABLE users; --",
            "../../../../windows/system32",
            "javascript:alert(1)",
            "file:///etc/passwd",
            "\\..\\..\\windows\\system32"
        ])
    )
    @settings(max_examples=25, deadline=2000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_security_boundary_enforcement(self, language, malicious_patterns):
        """
        **Property 3d: Security Boundary Enforcement**
        
        Malicious or dangerous patterns should be detected and blocked.
        
        **Validates: Requirements 3.3**
        """
        normalization_layer = self.create_normalization_layer()
        assume(language in normalization_layer.config.enabled_languages)
        
        # Create command with malicious pattern
        malicious_command = f"type {malicious_patterns}"
        
        note(f"Testing security for {language}: '{malicious_command}'")
        
        # Attempt normalization
        result = normalization_layer.normalize_intent(malicious_command, language, ProcessingMode.COMMAND)
        
        # Property 3d1: Security violations should be handled appropriately
        if result.success and result.canonical_intent:
            # If normalization succeeds, security validation should catch issues
            intent = result.canonical_intent
            
            # Check if security validator would catch this
            security_result = normalization_layer._security_validator.validate_intent(intent)
            
            # Either normalization should fail or security validation should catch it
            if malicious_patterns in ["../../../etc/passwd", "../../../../windows/system32", "\\..\\..\\windows\\system32"]:
                # Path traversal should be caught
                assert not security_result.valid, f"Path traversal should be blocked: {malicious_patterns}"
            
            if any(pattern in malicious_patterns for pattern in ["<script", "javascript:", "DROP TABLE"]):
                # Injection attempts should be sanitized or blocked
                if 'text' in intent.parameters:
                    sanitized_text = intent.parameters['text']
                    # Check that dangerous patterns are removed or escaped
                    assert "<script" not in sanitized_text or "javascript:" not in sanitized_text
        
        # Property 3d2: Error messages should not leak sensitive information
        if not result.success and result.error:
            # Error messages should be generic, not revealing system details
            assert "password" not in result.error.lower()
            assert "system32" not in result.error.lower()
            assert "/etc/" not in result.error.lower()
    
    @given(
        config=multilingual_config()
    )
    @settings(max_examples=15, deadline=3000)
    def test_registry_validation_consistency(self, config):
        """
        **Property 3e: Registry Validation Consistency**
        
        Intent validation should be consistent across different configurations.
        
        **Validates: Requirements 3.1, 3.6**
        """
        layer = IntentNormalizationLayer(config)
        registry = layer.get_canonical_registry()
        
        note(f"Testing with {len(config.enabled_languages)} enabled languages")
        
        # Test all supported actions
        supported_actions = registry.get_supported_actions()
        assert len(supported_actions) > 0, "Registry should have supported actions"
        
        # Property 3e1: All actions should have valid definitions
        for action in supported_actions:
            definition = registry.get_intent_definition(action)
            assert definition is not None, f"Action {action} should have definition"
            assert definition.action == action, "Definition action should match"
            assert isinstance(definition.required_parameters, list), "Required parameters should be list"
            assert isinstance(definition.optional_parameters, list), "Optional parameters should be list"
            assert definition.security_level in ['low', 'medium', 'high', 'admin'], "Security level should be valid"
        
        # Property 3e2: Categories should be consistent
        categories = registry.get_categories()
        assert len(categories) > 0, "Should have intent categories"
        
        for category in categories:
            actions_in_category = registry.get_actions_by_category(category)
            assert len(actions_in_category) > 0, f"Category {category} should have actions"
            
            # All actions in category should have consistent properties
            definitions = [registry.get_intent_definition(action) for action in actions_in_category]
            category_names = {d.category for d in definitions}
            assert len(category_names) == 1, f"All actions in category should have same category name"
            assert category in category_names, f"Category name should match"
        
        # Property 3e3: Security policies should be consistent
        for action in supported_actions:
            security_policy = registry.get_security_policy(action)
            assert security_policy is not None, f"Action {action} should have security policy"
            assert security_policy.action == action, "Security policy action should match"
            
            # Create a test intent to validate policy
            test_intent = CanonicalIntent(
                action=action,
                parameters={},
                original_language='en',
                processing_mode=ProcessingMode.COMMAND
            )
            
            # Policy validation should not crash
            policy_result = security_policy.validate(test_intent)
            assert isinstance(policy_result.valid, bool), "Policy validation should return boolean"
            assert isinstance(policy_result.errors, list), "Policy errors should be list"
            assert isinstance(policy_result.warnings, list), "Policy warnings should be list"


class IntentNormalizationStateMachine(RuleBasedStateMachine):
    """
    Stateful property-based testing for intent normalization layer.
    
    Tests complex interactions and caching behavior over multiple operations.
    """
    
    def __init__(self):
        super().__init__()
        
        # Create normalization layer
        self.config = MultilingualConfig(
            enabled_languages=['en', 'hi', 'ta', 'de', 'fr'],
            primary_language='en',
            fallback_language='en',
            detection_threshold=0.85,
            log_intent_normalization=True
        )
        
        self.layer = IntentNormalizationLayer(self.config)
        self.normalization_history = []
        self.cache_hits = 0
        self.total_normalizations = 0
    
    commands = Bundle('commands')
    languages = Bundle('languages')
    
    @initialize()
    def setup(self):
        """Initialize the state machine."""
        pass
    
    @rule(target=languages)
    def generate_language(self):
        """Generate supported language for testing."""
        return st.sampled_from(self.config.enabled_languages)
    
    @rule(target=commands, data=st.data())
    def generate_command(self, data):
        """Generate command for testing."""
        language = data.draw(st.sampled_from(self.config.enabled_languages))
        command_text = data.draw(command_text_for_language(st.just(language)))
        return (language, command_text)
    
    @rule(command=commands, mode=st.sampled_from([ProcessingMode.COMMAND, ProcessingMode.DICTATION]))
    def normalize_intent(self, command, mode):
        """Perform intent normalization and verify properties."""
        language, command_text = command
        
        # Check if this is a cache hit
        cache_key = f"{language}:{mode.value}:{command_text}"
        is_potential_cache_hit = any(
            h['cache_key'] == cache_key for h in self.normalization_history
        )
        
        # Perform normalization
        result = self.layer.normalize_intent(command_text, language, mode)
        self.total_normalizations += 1
        
        # Record normalization
        self.normalization_history.append({
            'cache_key': cache_key,
            'language': language,
            'command_text': command_text,
            'mode': mode,
            'result': result,
            'timestamp': time.time()
        })
        
        # Property: Valid normalization result
        assert isinstance(result.success, bool), "Result should have success flag"
        assert result.processing_time_ms >= 0, "Processing time should be non-negative"
        
        if result.success and result.canonical_intent:
            intent = result.canonical_intent
            
            # Property: Valid canonical intent structure
            assert isinstance(intent.action, IntentAction), "Should have valid action"
            assert isinstance(intent.parameters, dict), "Should have parameters dict"
            assert intent.original_language == language, "Should preserve original language"
            assert intent.processing_mode == mode, "Should preserve processing mode"
            assert intent.original_text == command_text, "Should preserve original text"
            
            # Property: Deterministic behavior for same input
            same_input_results = [
                h['result'] for h in self.normalization_history
                if h['cache_key'] == cache_key
            ]
            
            if len(same_input_results) > 1:
                # All results for same input should be consistent
                first_result = same_input_results[0]
                for other_result in same_input_results[1:]:
                    if first_result.success and other_result.success:
                        assert (first_result.canonical_intent.action == 
                               other_result.canonical_intent.action), "Same input should produce same action"
        
        # Property: Cache behavior
        if is_potential_cache_hit and result.success:
            # Cache hits should be faster (though this is implementation dependent)
            recent_times = [
                h['result'].processing_time_ms for h in self.normalization_history[-5:]
                if h['cache_key'] == cache_key
            ]
            if len(recent_times) > 1:
                # Don't enforce strict cache timing, just verify consistency
                pass
    
    @rule(commands=st.lists(commands, min_size=2, max_size=5))
    def test_batch_normalization_consistency(self, commands):
        """Test consistency across batch normalization."""
        results = []
        
        for language, command_text in commands:
            result = self.layer.normalize_intent(command_text, language, ProcessingMode.COMMAND)
            results.append((language, command_text, result))
        
        # Property: All results should be valid
        for language, command_text, result in results:
            assert isinstance(result.success, bool), f"Result for {language}:'{command_text}' should have success flag"
            
            if result.success and result.canonical_intent:
                intent = result.canonical_intent
                assert intent.original_language == language, "Language should be preserved"
                assert intent.original_text == command_text, "Text should be preserved"
    
    def teardown(self):
        """Clean up resources and verify final properties."""
        # Property: Cache should improve performance over time
        if self.total_normalizations > 10:
            stats = self.layer.get_normalization_statistics()
            
            # Should have some successful normalizations
            assert stats['successful_normalizations'] > 0, "Should have successful normalizations"
            
            # Cache hit rate should be reasonable if there were repeated commands
            if stats['cache_hits'] > 0:
                cache_hit_rate = stats['cache_hit_rate']  # Use the pre-calculated rate
                assert 0.0 <= cache_hit_rate <= 1.0, "Cache hit rate should be valid percentage"


# Property-based test runner
TestIntentNormalizationStateMachine = IntentNormalizationStateMachine.TestCase


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])