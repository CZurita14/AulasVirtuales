# Arranca "Sílabo -> Aula virtual" en http://localhost:8770
# Uso:  .\iniciar.ps1            (solo este equipo)
#       .\iniciar.ps1 -Red       (accesible desde la red, p. ej. servidor de la UTI)
param([switch]$Red, [int]$Puerto = 8770)
Set-Location $PSScriptRoot
if (-not (Test-Path .venv)) {
    python -m venv .venv
    .\.venv\Scripts\python -m pip install -q -r requirements.txt
}
$hostIp = if ($Red) { '0.0.0.0' } else { '127.0.0.1' }
Write-Host "Abriendo http://localhost:$Puerto ..."
.\.venv\Scripts\python -m uvicorn app:app --host $hostIp --port $Puerto
