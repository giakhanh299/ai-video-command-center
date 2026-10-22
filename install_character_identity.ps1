$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "=== Character ID stack: Config 2 + Wuby ===" -ForegroundColor Cyan
Write-Host "1/3 Installing WeSpeaker (speaker identity / diarization)..."
python -m pip install -U "git+https://github.com/wenet-e2e/wespeaker.git"

Write-Host "2/3 Preparing Light-ASD (only for ambiguous dialogue)..."
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "Git is required. Install Git for Windows, then run this script again."
}
New-Item -ItemType Directory -Force -Path "external" | Out-Null
if (-not (Test-Path "external\Light-ASD\Columbia_test.py")) {
    git clone --depth 1 https://github.com/Junhua-Liao/Light-ASD.git "external\Light-ASD"
} else {
    Write-Host "Light-ASD already exists; keeping the current checkout."
}

# Do not replace the user's CUDA/PyTorch build. Install only the Python-side helpers
# that Light-ASD commonly needs and that are safe to layer onto the current env.
# Keep the media/TTS environment on NumPy 1.x. New OpenCV releases pull NumPy 2.x,
# which breaks F5-TTS on Python 3.10.
python -m pip install -U "numpy==1.26.4" "opencv-python==4.10.0.84" scenedetect python_speech_features scikit-learn scipy tqdm
if (Test-Path "external\Light-ASD\requirements.txt") {
    Write-Host "Light-ASD has its own requirements.txt; installing without forcing torch upgrades..."
    $tmpReq = Join-Path $env:TEMP "light_asd_requirements_no_torch.txt"
    Get-Content "external\Light-ASD\requirements.txt" |
        Where-Object { $_ -notmatch '^\s*(torch|torchvision|torchaudio)(\s|=|<|>|$)' } |
        Set-Content -Encoding UTF8 $tmpReq
    python -m pip install -r $tmpReq
}

Write-Host "3/3 Running doctor..."
python tools\check_character_identity.py

Write-Host ""
Write-Host "Done. Config 2 + Wuby now use Character ID first." -ForegroundColor Green
Write-Host "F0/pitch does NOT decide who the character is and no pitch shift is applied."
