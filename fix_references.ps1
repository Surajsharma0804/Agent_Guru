# Fix all missing & references in platform/property_tests.rs

$file = "guru/platform/property_tests.rs"
$content = Get-Content $file -Raw

# Fix inject_input_event calls
$content = $content -replace 'bridge\.inject_input_event\(([a-z_]+)\)', 'bridge.inject_input_event(&$1)'

# Fix control_window calls with actions (not already fixed)
$content = $content -replace 'bridge\.control_window\(window_id, (Windows|MacOS|Linux)WindowAction::', 'bridge.control_window(window_id, &$1WindowAction::'

# Fix modify_system_setting calls (not already fixed)
$content = $content -replace 'bridge\.modify_system_setting\((setting|invalid_setting)\)', 'bridge.modify_system_setting(&$1)'

# Save the file
Set-Content -Path $file -Value $content -NoNewline

Write-Host "Fixed all reference issues in $file"
