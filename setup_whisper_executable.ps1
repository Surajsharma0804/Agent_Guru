# whisper.cpp Executable Setup Script
# Ensures correct whisper executable is available for GURU

Write-Host "=" -NoNewline -ForegroundColor Cyan
Write-Host ("=" * 69) -ForegroundColor Cyan
Write-Host "whisper.cpp Executable Setup" -ForegroundColor Cyan
Write-Host "=" -NoNewline -ForegroundColor Cyan
Write-Host ("=" * 69) -ForegroundColor Cyan
Write-Host ""

$WHISPER_DIR = "C:\GURU\engines\whisper"

# Check if directory exists
if (-not (Test-Path $WHISPER_DIR)) {
    Write-Host "ERROR: whisper directory not found: $WHISPER_DIR" -ForegroundColor Red
    Write-Host "Please install whisper.cpp first" -ForegroundColor Yellow
    exit 1
}

Write-Host "Scanning for whisper executables..." -ForegroundColor Yellow
Write-Host ""

# Define all possible executable locations
$executables = @(
    @{
        Path = "$WHISPER_DIR\whisper.exe"
        Name = "whisper.exe"
        Priority = 1
        Recommended = $true
    },
    @{
        Path = "$WHISPER_DIR\Release\whisper-cli.exe"
        Name = "Release\whisper-cli.exe"
        Priority = 2
        Recommended = $true
    },
    @{
        Path = "$WHISPER_DIR\whisper-cli.exe"
        Name = "whisper-cli.exe"
        Priority = 3
        Recommended = $true
    },
    @{
        Path = "$WHISPER_DIR\main.exe"
        Name = "main.exe"
        Priority = 4
        Recommended = $false
    }
)

# Find all existing executables
$found = @()
foreach ($exe in $executables) {
    if (Test-Path $exe.Path) {
        $exe.Exists = $true
        $found += $exe
        
        $icon = if ($exe.Recommended) { "✓" } else { "⚠" }
        $color = if ($exe.Recommended) { "Green" } else { "Yellow" }
        
        Write-Host "$icon Found: $($exe.Name)" -ForegroundColor $color
        Write-Host "  Path: $($exe.Path)" -ForegroundColor Gray
    }
}

Write-Host ""

if ($found.Count -eq 0) {
    Write-Host "ERROR: No whisper executables found" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please install whisper.cpp:" -ForegroundColor Yellow
    Write-Host "  1. Download from: https://github.com/ggerganov/whisper.cpp/releases" -ForegroundColor Gray
    Write-Host "  2. Extract to: $WHISPER_DIR" -ForegroundColor Gray
    exit 1
}

# Sort by priority
$found = $found | Sort-Object -Property Priority

# Check if whisper.exe exists
$whisperExe = "$WHISPER_DIR\whisper.exe"
$whisperExeExists = Test-Path $whisperExe

if ($whisperExeExists) {
    Write-Host "✓ whisper.exe is available" -ForegroundColor Green
    Write-Host "  GURU will use: $whisperExe" -ForegroundColor Gray
    Write-Host ""
    Write-Host "Setup complete!" -ForegroundColor Green
} else {
    Write-Host "⚠ whisper.exe not found" -ForegroundColor Yellow
    Write-Host ""
    
    # Find best alternative
    $best = $found[0]
    
    Write-Host "Recommended action:" -ForegroundColor Cyan
    Write-Host "  Copy $($best.Name) to whisper.exe" -ForegroundColor White
    Write-Host ""
    Write-Host "Command:" -ForegroundColor Cyan
    Write-Host "  Copy-Item `"$($best.Path)`" `"$whisperExe`"" -ForegroundColor Gray
    Write-Host ""
    
    $response = Read-Host "Do you want to create whisper.exe now? (Y/N)"
    
    if ($response -eq "Y" -or $response -eq "y") {
        try {
            Copy-Item $best.Path $whisperExe -Force
            Write-Host ""
            Write-Host "✓ Created: whisper.exe" -ForegroundColor Green
            Write-Host "  Source: $($best.Name)" -ForegroundColor Gray
            Write-Host "  Target: whisper.exe" -ForegroundColor Gray
            Write-Host ""
            Write-Host "Setup complete!" -ForegroundColor Green
        } catch {
            Write-Host ""
            Write-Host "ERROR: Failed to create whisper.exe" -ForegroundColor Red
            Write-Host "  $($_.Exception.Message)" -ForegroundColor Yellow
            exit 1
        }
    } else {
        Write-Host ""
        Write-Host "Setup skipped" -ForegroundColor Yellow
        Write-Host "GURU will automatically find and use: $($best.Name)" -ForegroundColor Gray
    }
}

Write-Host ""
Write-Host "=" -NoNewline -ForegroundColor Cyan
Write-Host ("=" * 69) -ForegroundColor Cyan
Write-Host "Next Steps" -ForegroundColor Cyan
Write-Host "=" -NoNewline -ForegroundColor Cyan
Write-Host ("=" * 69) -ForegroundColor Cyan
Write-Host ""

Write-Host "1. Verify installation:" -ForegroundColor White
Write-Host "   python desktop-agent/check_system_ready.py" -ForegroundColor Gray
Write-Host ""

Write-Host "2. Test whisper.cpp:" -ForegroundColor White
Write-Host "   python desktop-agent/test_whisper_integration.py" -ForegroundColor Gray
Write-Host ""

Write-Host "3. Launch GURU:" -ForegroundColor White
Write-Host "   python desktop-agent/launch_guru_complete.py" -ForegroundColor Gray
Write-Host ""

Write-Host "Press any key to exit..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
