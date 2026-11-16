# Vigilante del sistema y de su dirección pública fija (Tailscale Funnel, servicio "funnel" del docker-compose).
# Lo ejecuta la tarea programada "AulasVirtuales - vigilar puente" cada 5 minutos y al iniciar sesión.
# Si la app o el puente no responden, los vuelve a levantar. La dirección NO cambia al reiniciar
# (la identidad de Tailscale vive en el volumen tailscale_estado).
$ErrorActionPreference = 'Continue'
$raiz = Split-Path -Parent $PSScriptRoot
$datos = Join-Path $raiz 'datos'
New-Item -ItemType Directory -Force $datos | Out-Null
$log = Join-Path $datos 'vigilancia.log'
$puente = 'aulasvirtuales-silabos-funnel-1'

function Anotar($m) { Add-Content -Path $log -Encoding utf8 -Value ("{0}  {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $m) }
function Codigo($url) {
    $c = & curl.exe --ssl-no-revoke -s -o NUL -m 20 -w '%{http_code}' $url 2>$null
    if ($c) { return "$c" } else { return '000' }
}
function Levantar { Push-Location $raiz; docker compose --profile publico up -d *> $null; Pop-Location }

# 0) Docker disponible
docker info *> $null
if ($LASTEXITCODE -ne 0) { Anotar 'Docker no responde (¿Docker Desktop cerrado?). No se puede vigilar.'; exit 1 }

# 1) La app local
if ((Codigo 'http://127.0.0.1:8770/') -ne '200') {
    Anotar 'La app no responde: se levanta'
    Levantar; Start-Sleep 20
    Anotar ("App tras levantar: {0}" -f (Codigo 'http://127.0.0.1:8770/'))
}

# 2) El puente: contenedor en marcha y la dirección pública responde
if ((docker inspect $puente --format '{{.State.Status}}' 2>$null) -ne 'running') {
    Anotar 'El puente no está en marcha: se levanta'
    Levantar; Start-Sleep 20
}
$dns = (docker exec $puente tailscale status --json 2>$null | ConvertFrom-Json).Self.DNSName
if (-not $dns) { Anotar 'El puente no tiene sesión en Tailscale (revisar: docker logs aulasvirtuales-silabos-funnel-1)'; exit 1 }
$url = 'https://' + $dns.TrimEnd('.') + '/'
$ok = $false
foreach ($i in 1..3) { if ((Codigo $url) -eq '200') { $ok = $true; break }; Start-Sleep 15 }
if (-not $ok) {
    Anotar "La dirección fija no responde: se reinicia el puente"
    docker restart $puente *> $null
    Start-Sleep 45
    Anotar ("Dirección fija tras reiniciar: {0}" -f (Codigo $url))
}
