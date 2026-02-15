# Fix all remaining clippy errors systematically

Write-Host "Fixing all remaining clippy errors..." -ForegroundColor Green

# Fix guru/memory/semantic_index.rs - explicit_iter_loop errors
Write-Host "Fixing guru/memory/semantic_index.rs..." -ForegroundColor Yellow
(Get-Content "guru/memory/semantic_index.rs") -replace 'for x in embedding\.iter_mut\(\)', 'for x in &mut embedding' | Set-Content "guru/memory/semantic_index.rs"
(Get-Content "guru/memory/semantic_index.rs") -replace 'for x in query\.iter_mut\(\)', 'for x in &mut query' | Set-Content "guru/memory/semantic_index.rs"

# Fix guru/memory/encryption.rs - field_reassign_with_default
Write-Host "Fixing guru/memory/encryption.rs..." -ForegroundColor Yellow
$content = Get-Content "guru/memory/encryption.rs" -Raw
$content = $content -replace '(?s)(let mut config_chacha = EncryptionConfig::default\(\);)\s+config_chacha\.algorithm = EncryptionAlgorithm::ChaCha20Poly1305;', 'let mut config_chacha = EncryptionConfig { algorithm: EncryptionAlgorithm::ChaCha20Poly1305, ..Default::default() };'
$content | Set-Content "guru/memory/encryption.rs"

# Fix guru/memory/pruning.rs - uninlined_format_args, float_cmp, manual_range_contains
Write-Host "Fixing guru/memory/pruning.rs..." -ForegroundColor Yellow
(Get-Content "guru/memory/pruning.rs") -replace 'format!\("hash_\{\}", id\)', 'format!("hash_{id}")' | Set-Content "guru/memory/pruning.rs"
(Get-Content "guru/memory/pruning.rs") -replace 'assert_eq!\(score\.user_importance, 0\.8\);', 'assert!((score.user_importance - 0.8).abs() < f32::EPSILON);' | Set-Content "guru/memory/pruning.rs"
(Get-Content "guru/memory/pruning.rs") -replace 'assert_eq!\(score\.frequency, 0\.5\);', 'assert!((score.frequency - 0.5).abs() < f32::EPSILON);' | Set-Content "guru/memory/pruning.rs"
(Get-Content "guru/memory/pruning.rs") -replace 'assert!\(prediction1 >= 0\.0 && prediction1 <= 1\.0\);', 'assert!((0.0..=1.0).contains(&prediction1));' | Set-Content "guru/memory/pruning.rs"
(Get-Content "guru/memory/pruning.rs") -replace 'assert!\(prediction2 >= 0\.0 && prediction2 <= 1\.0\);', 'assert!((0.0..=1.0).contains(&prediction2));' | Set-Content "guru/memory/pruning.rs"

# Fix guru/memory/temporal_graph.rs - uninlined_format_args, field_reassign_with_default
Write-Host "Fixing guru/memory/temporal_graph.rs..." -ForegroundColor Yellow
(Get-Content "guru/memory/temporal_graph.rs") -replace 'format!\("hash_\{\}", id\)', 'format!("hash_{id}")' | Set-Content "guru/memory/temporal_graph.rs"

# Fix guru/vision/ocr.rs - useless_conversion
Write-Host "Fixing guru/vision/ocr.rs..." -ForegroundColor Yellow
(Get-Content "guru/vision/ocr.rs") -replace '\.chain\(vec!\[200u8; 100\]\.into_iter\(\)\)', '.chain(vec![200u8; 100])' | Set-Content "guru/vision/ocr.rs"

# Fix guru/vision/property_tests.rs - len_zero, manual_range_contains, needless_range_loop
Write-Host "Fixing guru/vision/property_tests.rs..." -ForegroundColor Yellow
(Get-Content "guru/vision/property_tests.rs") -replace 'if privacy_enabled && frame_result\.face_detections\.len\(\) > 0', 'if privacy_enabled && !frame_result.face_detections.is_empty()' | Set-Content "guru/vision/property_tests.rs"
(Get-Content "guru/vision/property_tests.rs") -replace 'emotion_confidence >= 0\.0 && emotion_confidence <= 1\.0', '(0.0..=1.0).contains(&emotion_confidence)' | Set-Content "guru/vision/property_tests.rs"
(Get-Content "guru/vision/property_tests.rs") -replace 'iou_ab >= 0\.0 && iou_ab <= 1\.0', '(0.0..=1.0).contains(&iou_ab)' | Set-Content "guru/vision/property_tests.rs"
(Get-Content "guru/vision/property_tests.rs") -replace 'if orig_detection\.objects\.len\(\) > 0 && scaled_detection\.objects\.len\(\) > 0', 'if !orig_detection.objects.is_empty() && !scaled_detection.objects.is_empty()' | Set-Content "guru/vision/property_tests.rs"
(Get-Content "guru/vision/property_tests.rs") -replace 'size_ratio >= 0\.5 && size_ratio <= 2\.0', '(0.5..=2.0).contains(&size_ratio)' | Set-Content "guru/vision/property_tests.rs"

# Fix guru/agents/property_tests.rs - expect_fun_call
Write-Host "Fixing guru/agents/property_tests.rs..." -ForegroundColor Yellow
(Get-Content "guru/agents/property_tests.rs") -replace '\.await\.expect\(&format!\("Failed to register agent \{\}", i\)\);', '.await.unwrap_or_else(|_| panic!("Failed to register agent {}", i));' | Set-Content "guru/agents/property_tests.rs"

# Fix guru/avatar/emotion_controller.rs - field_reassign_with_default, manual_range_contains
Write-Host "Fixing guru/avatar/emotion_controller.rs..." -ForegroundColor Yellow
(Get-Content "guru/avatar/emotion_controller.rs") -replace 'assert!\(result >= 0\.0 && result <= 1\.0\);', 'assert!((0.0..=1.0).contains(&result));' | Set-Content "guru/avatar/emotion_controller.rs"

# Fix guru/avatar/lip_sync_controller.rs - float_cmp, field_reassign_with_default
Write-Host "Fixing guru/avatar/lip_sync_controller.rs..." -ForegroundColor Yellow
(Get-Content "guru/avatar/lip_sync_controller.rs") -replace 'assert_eq!\(controller\.blendshape_weights\.jaw_open, 0\.0\);', 'assert!((controller.blendshape_weights.jaw_open - 0.0).abs() < f32::EPSILON);' | Set-Content "guru/avatar/lip_sync_controller.rs"
(Get-Content "guru/avatar/lip_sync_controller.rs") -replace 'assert_eq!\(controller\.blendshape_weights\.jaw_open, 0\.5\);', 'assert!((controller.blendshape_weights.jaw_open - 0.5).abs() < f32::EPSILON);' | Set-Content "guru/avatar/lip_sync_controller.rs"
(Get-Content "guru/avatar/lip_sync_controller.rs") -replace 'assert_eq!\(controller\.blendshape_weights\.jaw_open, 1\.0\);', 'assert!((controller.blendshape_weights.jaw_open - 1.0).abs() < f32::EPSILON);' | Set-Content "guru/avatar/lip_sync_controller.rs"

# Fix guru/avatar/property_tests.rs - uninlined_format_args
Write-Host "Fixing guru/avatar/property_tests.rs..." -ForegroundColor Yellow
(Get-Content "guru/avatar/property_tests.rs") -replace 'return Err\(format!\("Concurrent operations took too long: \{:\?\} > \{:\?\}", total_time, max_expected_time\)\);', 'return Err(format!("Concurrent operations took too long: {total_time:?} > {max_expected_time:?}"));' | Set-Content "guru/avatar/property_tests.rs"

# Fix guru/avatar/mod.rs - assertions_on_constants, float_cmp
Write-Host "Fixing guru/avatar/mod.rs..." -ForegroundColor Yellow
(Get-Content "guru/avatar/mod.rs") -replace 'assert!\(true, "Avatar module should initialize correctly"\);', '// Avatar module initializes correctly' | Set-Content "guru/avatar/mod.rs"
(Get-Content "guru/avatar/mod.rs") -replace 'assert_eq!\(avatar_system\.lip_sync_controller\.get_blendshape_weights\(\)\.jaw_open, 0\.0\);', 'assert!((avatar_system.lip_sync_controller.get_blendshape_weights().jaw_open - 0.0).abs() < f32::EPSILON);' | Set-Content "guru/avatar/mod.rs"

# Fix guru/deployment/property_tests.rs - let_unit_value
Write-Host "Fixing guru/deployment/property_tests.rs..." -ForegroundColor Yellow
(Get-Content "guru/deployment/property_tests.rs") -replace 'let _rollback_result = self\.rollback_manager\.rollback_to_version\(&self\.installation_root, target_version\)\?;', 'self.rollback_manager.rollback_to_version(&self.installation_root, target_version)?;' | Set-Content "guru/deployment/property_tests.rs"

# Fix guru/lib.rs - len_zero
Write-Host "Fixing guru/lib.rs..." -ForegroundColor Yellow
(Get-Content "guru/lib.rs") -replace 'assert!\(VERSION\.len\(\) > 0, "VERSION should not be empty"\);', 'assert!(!VERSION.is_empty(), "VERSION should not be empty");' | Set-Content "guru/lib.rs"
(Get-Content "guru/lib.rs") -replace 'assert!\(BUILD_INFO\.len\(\) > 0, "BUILD_INFO should not be empty"\);', 'assert!(!BUILD_INFO.is_empty(), "BUILD_INFO should not be empty");' | Set-Content "guru/lib.rs"

Write-Host "All fixes applied! Running clippy to verify..." -ForegroundColor Green
cargo clippy --all-features --all-targets -- -D warnings
