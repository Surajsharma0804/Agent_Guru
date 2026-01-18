/**
 * Phoneme to viseme mapping constants for lip synchronization
 * Based on industry standard 15-viseme system
 */

/**
 * Standard viseme set (15 visemes)
 */
export const STANDARD_VISEMES = [
  'sil',  // Silence
  'PP',   // Bilabial (p, b, m)
  'FF',   // Labiodental (f, v)
  'TH',   // Dental (th, dh)
  'DD',   // Alveolar (t, d, n, l)
  'kk',   // Velar (k, g, ng)
  'CH',   // Postalveolar (ch, sh, j, zh)
  'SS',   // Fricative (s, z)
  'nn',   // Nasal (n, ng)
  'RR',   // Rhotic (r)
  'aa',   // Open vowel (a, ah, ae)
  'E',    // Mid vowel (e, eh, er)
  'ih',   // Close vowel (i, ih, iy)
  'oh',   // Back vowel (o, oh, ow)
  'ou'    // Close back vowel (u, uh, uw)
] as const;

/**
 * Phoneme to viseme mapping (ARPABET to viseme)
 */
export const PHONEME_VISEME_MAP: Record<string, string> = {
  // Silence
  'sil': 'sil',
  'sp': 'sil',
  'pau': 'sil',
  
  // Bilabial sounds (lips together)
  'p': 'PP',
  'b': 'PP',
  'm': 'PP',
  
  // Labiodental sounds (lip to teeth)
  'f': 'FF',
  'v': 'FF',
  
  // Dental sounds (tongue to teeth)
  'th': 'TH',
  'dh': 'TH',
  
  // Alveolar sounds (tongue to alveolar ridge)
  't': 'DD',
  'd': 'DD',
  'n': 'DD',
  'l': 'DD',
  
  // Velar sounds (tongue to soft palate)
  'k': 'kk',
  'g': 'kk',
  'ng': 'kk',
  
  // Postalveolar sounds (tongue behind alveolar ridge)
  'ch': 'CH',
  'jh': 'CH',
  'sh': 'CH',
  'zh': 'CH',
  
  // Fricatives (s sounds)
  's': 'SS',
  'z': 'SS',
  
  // Nasal sounds
  'nn': 'nn',
  
  // Rhotic sounds (r sounds)
  'r': 'RR',
  'er': 'RR',
  
  // Open vowels (mouth open)
  'aa': 'aa',
  'ae': 'aa',
  'ah': 'aa',
  'ao': 'aa',
  'aw': 'aa',
  'ay': 'aa',
  
  // Mid vowels
  'e': 'E',
  'eh': 'E',
  'ey': 'E',
  
  // Close vowels (mouth more closed)
  'i': 'ih',
  'ih': 'ih',
  'iy': 'ih',
  
  // Back vowels (tongue back)
  'o': 'oh',
  'oh': 'oh',
  'ow': 'oh',
  'oy': 'oh',
  
  // Close back vowels (rounded lips)
  'u': 'ou',
  'uh': 'ou',
  'uw': 'ou'
};

/**
 * IPA (International Phonetic Alphabet) to viseme mapping
 */
export const IPA_VISEME_MAP: Record<string, string> = {
  // Silence
  '∅': 'sil',
  
  // Bilabial
  'p': 'PP',
  'b': 'PP',
  'm': 'PP',
  
  // Labiodental
  'f': 'FF',
  'v': 'FF',
  
  // Dental
  'θ': 'TH',
  'ð': 'TH',
  
  // Alveolar
  't': 'DD',
  'd': 'DD',
  'n': 'DD',
  'l': 'DD',
  
  // Velar
  'k': 'kk',
  'g': 'kk',
  'ŋ': 'kk',
  
  // Postalveolar
  'ʃ': 'CH',
  'ʒ': 'CH',
  'tʃ': 'CH',
  'dʒ': 'CH',
  
  // Fricatives
  's': 'SS',
  'z': 'SS',
  
  // Nasal
  'ɲ': 'nn',
  
  // Rhotic
  'r': 'RR',
  'ɹ': 'RR',
  'ɚ': 'RR',
  'ɝ': 'RR',
  
  // Vowels - Open
  'a': 'aa',
  'ɑ': 'aa',
  'æ': 'aa',
  'ɒ': 'aa',
  
  // Vowels - Mid
  'e': 'E',
  'ɛ': 'E',
  'ə': 'E',
  'ɜ': 'E',
  
  // Vowels - Close
  'i': 'ih',
  'ɪ': 'ih',
  
  // Vowels - Back
  'o': 'oh',
  'ɔ': 'oh',
  
  // Vowels - Close back
  'u': 'ou',
  'ʊ': 'ou'
};

/**
 * Viseme mouth shape configurations
 */
export const VISEME_MOUTH_SHAPES = {
  'sil': {
    openness: 0.0,
    width: 0.5,
    lipRounding: 0.0,
    tonguePosition: { x: 0.0, y: 0.0, z: 0.0 },
    teethVisibility: 0.0,
    lipTension: 0.2
  },
  'PP': {
    openness: 0.0,
    width: 0.3,
    lipRounding: 0.0,
    tonguePosition: { x: 0.0, y: 0.0, z: 0.0 },
    teethVisibility: 0.0,
    lipTension: 0.8
  },
  'FF': {
    openness: 0.1,
    width: 0.4,
    lipRounding: 0.0,
    tonguePosition: { x: 0.0, y: -0.2, z: 0.0 },
    teethVisibility: 0.7,
    lipTension: 0.6
  },
  'TH': {
    openness: 0.2,
    width: 0.5,
    lipRounding: 0.0,
    tonguePosition: { x: 0.0, y: 0.3, z: 0.8 },
    teethVisibility: 0.8,
    lipTension: 0.4
  },
  'DD': {
    openness: 0.3,
    width: 0.5,
    lipRounding: 0.0,
    tonguePosition: { x: 0.0, y: 0.5, z: 0.6 },
    teethVisibility: 0.5,
    lipTension: 0.4
  },
  'kk': {
    openness: 0.4,
    width: 0.6,
    lipRounding: 0.0,
    tonguePosition: { x: 0.0, y: -0.3, z: -0.5 },
    teethVisibility: 0.3,
    lipTension: 0.3
  },
  'CH': {
    openness: 0.2,
    width: 0.4,
    lipRounding: 0.2,
    tonguePosition: { x: 0.0, y: 0.2, z: 0.3 },
    teethVisibility: 0.4,
    lipTension: 0.5
  },
  'SS': {
    openness: 0.1,
    width: 0.4,
    lipRounding: 0.0,
    tonguePosition: { x: 0.0, y: 0.4, z: 0.7 },
    teethVisibility: 0.9,
    lipTension: 0.6
  },
  'nn': {
    openness: 0.0,
    width: 0.5,
    lipRounding: 0.0,
    tonguePosition: { x: 0.0, y: 0.3, z: 0.5 },
    teethVisibility: 0.0,
    lipTension: 0.3
  },
  'RR': {
    openness: 0.3,
    width: 0.5,
    lipRounding: 0.3,
    tonguePosition: { x: 0.0, y: 0.0, z: -0.2 },
    teethVisibility: 0.2,
    lipTension: 0.4
  },
  'aa': {
    openness: 0.8,
    width: 0.7,
    lipRounding: 0.0,
    tonguePosition: { x: 0.0, y: -0.5, z: 0.0 },
    teethVisibility: 0.6,
    lipTension: 0.2
  },
  'E': {
    openness: 0.5,
    width: 0.6,
    lipRounding: 0.0,
    tonguePosition: { x: 0.0, y: 0.0, z: 0.2 },
    teethVisibility: 0.4,
    lipTension: 0.3
  },
  'ih': {
    openness: 0.2,
    width: 0.8,
    lipRounding: 0.0,
    tonguePosition: { x: 0.0, y: 0.3, z: 0.4 },
    teethVisibility: 0.5,
    lipTension: 0.4
  },
  'oh': {
    openness: 0.6,
    width: 0.4,
    lipRounding: 0.6,
    tonguePosition: { x: 0.0, y: -0.2, z: -0.3 },
    teethVisibility: 0.1,
    lipTension: 0.3
  },
  'ou': {
    openness: 0.3,
    width: 0.3,
    lipRounding: 0.9,
    tonguePosition: { x: 0.0, y: -0.1, z: -0.5 },
    teethVisibility: 0.0,
    lipTension: 0.5
  }
} as const;

/**
 * Viseme transition rules for smooth animation
 */
export const VISEME_TRANSITIONS = {
  // Fast transitions (consonants)
  FAST: {
    duration: 50, // milliseconds
    visemes: ['PP', 'FF', 'TH', 'DD', 'kk', 'CH', 'SS', 'nn', 'RR']
  },
  
  // Medium transitions (semi-vowels)
  MEDIUM: {
    duration: 100, // milliseconds
    visemes: ['sil']
  },
  
  // Slow transitions (vowels)
  SLOW: {
    duration: 150, // milliseconds
    visemes: ['aa', 'E', 'ih', 'oh', 'ou']
  }
} as const;

/**
 * Coarticulation rules (how phonemes affect each other)
 */
export const COARTICULATION_RULES = {
  // Lip rounding anticipation
  ROUNDING_ANTICIPATION: {
    triggers: ['ou', 'oh'],
    effect: 'increase_lip_rounding',
    strength: 0.3,
    duration: 100 // milliseconds before the rounded vowel
  },
  
  // Nasal anticipation
  NASAL_ANTICIPATION: {
    triggers: ['nn', 'm', 'ng'],
    effect: 'lower_velum',
    strength: 0.5,
    duration: 80
  },
  
  // Fricative preparation
  FRICATIVE_PREPARATION: {
    triggers: ['SS', 'FF', 'TH', 'CH'],
    effect: 'increase_tongue_precision',
    strength: 0.4,
    duration: 60
  }
} as const;

/**
 * Language-specific phoneme variations
 */
export const LANGUAGE_VARIATIONS = {
  'en-US': {
    // American English specific mappings
    'r': 'RR',
    'er': 'RR',
    'ar': 'RR'
  },
  'en-GB': {
    // British English specific mappings
    'r': 'sil', // Non-rhotic
    'er': 'E',
    'ar': 'aa'
  },
  'es': {
    // Spanish specific mappings
    'rr': 'RR', // Rolled R
    'ñ': 'nn'
  },
  'fr': {
    // French specific mappings
    'r': 'RR', // Uvular R
    'œ': 'E',
    'y': 'ih'
  },
  'de': {
    // German specific mappings
    'r': 'RR', // Uvular R
    'ü': 'ih',
    'ö': 'E'
  }
} as const;

/**
 * Emotional modulation for visemes
 */
export const EMOTIONAL_VISEME_MODULATION = {
  'happy': {
    mouth_curvature: 0.3,
    lip_tension: -0.2,
    openness_multiplier: 1.1
  },
  'sad': {
    mouth_curvature: -0.2,
    lip_tension: 0.1,
    openness_multiplier: 0.9
  },
  'angry': {
    mouth_curvature: -0.1,
    lip_tension: 0.4,
    openness_multiplier: 0.8
  },
  'surprised': {
    mouth_curvature: 0.0,
    lip_tension: -0.3,
    openness_multiplier: 1.3
  },
  'disgusted': {
    mouth_curvature: -0.3,
    lip_tension: 0.3,
    openness_multiplier: 0.7
  },
  'fearful': {
    mouth_curvature: -0.1,
    lip_tension: 0.2,
    openness_multiplier: 0.9
  }
} as const;

/**
 * Viseme blend weights for morphing
 */
export const VISEME_BLEND_WEIGHTS = {
  // Primary viseme gets full weight
  PRIMARY_WEIGHT: 1.0,
  
  // Secondary viseme for transitions
  SECONDARY_WEIGHT: 0.3,
  
  // Coarticulation influence
  COARTICULATION_WEIGHT: 0.2,
  
  // Emotional modulation
  EMOTIONAL_WEIGHT: 0.15
} as const;

/**
 * Timing constants for lip sync
 */
export const LIP_SYNC_TIMING = {
  // Minimum phoneme duration
  MIN_PHONEME_DURATION: 30, // milliseconds
  
  // Maximum phoneme duration
  MAX_PHONEME_DURATION: 500, // milliseconds
  
  // Default phoneme duration
  DEFAULT_PHONEME_DURATION: 80, // milliseconds
  
  // Transition overlap
  TRANSITION_OVERLAP: 0.3, // 30% overlap
  
  // Look-ahead time for coarticulation
  COARTICULATION_LOOKAHEAD: 150, // milliseconds
  
  // Audio-visual sync tolerance
  SYNC_TOLERANCE: 40 // milliseconds
} as const;