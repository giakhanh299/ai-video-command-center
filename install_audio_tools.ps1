$ErrorActionPreference = "Stop"
Write-Host "Installing optional audio tools for Config 3..."
python -m pip install -U demucs soundfile numpy scipy
Write-Host "Done. Demucs model checkpoint may be downloaded automatically on first use."
