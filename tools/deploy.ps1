# Kopierer src\ til CIRCUITPY og starter kortet på nytt, siden auto-reload er av.
# src\ er originalen, CIRCUITPY er bare en kopi.
$ErrorActionPreference = 'Stop'

$repo = Split-Path -Parent $PSScriptRoot
$src = Join-Path $repo 'src'

$volume = Get-Volume | Where-Object FileSystemLabel -eq 'CIRCUITPY' | Select-Object -First 1
if (-not $volume) { throw 'Fant ikke CIRCUITPY. Er kortet koblet til?' }
$target = "$($volume.DriveLetter):\"

# code.py sist, siden kortet starter på nytt ved hver endring og trenger resten først.
Get-ChildItem $src -Exclude 'code.py', '__pycache__' | Copy-Item -Destination $target -Recurse -Force
Copy-Item (Join-Path $src 'code.py') $target -Force
Write-Output "Kopiert til $target"
python -I (Join-Path $PSScriptRoot 'restart.py')
