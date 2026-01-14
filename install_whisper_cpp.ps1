# whisper.cpp Installation Script for GURU
# Production-Grade Automated Setup
# Run as Administrator

Write-Host "=" -NoNewline -ForegroundColor Cyan
Write-Host ("=" * 69) -ForegroundColor Cyan
Write-Host "GURU whisper.cpp Installation" -ForegroundColor Cyan
Write-Host "=" -NoNewline -ForegroundColor Cyan
Write-Host ("=" * 69) -ForegroundColor Cyan
Write-Host ""

# Configuration
$GURU_ROOT = "C:\GURU"
$WHISPER_DIR = "$GURU_ROOT\engines\whisper"
$MODELS_DIR = "$WHISPER_DIR\models"
$WHISPER_VERSION = "1.5.4"  # Latest stable version
$MODEL_NAME = "ggml-large-v3.bin"

# Step 1: Create Directory Structure
Write-Host "[1/5] Creating directory structure..." -ForegroundColor Yellow

if (-not (Test-Path $GURU_ROOT)) {
    New-Item -ItemType Directory -Path $GURU_ROOT -Force | Out-Null
    Write-Host "  Created: $GURU_ROOT" -ForegroundColor Green
}

if (-not (Test-Path $WHISPER_DIR)) {
    New-Item -ItemType Directory -Path $WHISPER_DIR -Force | Out-Null
    Write-Host "  Created: $WHISPER_DIR" -ForegroundColor Green
}

if (-not (Test-Path $MODELS_DIR)) {
    New-Item -ItemType Directory -Path $MODELS_DIR -Force | Out-Null
    Write-Host "  Created: $MODELS_DIR" -ForegroundColor Green
}

Write-Host "  Directory structure ready" -ForegroundColor Green
Write-Host ""

# Step 2: Download whisper.cpp
Write-Host "[2/5] Downloading whisper.cpp..." -ForegroundColor Yellow

$WHISPER_URL = "https://github.com/ggerganov/whisper.cpp/releases/download/v$WHISPER_VERSION/whisper-bin-x64-Win64.zip"
$WHISPER_ZIP = "$env:TEMP\whisper-cpp.zip"

try {
    Write-Host "  Downloading from GitHub releases..." -ForegroundColor Gray
    Invoke-WebRequest -Uri $WHISPER_URL -OutFile $WHISPER_ZIP -UseBasicParsing
    Write-Host "  Downloaded: whisper-cpp.zip" -ForegroundColor Green
} catch {
    Write-Host "  ERROR: Failed to download whisper.cpp" -ForegroundColor Red
    Write-Host "  Please download manually from:" -ForegroundColor Yellow
    Write-Host "  https://github.com/ggerganov/whisper.cpp/releases" -ForegroundColor Yellow
    Write-Host "  Extract to: $WHISPER_DIR" -ForegroundColor Yellow
    exit 1
}

Write-Host ""

# Step 3: Extract whisper.cpp
Write-Host "[3/5] Extracting whisper.cpp..." -ForegroundColor Yellow

try {
    Expand-Archive -Path $WHISPER_ZIP -DestinationPath $WHISPER_DIR -Force
    Write-Host "  Extracted to: $WHISPER_DIR" -ForegroundColor Green
    
    # Clean up
    Remove-Item $WHISPER_ZIP -Force
    Write-Host "  Cleaned up temporary files" -ForegroundColor Green
} catch {
    Write-Host "  ERROR: Failed to extract whisper.cpp" -ForegroundColor Red
    exit 1
}

Write-Host ""

# Step 4: Download Model
Write-Host "[4/5] Downloading whisper model (large-v3)..." -ForegroundColor Yellow
Write-Host "  This is a large file (~1.5 GB), please wait..." -ForegroundColor Gray

$MODEL_URL = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/$MODEL_NAME"
$MODEL_PATH = "$MODELS_DIR\$MODEL_NAME"

if (Test-Path $MODEL_PATH) {
    $fileSize = (Get-Item $MODEL_PATH).Length / 1MB
    if ($fileSize -gt 1400 -and $fileSize -lt 1700) {
        Write-Host "  Model already exists and is valid ($([math]::Round($fileSize, 0)) MB)" -ForegroundColor Green
    } else {
        Write-Host "  Existing model file is invalid, re-downloading..." -ForegroundColor Yellow
        Remove-Item $MODEL_PATH -Force
    }
}

if (-not (Test-Path $MODEL_PATH)) {
    try {
        Write-Host "  Downloading from Hugging Face..." -ForegroundColor Gray
        
        # Use curl for better progress display
        $curlPath = "C:\Windows\System32\curl.exe"
        if (Test-Path $curlPath) {
            & $curlPath -L -o $MODEL_PATH $MODEL_URL --progress-bar
        } else {
            # Fallback to Invoke-WebRequest
            Invoke-WebRequest -Uri $MODEL_URL -OutFile $MODEL_PATH -UseBasicParsing
        }
        
        $fileSize = (Get-Item $MODEL_PATH).Length / 1MB
        Write-Host "  Downloaded: $MODEL_NAME ($([math]::Round($fileSize, 0)) MB)" -ForegroundColor Green
    } catch {
        Write-Host "  ERROR: Failed to download model" -ForegroundColor Red
        Write-Host "  Please download manually from:" -ForegroundColor Yellow
        Write-Host "  $MODEL_URL" -ForegroundColor Yellow
        Write-Host "  Save to: $MODEL_PATH" -ForegroundColor Yellow
        exit 1
    }
}

Write-Host ""

# Step 5: Verify Installation
Write-Host "[5/5] Verifying installation..." -ForegroundColor Yellow

# Check for whisper executables (multiple possible locations)
$possibleExes = @(
    "$WHISPER_DIR\whisper.exe",
    "$WHISPER_DIR\Release\whisper-cli.exe",
    "$WHISPER_DIR\whisper-cli.exe",
    "$WHISPER_DIR\main.exe"
)

$exeFound = $false
$exePath = ""

foreach ($exe in $possibleExes) {
    if (Test-Path $exe) {
        $exeFound = $true
        $exePath = $exe
        Write-Host "  Found: $(Split-Path $exe -Leaf) at $(Split-Path $exe -Parent)" -ForegroundColor Green
        break
    }
}

if (-not $exeFound) {
    Write-Host "  ERROR: No whisper executable found" -ForegroundColor Red
    Write-Host "  Tried: whisper.exe, Release/whisper-cli.exe, whisper-cli.exe, main.exe" -ForegroundColor Yellow
    exit 1
}

# Create whisper.exe symlink if using whisper-cli.exe
if ($exePath -like "*whisper-cli.exe" -and -not (Test-Path "$WHISPER_DIR\whisper.exe")) {
    Copy-Item $exePath "$WHISPER_DIR\whisper.exe" -Force
    Write-Host "  Created: whisper.exe (copy of whisper-cli.exe)" -ForegroundColor Green
    $exePath = "$WHISPER_DIR\whisper.exe"
}

# Test execution
try {
    $output = & $exePath --help 2>&1
    if ($LASTEXITCODE -eq 0 -or $output -match "usage:") {
        Write-Host "  whisper.exe execution: OK" -ForegroundColor Green
    } else {
        Write-Host "  WARNING: whisper.exe may not work correctly" -ForegroundColor Yellow
    }
} catch {
    Write-Host "  WARNING: Could not test whisper.exe execution" -ForegroundColor Yellow
}

# Check model
if (Test-Path $MODEL_PATH) {
    $fileSize = (Get-Item $MODEL_PATH).Length / 1MB
    Write-Host "  Model file: OK ($([math]::Round($fileSize, 0)) MB)" -ForegroundColor Green
} else {
    Write-Host "  ERROR: Model file not found" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "=" -NoNewline -ForegroundColor Cyan
Write-Host ("=" * 69) -ForegroundColor Cyan
Write-Host "Installation Complete!" -ForegroundColor Green
Write-Host "=" -NoNewline -ForegroundColor Cyan
Write-Host ("=" * 69) -ForegroundColor Cyan
Write-Host ""

Write-Host "Installation Summary:" -ForegroundColor Cyan
Write-Host "  whisper.cpp: $exePath" -ForegroundColor White
Write-Host "  Model: $MODEL_PATH" -ForegroundColor White
Write-Host "  Model Size: $([math]::Round((Get-Item $MODEL_PATH).Length / 1MB, 0)) MB" -ForegroundColor White
Write-Host ""

Write-Host "Next Steps:" -ForegroundColor Cyan
Write-Host "  1. Test installation:" -ForegroundColor White
Write-Host "     python desktop-agent/test_whisper_integration.py" -ForegroundColor Gray
Write-Host ""
Write-Host "  2. Configure GURU:" -ForegroundColor White
Write-Host "     Configuration will be created automatically" -ForegroundColor Gray
Write-Host ""
Write-Host "  3. Start GURU:" -ForegroundColor White
Write-Host "     python desktop-agent/launch_guru_complete.py" -ForegroundColor Gray
Write-Host ""

Write-Host "Documentation:" -ForegroundColor Cyan
Write-Host "  See WHISPER_CPP_SETUP.md for detailed information" -ForegroundColor White
Write-Host ""

Write-Host "Press any key to exit..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
