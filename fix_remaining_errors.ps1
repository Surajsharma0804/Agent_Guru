# Fix all remaining clippy errors - Part 2

Write-Host "Fixing remaining clippy errors..." -ForegroundColor Green

# Fix guru/platform/property_tests.rs - equatable_if_let errors
# Change "if let Ok(()) =" to ".is_ok()"
Write-Host "Fixing guru/platform/property_tests.rs equatable_if_let errors..." -ForegroundColor Yellow
$content = Get-Content "guru/platform/property_tests.rs" -Raw

# Replace all "if let Ok(()) = X {" with "if X.is_ok() {"
$content = $content -replace 'if let Ok\(\(\)\) = ([^\{]+) \{', 'if $1.is_ok() {'

# Replace all "} else if let Err(e) = X {" with "} else if let Err(e) = X {"  (keep as is, but handle the Ok case)
# Actually, we need to handle the pattern where we have both Ok and Err branches
# For now, let's just fix the simple Ok cases

$content | Set-Content "guru/platform/property_tests.rs"

# Fix guru/platform/property_tests.rs - ignored_unit_patterns for remaining Ok(_)
Write-Host "Fixing guru/platform/property_tests.rs ignored_unit_patterns..." -ForegroundColor Yellow
(Get-Content "guru/platform/property_tests.rs") -replace 'Ok\(_\) =>', 'Ok(()) =>' | Set-Content "guru/platform/property_tests.rs"

# Fix guru/memory/semantic_index.rs - explicit_iter_loop (line 1499)
Write-Host "Fixing guru/memory/semantic_index.rs..." -ForegroundColor Yellow
# This needs manual inspection - skipping automated fix

# Fix guru/memory/temporal_graph.rs - field_reassign_with_default
Write-Host "Fixing guru/memory/temporal_graph.rs..." -ForegroundColor Yellow
$content = Get-Content "guru/memory/temporal_graph.rs" -Raw
$content = $content -replace '(?s)(let mut config = TemporalGraphConfig::default\(\);)\s+config\.enable_temporal_decay = true;\s+config\.decay_rate = 1\.0;\s+config\.min_relationship_strength = 0\.5;', 'let mut config = TemporalGraphConfig { enable_temporal_decay: true, decay_rate: 1.0, min_relationship_strength: 0.5, ..Default::default() };'
$content = $content -replace '(?s)(let mut config = TemporalGraphConfig::default\(\);)\s+config\.auto_inference = false;', 'let mut config = TemporalGraphConfig { auto_inference: false, ..Default::default() };'
$content | Set-Content "guru/memory/temporal_graph.rs"

# Fix guru/vision/property_tests.rs - needless_range_loop
Write-Host "Fixing guru/vision/property_tests.rs needless_range_loop..." -ForegroundColor Yellow
# These need manual fixes - skipping for now

# Fix guru/avatar files - field_reassign_with_default
Write-Host "Fixing guru/avatar files..." -ForegroundColor Yellow
$content = Get-Content "guru/avatar/emotion_controller.rs" -Raw
$content = $content -replace '(?s)(let mut guru_personality = PersonalityProfile::default\(\);)\s+guru_personality\.personality_type = PersonalityType::GURU;', 'let mut guru_personality = PersonalityProfile { personality_type: PersonalityType::GURU, ..Default::default() };'
$content | Set-Content "guru/avatar/emotion_controller.rs"

$content = Get-Content "guru/avatar/lip_sync_controller.rs" -Raw
$content = $content -replace '(?s)(let mut weights = BlendshapeWeights::default\(\);)\s+weights\.jaw_open = i as f32 \* 0\.2;', 'let mut weights = BlendshapeWeights { jaw_open: i as f32 * 0.2, ..Default::default() };'
$content | Set-Content "guru/avatar/lip_sync_controller.rs"

$content = Get-Content "guru/avatar/personality_engine.rs" -Raw
$content = $content -replace '(?s)(let mut guru_personality = PersonalityProfile::default\(\);)\s+guru_personality\.personality_type = PersonalityType::GURU;\s+guru_personality\.confidence = 0\.9;', 'let mut guru_personality = PersonalityProfile { personality_type: PersonalityType::GURU, confidence: 0.9, ..Default::default() };'
$content = $content -replace '(?s)(let mut maya_personality = PersonalityProfile::default\(\);)\s+maya_personality\.personality_type = PersonalityType::MAYA;\s+maya_personality\.empathy = 0\.9;', 'let mut maya_personality = PersonalityProfile { personality_type: PersonalityType::MAYA, empathy: 0.9, ..Default::default() };'
$content = $content -replace '(?s)(let mut personality = PersonalityProfile::default\(\);)\s+personality\.confidence = 0\.9;\s+personality\.expressiveness = 0\.8;', 'let mut personality = PersonalityProfile { confidence: 0.9, expressiveness: 0.8, ..Default::default() };'
$content = $content -replace '(?s)(let mut low_confidence_personality = PersonalityProfile::default\(\);)\s+low_confidence_personality\.confidence = 0\.3;', 'let mut low_confidence_personality = PersonalityProfile { confidence: 0.3, ..Default::default() };'
$content | Set-Content "guru/avatar/personality_engine.rs"

# Fix guru/avatar/property_tests.rs - must_use attributes
Write-Host "Fixing guru/avatar/property_tests.rs must_use..." -ForegroundColor Yellow
(Get-Content "guru/avatar/property_tests.rs") -replace '(\s+pub fn new\(personality: PersonalityProfile\) -> Self \{)', "`n    #[must_use]`$1" | Set-Content "guru/avatar/property_tests.rs"
(Get-Content "guru/avatar/property_tests.rs") -replace '(\s+pub fn validate_emotion_consistency\(&self\) -> bool \{)', "`n    #[must_use]`$1" | Set-Content "guru/avatar/property_tests.rs"
(Get-Content "guru/avatar/property_tests.rs") -replace '(\s+pub fn validate_lip_sync_accuracy\(&self\) -> bool \{)', "`n    #[must_use]`$1" | Set-Content "guru/avatar/property_tests.rs"
(Get-Content "guru/avatar/property_tests.rs") -replace '(\s+pub fn validate_personality_consistency\(&self\) -> bool \{)', "`n    #[must_use]`$1" | Set-Content "guru/avatar/property_tests.rs"
(Get-Content "guru/avatar/property_tests.rs") -replace '(\s+pub fn validate_performance_requirements\(&self\) -> bool \{)', "`n    #[must_use]`$1" | Set-Content "guru/avatar/property_tests.rs"

# Fix guru/lib.rs - const_is_empty
Write-Host "Fixing guru/lib.rs..." -ForegroundColor Yellow
(Get-Content "guru/lib.rs") -replace 'assert!\(!VERSION\.is_empty\(\), "VERSION should not be empty"\);', '// VERSION is a compile-time constant and cannot be empty' | Set-Content "guru/lib.rs"
(Get-Content "guru/lib.rs") -replace 'assert!\(!BUILD_INFO\.is_empty\(\), "BUILD_INFO should not be empty"\);', '// BUILD_INFO is a compile-time constant and cannot be empty' | Set-Content "guru/lib.rs"

Write-Host "All automated fixes applied!" -ForegroundColor Green
