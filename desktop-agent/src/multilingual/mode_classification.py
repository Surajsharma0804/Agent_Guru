"""
Multilingual Mode Classification

Production-grade mode classification system that determines whether user input
should be processed as commands or dictation across all supported languages
with consistent behavior and explicit mode switching capabilities.
"""

import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Pattern, Set, Tuple
from threading import RLock

from .configuration import MultilingualConfig, SupportedLanguages
from .exceptions import MultilingualError, UnsupportedLanguageError


class ProcessingMode(Enum):
    """Processing modes for multilingual input."""
    
    COMMAND = "command"      # Interpret as system commands
    DICTATION = "dictation"  # Type exactly as spoken
    MIXED = "mixed"          # Contains both commands and dictation


class ModeTransition(Enum):
    """Mode transition types."""
    
    EXPLICIT_COMMAND = "explicit_command"      # User explicitly requested mode
    AUTOMATIC_DETECTION = "automatic_detection"  # System detected mode
    SESSION_DEFAULT = "session_default"       # Using session default
    FALLBACK = "fallback"                     # Fallback to default mode


@dataclass
class ModeSwitchCommand:
    """Represents a mode switching command."""
    
    new_mode: ProcessingMode
    command_text: str
    language: str
    confidence: float = 1.0
    pattern_matched: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging."""
        return {
            'new_mode': self.new_mode.value,
            'command_text': self.command_text,
            'language': self.language,
            'confidence': self.confidence,
            'pattern_matched': self.pattern_matched
        }


@dataclass
class ModeClassificationResult:
    """Result of mode classification operation."""
    
    # Classification results
    mode: ProcessingMode
    confidence: float
    transition_type: ModeTransition
    
    # Mode switching information
    mode_switched: bool = False
    switch_command: Optional[ModeSwitchCommand] = None
    previous_mode: Optional[ProcessingMode] = None
    
    # Processing metadata
    processing_time_ms: int = 0
    patterns_evaluated: int = 0
    language: Optional[str] = None
    
    # Context information
    session_context_used: bool = False
    fallback_used: bool = False
    
    # Error information
    error: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    
    @property
    def success(self) -> bool:
        """Check if classification was successful."""
        return self.error is None
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging."""
        return {
            'mode': self.mode.value,
            'confidence': self.confidence,
            'transition_type': self.transition_type.value,
            'mode_switched': self.mode_switched,
            'switch_command': self.switch_command.to_dict() if self.switch_command else None,
            'previous_mode': self.previous_mode.value if self.previous_mode else None,
            'processing_time_ms': self.processing_time_ms,
            'patterns_evaluated': self.patterns_evaluated,
            'language': self.language,
            'session_context_used': self.session_context_used,
            'fallback_used': self.fallback_used,
            'success': self.success,
            'error': self.error,
            'warnings': self.warnings
        }


@dataclass
class ModePattern:
    """Pattern for detecting mode switching commands."""
    
    pattern: str  # Regex pattern
    target_mode: ProcessingMode
    confidence: float = 1.0
    priority: int = 0  # Higher priority patterns are checked first
    
    # Compiled pattern (cached)
    _compiled_pattern: Optional[Pattern] = field(default=None, init=False, repr=False)
    
    def __post_init__(self):
        """Compile regex pattern after initialization."""
        try:
            self._compiled_pattern = re.compile(
                self.pattern, 
                re.IGNORECASE | re.UNICODE | re.MULTILINE
            )
        except re.error as e:
            raise MultilingualError(
                f"Invalid mode pattern regex: {self.pattern}",
                context={'regex_error': str(e)}
            )
            
    def matches(self, text: str) -> bool:
        """Check if text matches this pattern."""
        if not self._compiled_pattern:
            return False
        return bool(self._compiled_pattern.search(text.strip()))


class ModeHistory:
    """Tracks mode switching history for session context."""
    
    def __init__(self, max_history: int = 100):
        self.max_history = max_history
        self._history: List[Tuple[datetime, ProcessingMode, str]] = []
        self._lock = RLock()
        self.logger = logging.getLogger(__name__)
        
    def record_mode_change(
        self, 
        mode: ProcessingMode, 
        reason: str,
        timestamp: Optional[datetime] = None
    ):
        """Record a mode change in history."""
        if timestamp is None:
            timestamp = datetime.utcnow()
            
        with self._lock:
            self._history.append((timestamp, mode, reason))
            
            # Maintain history size limit
            if len(self._history) > self.max_history:
                self._history = self._history[-self.max_history:]
                
        self.logger.debug(f"Recorded mode change: {mode.value} ({reason})")
        
    def get_recent_mode(self, within_minutes: int = 5) -> Optional[ProcessingMode]:
        """Get the most recent mode within specified time window."""
        cutoff_time = datetime.utcnow() - timedelta(minutes=within_minutes)
        
        with self._lock:
            for timestamp, mode, reason in reversed(self._history):
                if timestamp >= cutoff_time:
                    return mode
                    
        return None
        
    def get_mode_frequency(self, within_minutes: int = 30) -> Dict[ProcessingMode, int]:
        """Get frequency of modes within time window."""
        cutoff_time = datetime.utcnow() - timedelta(minutes=within_minutes)
        frequency = {mode: 0 for mode in ProcessingMode}
        
        with self._lock:
            for timestamp, mode, reason in self._history:
                if timestamp >= cutoff_time:
                    frequency[mode] += 1
                    
        return frequency
        
    def clear_history(self):
        """Clear mode history."""
        with self._lock:
            self._history.clear()
        self.logger.info("Cleared mode history")
        
    def get_history_summary(self) -> Dict[str, Any]:
        """Get summary of mode history."""
        with self._lock:
            total_changes = len(self._history)
            
            if total_changes == 0:
                return {
                    'total_changes': 0,
                    'current_mode': None,
                    'recent_mode': None
                }
                
            current_mode = self._history[-1][1]
            recent_frequency = self.get_mode_frequency(30)
            
            return {
                'total_changes': total_changes,
                'current_mode': current_mode.value,
                'recent_mode': self.get_recent_mode(5),
                'recent_frequency': {mode.value: count for mode, count in recent_frequency.items()}
            }


class ModePatternRegistry:
    """Registry of mode switching patterns for all supported languages."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._patterns: Dict[str, List[ModePattern]] = {}
        self._lock = RLock()
        
        # Initialize with default patterns
        self._initialize_default_patterns()
        
    def _initialize_default_patterns(self):
        """Initialize default mode switching patterns for supported languages."""
        
        # English patterns
        self.register_patterns("en", [
            # Command mode patterns
            ModePattern(
                pattern=r"^(command\s+mode|switch\s+to\s+commands?|enable\s+commands?)$",
                target_mode=ProcessingMode.COMMAND,
                priority=10
            ),
            ModePattern(
                pattern=r"^(start\s+commanding|begin\s+commands?)$",
                target_mode=ProcessingMode.COMMAND,
                priority=8
            ),
            
            # Dictation mode patterns
            ModePattern(
                pattern=r"^(dictation\s+mode|start\s+dictating|type\s+mode)$",
                target_mode=ProcessingMode.DICTATION,
                priority=10
            ),
            ModePattern(
                pattern=r"^(begin\s+typing|start\s+writing|writing\s+mode)$",
                target_mode=ProcessingMode.DICTATION,
                priority=8
            ),
            
            # Implicit command indicators (lower priority)
            ModePattern(
                pattern=r"^(open|close|click|scroll|switch|launch|run|execute)",
                target_mode=ProcessingMode.COMMAND,
                priority=3
            ),
            
            # Implicit dictation indicators (lower priority)
            ModePattern(
                pattern=r"^(dear|hello|hi|the|a|an|this|that|i|you|we|they)",
                target_mode=ProcessingMode.DICTATION,
                priority=2
            )
        ])
        
        # Hindi patterns
        self.register_patterns("hi", [
            # Command mode patterns
            ModePattern(
                pattern=r"^(कमांड\s+मोड|आदेश\s+मोड|कमांड\s+चालू\s+करो)$",
                target_mode=ProcessingMode.COMMAND,
                priority=10
            ),
            ModePattern(
                pattern=r"^(कमांड\s+शुरू\s+करो|आदेश\s+देना\s+शुरू\s+करो)$",
                target_mode=ProcessingMode.COMMAND,
                priority=8
            ),
            
            # Dictation mode patterns
            ModePattern(
                pattern=r"^(डिक्टेशन\s+मोड|लिखना\s+शुरू\s+करो|टाइप\s+मोड)$",
                target_mode=ProcessingMode.DICTATION,
                priority=10
            ),
            ModePattern(
                pattern=r"^(लेखन\s+मोड|टाइपिंग\s+शुरू\s+करो)$",
                target_mode=ProcessingMode.DICTATION,
                priority=8
            ),
            
            # Implicit command indicators
            ModePattern(
                pattern=r"^(खोलो|बंद\s+करो|क्लिक\s+करो|चलाओ|शुरू\s+करो)",
                target_mode=ProcessingMode.COMMAND,
                priority=3
            ),
            
            # Implicit dictation indicators
            ModePattern(
                pattern=r"^(प्रिय|नमस्ते|हैलो|यह|वह|मैं|आप|हम|वे)",
                target_mode=ProcessingMode.DICTATION,
                priority=2
            )
        ])
        
        # Tamil patterns
        self.register_patterns("ta", [
            # Command mode patterns
            ModePattern(
                pattern=r"^(கமாண்ட்\s+மோட்|கட்டளை\s+முறை|கமாண்ட்\s+ஆன்\s+பண்ணு)$",
                target_mode=ProcessingMode.COMMAND,
                priority=10
            ),
            
            # Dictation mode patterns
            ModePattern(
                pattern=r"^(டிக்டேஷன்\s+மோட்|எழுத\s+ஆரம்பி|டைப்\s+மோட்)$",
                target_mode=ProcessingMode.DICTATION,
                priority=10
            ),
            
            # Implicit command indicators
            ModePattern(
                pattern=r"^(ஓபன்\s+பண்ணு|கிளோஸ்\s+பண்ணு|கிளிக்\s+பண்ணு|ரன்\s+பண்ணு)",
                target_mode=ProcessingMode.COMMAND,
                priority=3
            ),
            
            # Implicit dictation indicators
            ModePattern(
                pattern=r"^(அன்புள்ள|வணக்கம்|ஹலோ|இது|அது|நான்|நீங்கள்|நாங்கள்)",
                target_mode=ProcessingMode.DICTATION,
                priority=2
            )
        ])
        
        # German patterns
        self.register_patterns("de", [
            # Command mode patterns
            ModePattern(
                pattern=r"^(befehl\s+modus|kommando\s+modus|befehle\s+aktivieren)$",
                target_mode=ProcessingMode.COMMAND,
                priority=10
            ),
            
            # Dictation mode patterns
            ModePattern(
                pattern=r"^(diktat\s+modus|schreib\s+modus|tippen\s+beginnen)$",
                target_mode=ProcessingMode.DICTATION,
                priority=10
            ),
            
            # Implicit command indicators
            ModePattern(
                pattern=r"^(öffne|schließe|klicke|starte|führe\s+aus)",
                target_mode=ProcessingMode.COMMAND,
                priority=3
            ),
            
            # Implicit dictation indicators
            ModePattern(
                pattern=r"^(liebe|hallo|guten|das|die|der|ich|du|wir|sie)",
                target_mode=ProcessingMode.DICTATION,
                priority=2
            )
        ])
        
        # French patterns
        self.register_patterns("fr", [
            # Command mode patterns
            ModePattern(
                pattern=r"^(mode\s+commande|activer\s+commandes|commencer\s+commandes)$",
                target_mode=ProcessingMode.COMMAND,
                priority=10
            ),
            
            # Dictation mode patterns
            ModePattern(
                pattern=r"^(mode\s+dictée|commencer\s+dictée|mode\s+écriture)$",
                target_mode=ProcessingMode.DICTATION,
                priority=10
            ),
            
            # Implicit command indicators
            ModePattern(
                pattern=r"^(ouvre|ferme|clique|lance|exécute)",
                target_mode=ProcessingMode.COMMAND,
                priority=3
            ),
            
            # Implicit dictation indicators
            ModePattern(
                pattern=r"^(cher|bonjour|salut|le|la|les|je|tu|nous|vous)",
                target_mode=ProcessingMode.DICTATION,
                priority=2
            )
        ])
        
        # Chinese (Mandarin) patterns
        self.register_patterns("zh", [
            # Command mode patterns
            ModePattern(
                pattern=r"^(命令模式|切换到命令|启用命令)$",
                target_mode=ProcessingMode.COMMAND,
                priority=10
            ),
            ModePattern(
                pattern=r"^(开始命令|命令开始)$",
                target_mode=ProcessingMode.COMMAND,
                priority=8
            ),
            
            # Dictation mode patterns
            ModePattern(
                pattern=r"^(听写模式|开始听写|输入模式)$",
                target_mode=ProcessingMode.DICTATION,
                priority=10
            ),
            ModePattern(
                pattern=r"^(开始输入|写字模式)$",
                target_mode=ProcessingMode.DICTATION,
                priority=8
            ),
            
            # Implicit command indicators
            ModePattern(
                pattern=r"^(打开|关闭|点击|运行|执行)",
                target_mode=ProcessingMode.COMMAND,
                priority=3
            ),
            
            # Implicit dictation indicators
            ModePattern(
                pattern=r"^(亲爱的|你好|这个|那个|我|你|我们|他们)",
                target_mode=ProcessingMode.DICTATION,
                priority=2
            )
        ])
        
        # Japanese patterns
        self.register_patterns("ja", [
            # Command mode patterns
            ModePattern(
                pattern=r"^(コマンドモード|命令モード|コマンドを有効にする)$",
                target_mode=ProcessingMode.COMMAND,
                priority=10
            ),
            ModePattern(
                pattern=r"^(コマンド開始|命令開始)$",
                target_mode=ProcessingMode.COMMAND,
                priority=8
            ),
            
            # Dictation mode patterns
            ModePattern(
                pattern=r"^(ディクテーションモード|入力モード|タイプモード)$",
                target_mode=ProcessingMode.DICTATION,
                priority=10
            ),
            ModePattern(
                pattern=r"^(入力開始|書き始める)$",
                target_mode=ProcessingMode.DICTATION,
                priority=8
            ),
            
            # Implicit command indicators
            ModePattern(
                pattern=r"^(開く|閉じる|クリック|実行|起動)",
                target_mode=ProcessingMode.COMMAND,
                priority=3
            ),
            
            # Implicit dictation indicators
            ModePattern(
                pattern=r"^(親愛なる|こんにちは|これ|それ|私|あなた|私たち|彼ら)",
                target_mode=ProcessingMode.DICTATION,
                priority=2
            )
        ])
        
        # Telugu patterns
        self.register_patterns("te", [
            # Command mode patterns
            ModePattern(
                pattern=r"^(కమాండ్\s+మోడ్|ఆదేశ\s+విధానం|కమాండ్\s+ఆన్\s+చేయండి)$",
                target_mode=ProcessingMode.COMMAND,
                priority=10
            ),
            ModePattern(
                pattern=r"^(కమాండ్\s+ప్రారంభించండి|ఆదేశాలు\s+ప్రారంభించండి)$",
                target_mode=ProcessingMode.COMMAND,
                priority=8
            ),
            
            # Dictation mode patterns
            ModePattern(
                pattern=r"^(డిక్టేషన్\s+మోడ్|రాయడం\s+ప్రారంభించండి|టైప్\s+మోడ్)$",
                target_mode=ProcessingMode.DICTATION,
                priority=10
            ),
            ModePattern(
                pattern=r"^(వ్రాయడం\s+మోడ్|టైపింగ్\s+ప్రారంభించండి)$",
                target_mode=ProcessingMode.DICTATION,
                priority=8
            ),
            
            # Implicit command indicators
            ModePattern(
                pattern=r"^(తెరవండి|మూసివేయండి|క్లిక్\s+చేయండి|రన్\s+చేయండి|ప్రారంభించండి)",
                target_mode=ProcessingMode.COMMAND,
                priority=3
            ),
            
            # Implicit dictation indicators
            ModePattern(
                pattern=r"^(ప్రియమైన|నమస్కారం|హలో|ఇది|అది|నేను|మీరు|మేము|వారు)",
                target_mode=ProcessingMode.DICTATION,
                priority=2
            )
        ])
        
        # Bengali patterns
        self.register_patterns("bn", [
            # Command mode patterns
            ModePattern(
                pattern=r"^(কমান্ড\s+মোড|আদেশ\s+মোড|কমান্ড\s+চালু\s+করুন)$",
                target_mode=ProcessingMode.COMMAND,
                priority=10
            ),
            ModePattern(
                pattern=r"^(কমান্ড\s+শুরু\s+করুন|আদেশ\s+শুরু\s+করুন)$",
                target_mode=ProcessingMode.COMMAND,
                priority=8
            ),
            
            # Dictation mode patterns
            ModePattern(
                pattern=r"^(ডিক্টেশন\s+মোড|লেখা\s+শুরু\s+করুন|টাইপ\s+মোড)$",
                target_mode=ProcessingMode.DICTATION,
                priority=10
            ),
            ModePattern(
                pattern=r"^(লেখার\s+মোড|টাইপিং\s+শুরু\s+করুন)$",
                target_mode=ProcessingMode.DICTATION,
                priority=8
            ),
            
            # Implicit command indicators
            ModePattern(
                pattern=r"^(খুলুন|বন্ধ\s+করুন|ক্লিক\s+করুন|চালান|শুরু\s+করুন)",
                target_mode=ProcessingMode.COMMAND,
                priority=3
            ),
            
            # Implicit dictation indicators
            ModePattern(
                pattern=r"^(প্রিয়|নমস্কার|হ্যালো|এটি|সেটি|আমি|আপনি|আমরা|তারা)",
                target_mode=ProcessingMode.DICTATION,
                priority=2
            )
        ])
        
        # Marathi patterns
        self.register_patterns("mr", [
            # Command mode patterns
            ModePattern(
                pattern=r"^(कमांड\s+मोड|आदेश\s+मोड|कमांड\s+चालू\s+करा)$",
                target_mode=ProcessingMode.COMMAND,
                priority=10
            ),
            ModePattern(
                pattern=r"^(कमांड\s+सुरू\s+करा|आदेश\s+सुरू\s+करा)$",
                target_mode=ProcessingMode.COMMAND,
                priority=8
            ),
            
            # Dictation mode patterns
            ModePattern(
                pattern=r"^(डिक्टेशन\s+मोड|लिहिणे\s+सुरू\s+करा|टाइप\s+मोड)$",
                target_mode=ProcessingMode.DICTATION,
                priority=10
            ),
            ModePattern(
                pattern=r"^(लेखन\s+मोड|टाइपिंग\s+सुरू\s+करा)$",
                target_mode=ProcessingMode.DICTATION,
                priority=8
            ),
            
            # Implicit command indicators
            ModePattern(
                pattern=r"^(उघडा|बंद\s+करा|क्लिक\s+करा|चालवा|सुरू\s+करा)",
                target_mode=ProcessingMode.COMMAND,
                priority=3
            ),
            
            # Implicit dictation indicators
            ModePattern(
                pattern=r"^(प्रिय|नमस्कार|हॅलो|हे|ते|मी|तुम्ही|आम्ही|ते)",
                target_mode=ProcessingMode.DICTATION,
                priority=2
            )
        ])
        
        # Gujarati patterns
        self.register_patterns("gu", [
            # Command mode patterns
            ModePattern(
                pattern=r"^(કમાન્ડ\s+મોડ|આદેશ\s+મોડ|કમાન્ડ\s+ચાલુ\s+કરો)$",
                target_mode=ProcessingMode.COMMAND,
                priority=10
            ),
            ModePattern(
                pattern=r"^(કમાન્ડ\s+શરૂ\s+કરો|આદેશ\s+શરૂ\s+કરો)$",
                target_mode=ProcessingMode.COMMAND,
                priority=8
            ),
            
            # Dictation mode patterns
            ModePattern(
                pattern=r"^(ડિક્ટેશન\s+મોડ|લખવાનું\s+શરૂ\s+કરો|ટાઇપ\s+મોડ)$",
                target_mode=ProcessingMode.DICTATION,
                priority=10
            ),
            ModePattern(
                pattern=r"^(લેખન\s+મોડ|ટાઇપિંગ\s+શરૂ\s+કરો)$",
                target_mode=ProcessingMode.DICTATION,
                priority=8
            ),
            
            # Implicit command indicators
            ModePattern(
                pattern=r"^(ખોલો|બંધ\s+કરો|ક્લિક\s+કરો|ચલાવો|શરૂ\s+કરો)",
                target_mode=ProcessingMode.COMMAND,
                priority=3
            ),
            
            # Implicit dictation indicators
            ModePattern(
                pattern=r"^(પ્રિય|નમસ્કાર|હેલો|આ|તે|હું|તમે|અમે|તેઓ)",
                target_mode=ProcessingMode.DICTATION,
                priority=2
            )
        ])
        
        # Kannada patterns
        self.register_patterns("kn", [
            # Command mode patterns
            ModePattern(
                pattern=r"^(ಕಮಾಂಡ್\s+ಮೋಡ್|ಆದೇಶ\s+ವಿಧಾನ|ಕಮಾಂಡ್\s+ಆನ್\s+ಮಾಡಿ)$",
                target_mode=ProcessingMode.COMMAND,
                priority=10
            ),
            ModePattern(
                pattern=r"^(ಕಮಾಂಡ್\s+ಪ್ರಾರಂಭಿಸಿ|ಆದೇಶಗಳು\s+ಪ್ರಾರಂಭಿಸಿ)$",
                target_mode=ProcessingMode.COMMAND,
                priority=8
            ),
            
            # Dictation mode patterns
            ModePattern(
                pattern=r"^(ಡಿಕ್ಟೇಶನ್\s+ಮೋಡ್|ಬರೆಯುವುದು\s+ಪ್ರಾರಂಭಿಸಿ|ಟೈಪ್\s+ಮೋಡ್)$",
                target_mode=ProcessingMode.DICTATION,
                priority=10
            ),
            ModePattern(
                pattern=r"^(ಬರವಣಿಗೆ\s+ಮೋಡ್|ಟೈಪಿಂಗ್\s+ಪ್ರಾರಂಭಿಸಿ)$",
                target_mode=ProcessingMode.DICTATION,
                priority=8
            ),
            
            # Implicit command indicators
            ModePattern(
                pattern=r"^(ತೆರೆಯಿರಿ|ಮುಚ್ಚಿರಿ|ಕ್ಲಿಕ್\s+ಮಾಡಿ|ರನ್\s+ಮಾಡಿ|ಪ್ರಾರಂಭಿಸಿ)",
                target_mode=ProcessingMode.COMMAND,
                priority=3
            ),
            
            # Implicit dictation indicators
            ModePattern(
                pattern=r"^(ಪ್ರಿಯ|ನಮಸ್ಕಾರ|ಹಲೋ|ಇದು|ಅದು|ನಾನು|ನೀವು|ನಾವು|ಅವರು)",
                target_mode=ProcessingMode.DICTATION,
                priority=2
            )
        ])
        
        # Malayalam patterns
        self.register_patterns("ml", [
            # Command mode patterns
            ModePattern(
                pattern=r"^(കമാൻഡ്\s+മോഡ്|ആദേശ\s+രീതി|കമാൻഡ്\s+ഓൺ\s+ചെയ്യുക)$",
                target_mode=ProcessingMode.COMMAND,
                priority=10
            ),
            ModePattern(
                pattern=r"^(കമാൻഡ്\s+ആരംഭിക്കുക|ആദേശങ്ങൾ\s+ആരംഭിക്കുക)$",
                target_mode=ProcessingMode.COMMAND,
                priority=8
            ),
            
            # Dictation mode patterns
            ModePattern(
                pattern=r"^(ഡിക്ടേഷൻ\s+മോഡ്|എഴുതുന്നത്\s+ആരംഭിക്കുക|ടൈപ്പ്\s+മോഡ്)$",
                target_mode=ProcessingMode.DICTATION,
                priority=10
            ),
            ModePattern(
                pattern=r"^(എഴുത്ത്\s+മോഡ്|ടൈപ്പിംഗ്\s+ആരംഭിക്കുക)$",
                target_mode=ProcessingMode.DICTATION,
                priority=8
            ),
            
            # Implicit command indicators
            ModePattern(
                pattern=r"^(തുറക്കുക|അടയ്ക്കുക|ക്ലിക്ക്\s+ചെയ്യുക|റൺ\s+ചെയ്യുക|ആരംഭിക്കുക)",
                target_mode=ProcessingMode.COMMAND,
                priority=3
            ),
            
            # Implicit dictation indicators
            ModePattern(
                pattern=r"^(പ്രിയ|നമസ്കാരം|ഹലോ|ഇത്|അത്|ഞാൻ|നിങ്ങൾ|ഞങ്ങൾ|അവർ)",
                target_mode=ProcessingMode.DICTATION,
                priority=2
            )
        ])
        
        # Punjabi patterns
        self.register_patterns("pa", [
            # Command mode patterns
            ModePattern(
                pattern=r"^(ਕਮਾਂਡ\s+ਮੋਡ|ਹੁਕਮ\s+ਮੋਡ|ਕਮਾਂਡ\s+ਚਾਲੂ\s+ਕਰੋ)$",
                target_mode=ProcessingMode.COMMAND,
                priority=10
            ),
            ModePattern(
                pattern=r"^(ਕਮਾਂਡ\s+ਸ਼ੁਰੂ\s+ਕਰੋ|ਹੁਕਮ\s+ਸ਼ੁਰੂ\s+ਕਰੋ)$",
                target_mode=ProcessingMode.COMMAND,
                priority=8
            ),
            
            # Dictation mode patterns
            ModePattern(
                pattern=r"^(ਡਿਕਟੇਸ਼ਨ\s+ਮੋਡ|ਲਿਖਣਾ\s+ਸ਼ੁਰੂ\s+ਕਰੋ|ਟਾਈਪ\s+ਮੋਡ)$",
                target_mode=ProcessingMode.DICTATION,
                priority=10
            ),
            ModePattern(
                pattern=r"^(ਲੇਖਣ\s+ਮੋਡ|ਟਾਈਪਿੰਗ\s+ਸ਼ੁਰੂ\s+ਕਰੋ)$",
                target_mode=ProcessingMode.DICTATION,
                priority=8
            ),
            
            # Implicit command indicators
            ModePattern(
                pattern=r"^(ਖੋਲ੍ਹੋ|ਬੰਦ\s+ਕਰੋ|ਕਲਿੱਕ\s+ਕਰੋ|ਚਲਾਓ|ਸ਼ੁਰੂ\s+ਕਰੋ)",
                target_mode=ProcessingMode.COMMAND,
                priority=3
            ),
            
            # Implicit dictation indicators
            ModePattern(
                pattern=r"^(ਪਿਆਰੇ|ਸਤ\s+ਸ਼ਰੀ\s+ਅਕਾਲ|ਹੈਲੋ|ਇਹ|ਉਹ|ਮੈਂ|ਤੁਸੀਂ|ਅਸੀਂ|ਉਹ)",
                target_mode=ProcessingMode.DICTATION,
                priority=2
            )
        ])
        
        # Bhojpuri patterns
        self.register_patterns("bho", [
            # Command mode patterns
            ModePattern(
                pattern=r"^(कमांड\s+मोड|आदेश\s+मोड|कमांड\s+चालू\s+करा)$",
                target_mode=ProcessingMode.COMMAND,
                priority=10
            ),
            ModePattern(
                pattern=r"^(कमांड\s+शुरू\s+करा|आदेश\s+शुरू\s+करा)$",
                target_mode=ProcessingMode.COMMAND,
                priority=8
            ),
            
            # Dictation mode patterns
            ModePattern(
                pattern=r"^(डिक्टेशन\s+मोड|लिखल\s+शुरू\s+करा|टाइप\s+मोड)$",
                target_mode=ProcessingMode.DICTATION,
                priority=10
            ),
            ModePattern(
                pattern=r"^(लेखन\s+मोड|टाइपिंग\s+शुरू\s+करा)$",
                target_mode=ProcessingMode.DICTATION,
                priority=8
            ),
            
            # Implicit command indicators
            ModePattern(
                pattern=r"^(खोला|बंद\s+करा|क्लिक\s+करा|चलावा|शुरू\s+करा)",
                target_mode=ProcessingMode.COMMAND,
                priority=3
            ),
            
            # Implicit dictation indicators
            ModePattern(
                pattern=r"^(प्रिय|नमस्कार|हैलो|ई|ओ|हम|रउआ|हमनी|ओकरा)",
                target_mode=ProcessingMode.DICTATION,
                priority=2
            )
        ])
        
        self.logger.info(f"Initialized mode patterns for {len(self._patterns)} languages")
        
    def register_patterns(self, language: str, patterns: List[ModePattern]):
        """Register mode patterns for a language."""
        with self._lock:
            if not SupportedLanguages.is_supported(language):
                raise UnsupportedLanguageError(
                    f"Cannot register patterns for unsupported language: {language}",
                    requested_language=language,
                    supported_languages=SupportedLanguages.get_language_codes()
                )
                
            # Sort patterns by priority (highest first)
            sorted_patterns = sorted(patterns, key=lambda p: p.priority, reverse=True)
            self._patterns[language] = sorted_patterns
            
            self.logger.info(f"Registered {len(patterns)} mode patterns for {language}")
            
    def get_patterns(self, language: str) -> List[ModePattern]:
        """Get mode patterns for a language."""
        with self._lock:
            return self._patterns.get(language, [])
            
    def add_pattern(self, language: str, pattern: ModePattern):
        """Add a single pattern to a language."""
        with self._lock:
            if language not in self._patterns:
                self._patterns[language] = []
                
            self._patterns[language].append(pattern)
            
            # Re-sort by priority
            self._patterns[language].sort(key=lambda p: p.priority, reverse=True)
            
    def get_supported_languages(self) -> List[str]:
        """Get list of languages with registered patterns."""
        with self._lock:
            return list(self._patterns.keys())


class MultilingualModeClassifier:
    """
    Production-grade multilingual mode classifier that determines processing mode
    (command vs dictation) with consistent behavior across all supported languages.
    """
    
    def __init__(self, config: MultilingualConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Initialize components
        self.pattern_registry = ModePatternRegistry()
        self.mode_history = ModeHistory()
        
        # Current session state
        self._current_mode = ProcessingMode.COMMAND  # Default mode
        self._session_lock = RLock()
        
        # Mode feedback system
        self._feedback_enabled = True
        self._audio_feedback_enabled = True
        self._visual_feedback_enabled = True
        
        # Classification statistics
        self._classification_stats = {
            'total_classifications': 0,
            'explicit_mode_switches': 0,
            'automatic_detections': 0,
            'fallback_uses': 0,
            'average_processing_time_ms': 0.0
        }
        
    def provide_mode_feedback(self, mode: ProcessingMode, language: str, transition_type: ModeTransition) -> Dict[str, str]:
        """
        Provide language-appropriate feedback for mode transitions.
        
        Returns:
            Dictionary with audio and visual feedback messages
        """
        
        if not self._feedback_enabled:
            return {'audio': '', 'visual': ''}
            
        # Language-specific feedback messages
        feedback_messages = {
            'en': {
                ProcessingMode.COMMAND: {
                    'audio': 'Command mode activated',
                    'visual': '🎯 Command Mode'
                },
                ProcessingMode.DICTATION: {
                    'audio': 'Dictation mode activated',
                    'visual': '✍️ Dictation Mode'
                }
            },
            'hi': {
                ProcessingMode.COMMAND: {
                    'audio': 'कमांड मोड सक्रिय',
                    'visual': '🎯 कमांड मोड'
                },
                ProcessingMode.DICTATION: {
                    'audio': 'डिक्टेशन मोड सक्रिय',
                    'visual': '✍️ डिक्टेशन मोड'
                }
            },
            'ta': {
                ProcessingMode.COMMAND: {
                    'audio': 'கமாண்ட் மோட் ஆக்டிவ்',
                    'visual': '🎯 கமாண்ட் மோட்'
                },
                ProcessingMode.DICTATION: {
                    'audio': 'டிக்டேஷன் மோட் ஆக்டிவ்',
                    'visual': '✍️ டிக்டேஷன் மோட்'
                }
            },
            'de': {
                ProcessingMode.COMMAND: {
                    'audio': 'Befehlsmodus aktiviert',
                    'visual': '🎯 Befehlsmodus'
                },
                ProcessingMode.DICTATION: {
                    'audio': 'Diktatmodus aktiviert',
                    'visual': '✍️ Diktatmodus'
                }
            },
            'fr': {
                ProcessingMode.COMMAND: {
                    'audio': 'Mode commande activé',
                    'visual': '🎯 Mode Commande'
                },
                ProcessingMode.DICTATION: {
                    'audio': 'Mode dictée activé',
                    'visual': '✍️ Mode Dictée'
                }
            },
            'zh': {
                ProcessingMode.COMMAND: {
                    'audio': '命令模式已激活',
                    'visual': '🎯 命令模式'
                },
                ProcessingMode.DICTATION: {
                    'audio': '听写模式已激活',
                    'visual': '✍️ 听写模式'
                }
            },
            'ja': {
                ProcessingMode.COMMAND: {
                    'audio': 'コマンドモードが有効になりました',
                    'visual': '🎯 コマンドモード'
                },
                ProcessingMode.DICTATION: {
                    'audio': 'ディクテーションモードが有効になりました',
                    'visual': '✍️ ディクテーションモード'
                }
            },
            'te': {
                ProcessingMode.COMMAND: {
                    'audio': 'కమాండ్ మోడ్ యాక్టివేట్ అయింది',
                    'visual': '🎯 కమాండ్ మోడ్'
                },
                ProcessingMode.DICTATION: {
                    'audio': 'డిక్టేషన్ మోడ్ యాక్టివేట్ అయింది',
                    'visual': '✍️ డిక్టేషన్ మోడ్'
                }
            },
            'bn': {
                ProcessingMode.COMMAND: {
                    'audio': 'কমান্ড মোড সক্রিয়',
                    'visual': '🎯 কমান্ড মোড'
                },
                ProcessingMode.DICTATION: {
                    'audio': 'ডিক্টেশন মোড সক্রিয়',
                    'visual': '✍️ ডিক্টেশন মোড'
                }
            },
            'mr': {
                ProcessingMode.COMMAND: {
                    'audio': 'कमांड मोड सक्रिय',
                    'visual': '🎯 कमांड मोड'
                },
                ProcessingMode.DICTATION: {
                    'audio': 'डिक्टेशन मोड सक्रिय',
                    'visual': '✍️ डिक्टेशन मोड'
                }
            },
            'gu': {
                ProcessingMode.COMMAND: {
                    'audio': 'કમાન્ડ મોડ સક્રિય',
                    'visual': '🎯 કમાન્ડ મોડ'
                },
                ProcessingMode.DICTATION: {
                    'audio': 'ડિક્ટેશન મોડ સક્રિય',
                    'visual': '✍️ ડિક્ટેશન મોડ'
                }
            },
            'kn': {
                ProcessingMode.COMMAND: {
                    'audio': 'ಕಮಾಂಡ್ ಮೋಡ್ ಸಕ್ರಿಯ',
                    'visual': '🎯 ಕಮಾಂಡ್ ಮೋಡ್'
                },
                ProcessingMode.DICTATION: {
                    'audio': 'ಡಿಕ್ಟೇಶನ್ ಮೋಡ್ ಸಕ್ರಿಯ',
                    'visual': '✍️ ಡಿಕ್ಟೇಶನ್ ಮೋಡ್'
                }
            },
            'ml': {
                ProcessingMode.COMMAND: {
                    'audio': 'കമാൻഡ് മോഡ് സജീവമാക്കി',
                    'visual': '🎯 കമാൻഡ് മോഡ്'
                },
                ProcessingMode.DICTATION: {
                    'audio': 'ഡിക്ടേഷൻ മോഡ് സജീവമാക്കി',
                    'visual': '✍️ ഡിക്ടേഷൻ മോഡ്'
                }
            },
            'pa': {
                ProcessingMode.COMMAND: {
                    'audio': 'ਕਮਾਂਡ ਮੋਡ ਸਰਗਰਮ',
                    'visual': '🎯 ਕਮਾਂਡ ਮੋਡ'
                },
                ProcessingMode.DICTATION: {
                    'audio': 'ਡਿਕਟੇਸ਼ਨ ਮੋਡ ਸਰਗਰਮ',
                    'visual': '✍️ ਡਿਕਟੇਸ਼ਨ ਮੋਡ'
                }
            },
            'bho': {
                ProcessingMode.COMMAND: {
                    'audio': 'कमांड मोड सक्रिय',
                    'visual': '🎯 कमांड मोड'
                },
                ProcessingMode.DICTATION: {
                    'audio': 'डिक्टेशन मोड सक्रिय',
                    'visual': '✍️ डिक्टेशन मोड'
                }
            }
        }
        
        # Get feedback for language, fallback to English
        lang_feedback = feedback_messages.get(language, feedback_messages['en'])
        mode_feedback = lang_feedback.get(mode, lang_feedback[ProcessingMode.COMMAND])
        
        # Add transition context for explicit switches
        if transition_type == ModeTransition.EXPLICIT_COMMAND:
            if language == 'en':
                mode_feedback['audio'] += ' - Voice command recognized'
            elif language == 'hi':
                mode_feedback['audio'] += ' - आवाज़ कमांड पहचाना गया'
            elif language == 'ta':
                mode_feedback['audio'] += ' - குரல் கட்டளை அங்கீகரிக்கப்பட்டது'
            # Add more languages as needed
                
        return {
            'audio': mode_feedback['audio'] if self._audio_feedback_enabled else '',
            'visual': mode_feedback['visual'] if self._visual_feedback_enabled else ''
        }
        
    def log_mode_transition(
        self, 
        result: ModeClassificationResult, 
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Log mode transition for audit purposes with language context.
        
        Args:
            result: Mode classification result
            session_id: Optional session ID
            
        Returns:
            Log entry dictionary
        """
        
        log_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'event_type': 'MODE_TRANSITION',
            'session_id': session_id,
            'language': result.language,
            'previous_mode': result.previous_mode.value if result.previous_mode else None,
            'new_mode': result.mode.value,
            'transition_type': result.transition_type.value,
            'confidence': result.confidence,
            'mode_switched': result.mode_switched,
            'processing_time_ms': result.processing_time_ms,
            'patterns_evaluated': result.patterns_evaluated,
            'session_context_used': result.session_context_used,
            'fallback_used': result.fallback_used,
            'success': result.success,
            'error': result.error,
            'warnings': result.warnings
        }
        
        # Add switch command details if available
        if result.switch_command:
            log_entry['switch_command'] = {
                'command_text': result.switch_command.command_text,
                'pattern_matched': result.switch_command.pattern_matched,
                'command_confidence': result.switch_command.confidence
            }
            
        # Log the transition
        if result.mode_switched:
            self.logger.info(f"Mode transition: {result.previous_mode.value if result.previous_mode else 'unknown'} -> {result.mode.value} ({result.transition_type.value})")
        else:
            self.logger.debug(f"Mode classification: {result.mode.value} (confidence: {result.confidence:.2f})")
            
        return log_entry
        
    def classify_mode(
        self, 
        text: str, 
        language: str,
        session_id: Optional[str] = None,
        use_session_context: bool = True
    ) -> ModeClassificationResult:
        """
        Classify processing mode for input text.
        
        Args:
            text: Input text to classify
            language: Detected language code
            session_id: Optional session ID for context
            use_session_context: Whether to use session context
            
        Returns:
            ModeClassificationResult with classification details
        """
        
        start_time = time.time()
        
        try:
            # Validate inputs
            if not text or not text.strip():
                return ModeClassificationResult(
                    mode=self._current_mode,
                    confidence=0.5,
                    transition_type=ModeTransition.SESSION_DEFAULT,
                    processing_time_ms=int((time.time() - start_time) * 1000),
                    language=language,
                    fallback_used=True,
                    warnings=["Empty input text, using current mode"]
                )
                
            if not SupportedLanguages.is_supported(language):
                return ModeClassificationResult(
                    mode=self._current_mode,
                    confidence=0.3,
                    transition_type=ModeTransition.FALLBACK,
                    processing_time_ms=int((time.time() - start_time) * 1000),
                    language=language,
                    fallback_used=True,
                    error=f"Unsupported language: {language}"
                )
                
            # Check for explicit mode switching commands
            switch_result = self._check_mode_switch_command(text, language)
            if switch_result:
                classification_result = self._handle_mode_switch(switch_result, start_time, language)
                
                # Provide feedback and log transition
                if classification_result.mode_switched:
                    feedback = self.provide_mode_feedback(
                        classification_result.mode, 
                        language, 
                        classification_result.transition_type
                    )
                    classification_result.warnings.extend([
                        f"Audio feedback: {feedback['audio']}", 
                        f"Visual feedback: {feedback['visual']}"
                    ])
                    
                    # Log the transition
                    self.log_mode_transition(classification_result, session_id)
                    
                return classification_result
                
            # Use session context if available and enabled
            if use_session_context:
                recent_mode = self.mode_history.get_recent_mode(5)  # 5 minutes
                if recent_mode:
                    return ModeClassificationResult(
                        mode=recent_mode,
                        confidence=0.8,
                        transition_type=ModeTransition.SESSION_DEFAULT,
                        processing_time_ms=int((time.time() - start_time) * 1000),
                        language=language,
                        session_context_used=True
                    )
                    
            # Perform automatic mode detection
            detection_result = self._detect_mode_automatically(text, language, start_time)
            
            # Update statistics
            self._update_classification_stats(detection_result)
            
            return detection_result
            
        except Exception as e:
            return ModeClassificationResult(
                mode=self._current_mode,
                confidence=0.1,
                transition_type=ModeTransition.FALLBACK,
                processing_time_ms=int((time.time() - start_time) * 1000),
                language=language,
                fallback_used=True,
                error=f"Mode classification failed: {str(e)}"
            )
            
    def _check_mode_switch_command(self, text: str, language: str) -> Optional[ModeSwitchCommand]:
        """Check if text contains explicit mode switching command."""
        
        patterns = self.pattern_registry.get_patterns(language)
        
        # Only check high-priority explicit patterns (priority >= 8)
        explicit_patterns = [p for p in patterns if p.priority >= 8]
        
        for pattern in explicit_patterns:
            if pattern.matches(text):
                return ModeSwitchCommand(
                    new_mode=pattern.target_mode,
                    command_text=text,
                    language=language,
                    confidence=pattern.confidence,
                    pattern_matched=pattern.pattern
                )
                
        return None
        
    def _handle_mode_switch(
        self, 
        switch_command: ModeSwitchCommand, 
        start_time: float,
        language: str
    ) -> ModeClassificationResult:
        """Handle explicit mode switching."""
        
        with self._session_lock:
            previous_mode = self._current_mode
            self._current_mode = switch_command.new_mode
            
        # Record mode change in history
        self.mode_history.record_mode_change(
            switch_command.new_mode,
            f"Explicit switch: {switch_command.command_text}"
        )
        
        self._classification_stats['explicit_mode_switches'] += 1
        
        self.logger.info(f"Mode switched from {previous_mode.value} to {switch_command.new_mode.value}")
        
        return ModeClassificationResult(
            mode=switch_command.new_mode,
            confidence=switch_command.confidence,
            transition_type=ModeTransition.EXPLICIT_COMMAND,
            mode_switched=True,
            switch_command=switch_command,
            previous_mode=previous_mode,
            processing_time_ms=int((time.time() - start_time) * 1000),
            language=language
        )
        
    def _detect_mode_automatically(
        self, 
        text: str, 
        language: str, 
        start_time: float
    ) -> ModeClassificationResult:
        """Automatically detect mode based on text patterns."""
        
        patterns = self.pattern_registry.get_patterns(language)
        patterns_evaluated = 0
        
        # Check implicit patterns (priority < 8)
        implicit_patterns = [p for p in patterns if p.priority < 8]
        
        best_match = None
        best_confidence = 0.0
        
        for pattern in implicit_patterns:
            patterns_evaluated += 1
            
            if pattern.matches(text):
                if pattern.confidence > best_confidence:
                    best_match = pattern
                    best_confidence = pattern.confidence
                    
        if best_match:
            detected_mode = best_match.target_mode
            confidence = best_confidence * 0.7  # Lower confidence for automatic detection
            
            # Record mode detection in history
            self.mode_history.record_mode_change(
                detected_mode,
                f"Automatic detection: {best_match.pattern}"
            )
            
            self._classification_stats['automatic_detections'] += 1
            
        else:
            # No pattern matched, use current mode
            detected_mode = self._current_mode
            confidence = 0.5
            self._classification_stats['fallback_uses'] += 1
            
        return ModeClassificationResult(
            mode=detected_mode,
            confidence=confidence,
            transition_type=ModeTransition.AUTOMATIC_DETECTION if best_match else ModeTransition.FALLBACK,
            processing_time_ms=int((time.time() - start_time) * 1000),
            patterns_evaluated=patterns_evaluated,
            language=language,
            fallback_used=(best_match is None)
        )
        
    def get_current_mode(self) -> ProcessingMode:
        """Get current processing mode."""
        with self._session_lock:
            return self._current_mode
            
    def set_mode(self, mode: ProcessingMode, reason: str = "Manual override"):
        """Manually set processing mode."""
        with self._session_lock:
            previous_mode = self._current_mode
            self._current_mode = mode
            
        self.mode_history.record_mode_change(mode, reason)
        self.logger.info(f"Mode manually set from {previous_mode.value} to {mode.value}: {reason}")
        
    def _update_classification_stats(self, result: ModeClassificationResult):
        """Update classification statistics."""
        self._classification_stats['total_classifications'] += 1
        
        # Update average processing time
        current_avg = self._classification_stats['average_processing_time_ms']
        total_classifications = self._classification_stats['total_classifications']
        
        new_avg = ((current_avg * (total_classifications - 1)) + result.processing_time_ms) / total_classifications
        self._classification_stats['average_processing_time_ms'] = new_avg
        
    def get_classification_statistics(self) -> Dict[str, Any]:
        """Get mode classification statistics."""
        total = self._classification_stats['total_classifications']
        
        return {
            **self._classification_stats,
            'explicit_switch_rate': (
                self._classification_stats['explicit_mode_switches'] / max(1, total)
            ),
            'automatic_detection_rate': (
                self._classification_stats['automatic_detections'] / max(1, total)
            ),
            'fallback_rate': (
                self._classification_stats['fallback_uses'] / max(1, total)
            ),
            'current_mode': self._current_mode.value,
            'mode_history_summary': self.mode_history.get_history_summary(),
            'supported_languages': self.pattern_registry.get_supported_languages()
        }
        
    def add_custom_pattern(self, language: str, pattern: ModePattern) -> bool:
        """Add custom mode pattern for a language."""
        try:
            self.pattern_registry.add_pattern(language, pattern)
            self.logger.info(f"Added custom mode pattern for {language}: {pattern.pattern}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to add custom mode pattern: {e}")
            return False
            
    def reset_session(self):
        """Reset session state and history."""
        with self._session_lock:
            self._current_mode = ProcessingMode.COMMAND
            
        self.mode_history.clear_history()
        self.logger.info("Reset mode classification session")
        
    def cleanup(self):
        """Cleanup resources and clear history."""
        self.mode_history.clear_history()
        self.logger.info("Mode classifier cleanup completed")
        
    def set_feedback_enabled(self, audio: bool = True, visual: bool = True):
        """Enable or disable mode feedback."""
        self._audio_feedback_enabled = audio
        self._visual_feedback_enabled = visual
        self._feedback_enabled = audio or visual
        
        self.logger.info(f"Mode feedback settings: audio={audio}, visual={visual}")
        
    def get_feedback_settings(self) -> Dict[str, bool]:
        """Get current feedback settings."""
        return {
            'feedback_enabled': self._feedback_enabled,
            'audio_feedback_enabled': self._audio_feedback_enabled,
            'visual_feedback_enabled': self._visual_feedback_enabled
        }