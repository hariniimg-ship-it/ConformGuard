$ErrorActionPreference = 'Stop'
python -m conformguard.cli --combined --mock --output-dir artifacts
Get-Content artifacts/report.md
