# Fix final 19 clippy errors

Write-Host "Fixing final clippy errors..." -ForegroundColor Green

# Fix guru/avatar/property_tests.rs - empty_line_after_doc_comments
Write-Host "Fixing guru/avatar/property_tests.rs empty lines..." -ForegroundColor Yellow
$content = Get-Content "guru/avatar/property_tests.rs" -Raw
# Remove empty lines after #[must_use] attributes
$content = $content -replace '#\[must_use\]\s+\n\s+\n', "#[must_use]`n"
$content | Set-Content "guru/avatar/property_tests.rs"

# Fix unused mut variables
Write-Host "Fixing unused mut variables..." -ForegroundColor Yellow
(Get-Content "guru/memory/temporal_graph.rs") -replace 'let mut config = TemporalGraphConfig \{', 'let config = TemporalGraphConfig {' | Set-Content "guru/memory/temporal_graph.rs"
(Get-Content "guru/avatar/emotion_controller.rs") -replace 'let mut guru_personality = PersonalityProfile \{', 'let guru_personality = PersonalityProfile {' | Set-Content "guru/avatar/emotion_controller.rs"
(Get-Content "guru/avatar/lip_sync_controller.rs") -replace 'let mut weights = BlendshapeWeights \{', 'let weights = BlendshapeWeights {' | Set-Content "guru/avatar/lip_sync_controller.rs"
(Get-Content "guru/avatar/personality_engine.rs") -replace 'let mut guru_personality = PersonalityProfile \{', 'let guru_personality = PersonalityProfile {' | Set-Content "guru/avatar/personality_engine.rs"
(Get-Content "guru/avatar/personality_engine.rs") -replace 'let mut maya_personality = PersonalityProfile \{', 'let maya_personality = PersonalityProfile {' | Set-Content "guru/avatar/personality_engine.rs"
(Get-Content "guru/avatar/personality_engine.rs") -replace 'let mut personality = PersonalityProfile \{', 'let personality = PersonalityProfile {' | Set-Content "guru/avatar/personality_engine.rs"
(Get-Content "guru/avatar/personality_engine.rs") -replace 'let mut low_confidence_personality = PersonalityProfile \{', 'let low_confidence_personality = PersonalityProfile {' | Set-Content "guru/avatar/personality_engine.rs"

Write-Host "All final fixes applied!" -ForegroundColor Green
