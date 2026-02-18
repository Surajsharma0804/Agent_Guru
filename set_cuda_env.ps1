# Set CUDA_VISIBLE_DEVICES to enable GPU
# Run this script if GPU is not detected

$env:CUDA_VISIBLE_DEVICES = '0'

# Set permanently for user
[System.Environment]::SetEnvironmentVariable('CUDA_VISIBLE_DEVICES', '0', [System.EnvironmentVariableTarget]::User)

Write-Host "✓ CUDA_VISIBLE_DEVICES set to 0 (GPU enabled)"
Write-Host "✓ Environment variable saved permanently for user"

# Verify
python -c "import torch; print('CUDA available:', torch.cuda.is_available()); print('GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'N/A')"
