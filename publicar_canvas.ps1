<#
  publicar_canvas.ps1 · Carga los archivos momento-N.html en las páginas "Momento N" de tu curso de Canvas.

  Uso (en la carpeta donde están los momento-N.html):
      powershell -ExecutionPolicy Bypass -File .\publicar_canvas.ps1 -Curso https://indoamerica.instructure.com/courses/12345

  Opciones:
      -SoloRevisar        Muestra qué páginas se actualizarían, sin cambiar nada.
      -Restaurar <carpeta> Vuelve a poner lo que había antes (usa una carpeta "respaldo_..." creada por este script).

  El token se escribe en esta ventana (no se muestra ni se guarda). Créalo en Canvas:
  Cuenta -> Configuraciones -> + Nuevo token de acceso (expiración: mañana) y elimínalo al terminar.
#>
param(
    [Parameter(Mandatory = $true)][string]$Curso,
    [string]$Carpeta = '',
    [switch]$SoloRevisar,
    [string]$Restaurar = '',
    [switch]$Confirmar,          # solo para pruebas automáticas: no pregunta
    [string]$ApiBase = ''        # solo para pruebas con un Canvas simulado
)
$ErrorActionPreference = 'Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
if (-not $Carpeta) { $Carpeta = (Get-Location).Path }

function Salir($msg) { Write-Host "`n$msg" -ForegroundColor Red; exit 1 }
function Texto($html) {
    $t = [regex]::Replace([string]$html, '<[^>]+>', ' ')
    $t = [System.Net.WebUtility]::HtmlDecode($t)
    return ([regex]::Replace($t, '\s+', ' ')).Trim()
}
function EsMomento($texto, $n) { return [regex]::IsMatch([string]$texto, "Momento\s*0?$n(?!\d)", 'IgnoreCase') }

# ---------- curso ----------
# Solo letras, números, puntos y guiones en el servidor (sin usuario, contraseña, puerto, "?" ni "#"):
# el token solo puede viajar a un servidor *.instructure.com legítimo.
$m = [regex]::Match($Curso.Trim(), '^https://([A-Za-z0-9.-]+)/courses/(\d+)(?:[/?#]\S*)?$')
if (-not $m.Success) { Salir 'La URL del curso debe verse así: https://indoamerica.instructure.com/courses/12345' }
$HostCurso = $m.Groups[1].Value.ToLower(); $Id = $m.Groups[2].Value
if (-not $ApiBase -and $HostCurso -notmatch '^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.instructure\.com$') { Salir "El servidor $HostCurso no es de Canvas (instructure.com)." }
$Base = if ($ApiBase) { $ApiBase.TrimEnd('/') } else { "https://$HostCurso" }

# ---------- token ----------
if ($env:CANVAS_TOKEN) { $Token = $env:CANVAS_TOKEN }
else {
    $seguro = Read-Host 'Pega tu token de Canvas (no se mostrará)' -AsSecureString
    $Token = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($seguro))
}
if (-not $Token -or $Token.Trim().Length -lt 10) { Salir 'Falta el token.' }
$Cab = @{ Authorization = "Bearer $($Token.Trim())"; Accept = 'application/json' }

function Api($metodo, $ruta, $cuerpo = $null) {
    $uri = if ($ruta -match '^https?://') { $ruta } else { "$Base/api/v1$ruta" }
    try {
        if ($cuerpo -ne $null) {
            $json = [Text.Encoding]::UTF8.GetBytes(($cuerpo | ConvertTo-Json -Depth 5 -Compress))
            return Invoke-WebRequest -Uri $uri -Method $metodo -Headers $Cab -Body $json -ContentType 'application/json; charset=utf-8' -UseBasicParsing
        }
        return Invoke-WebRequest -Uri $uri -Method $metodo -Headers $Cab -UseBasicParsing
    } catch {
        $code = 0; try { $code = [int]$_.Exception.Response.StatusCode } catch {}
        switch ($code) {
            401 { Salir 'Canvas rechazó el token: está vencido, fue eliminado o está mal copiado.' }
            403 { Salir 'Tu usuario no tiene permiso para esto en el curso (¿eres docente del curso?).' }
            404 { throw "No encontrado: $ruta" }
            default { throw "Canvas respondió con error $code en $ruta" }
        }
    }
}
function Json($r) { return [Text.Encoding]::UTF8.GetString($r.RawContentStream.ToArray()) | ConvertFrom-Json }
function GetTodo($ruta) {
    $out = @(); $url = $ruta + $(if ($ruta.Contains('?')) { '&' } else { '?' }) + 'per_page=100'
    for ($i = 0; $i -lt 50 -and $url; $i++) {
        $r = Api 'GET' $url
        $out += @(Json $r)
        $url = $null
        $link = [string]$r.Headers['Link']
        $sig = [regex]::Match($link, '<([^>]+)>;\s*rel="next"')
        if ($sig.Success) { $url = $sig.Groups[1].Value }
    }
    return $out
}
function Pagina($slug) { return Json (Api 'GET' "/courses/$Id/pages/$slug") }
function Poner($slug, $html) { return Api 'PUT' "/courses/$Id/pages/$slug" @{ wiki_page = @{ body = [string]$html } } }
# texto plano (Get-Content -Raw agrega propiedades que ConvertTo-Json convierte en objeto)
function Leer($ruta) { return [string][IO.File]::ReadAllText($ruta, [Text.Encoding]::UTF8) }

$info = Json (Api 'GET' "/courses/$Id")
Write-Host "`nCurso: $($info.name) (ID $Id)" -ForegroundColor Cyan

# ---------- restaurar ----------
if ($Restaurar) {
    $mapa = Leer (Join-Path $Restaurar 'paginas.json') | ConvertFrom-Json
    foreach ($p in $mapa) {
        $html = Leer (Join-Path $Restaurar "momento-$($p.n)-anterior.html")
        Poner $p.slug $html | Out-Null
        Write-Host "  Momento $($p.n): restaurada ($($p.slug))" -ForegroundColor Green
    }
    $Token = $null; exit 0
}

# ---------- archivos ----------
$archivos = Get-ChildItem -Path $Carpeta -Filter 'momento-*.html' | Where-Object { $_.Name -match '^momento-(\d+)\.html$' } |
    Sort-Object { [int]([regex]::Match($_.Name, '\d+').Value) }
if (-not $archivos) { Salir "No hay archivos momento-N.html en $Carpeta" }
$nums = @($archivos | ForEach-Object { [int]([regex]::Match($_.Name, '\d+').Value) })

# ---------- localizar páginas: inicio > módulo > búsqueda ----------
$cand = @{}; foreach ($n in $nums) { $cand[$n] = New-Object System.Collections.ArrayList }
$slugInicio = 'inicio'
try { $front = Json (Api 'GET' "/courses/$Id/front_page") } catch { $front = $null }
if ($front) {
    $slugInicio = $front.url
    foreach ($a in [regex]::Matches([string]$front.body, '<a\b([^>]*)>(.*?)</a>', 'Singleline')) {
        $h = [regex]::Match($a.Groups[1].Value, "href=""[^""]*/courses/$Id/pages/([^""/?#]+)")
        if (-not $h.Success) { continue }
        $alts = ([regex]::Matches($a.Value, '(?:alt|title|aria-label)="([^"]*)"') | ForEach-Object { $_.Groups[1].Value }) -join ' '
        $txt = (Texto $a.Groups[2].Value) + ' ' + $alts
        foreach ($n in $nums) {
            if ((EsMomento $txt $n) -or $h.Groups[1].Value -match "^momento-?0?$n(-\d+)?$") { [void]$cand[$n].Add(@($h.Groups[1].Value, 'página de inicio')) }
        }
    }
}
foreach ($mod in (GetTodo "/courses/$Id/modules?include[]=items")) {
    $pags = @($mod.items | Where-Object { $_.type -eq 'Page' -and $_.page_url })
    foreach ($n in $nums) {
        $por = @($pags | Where-Object { EsMomento $_.title $n })
        if ($por) { foreach ($it in $por) { [void]$cand[$n].Add(@($it.page_url, 'módulo')) } }
        elseif ($pags -and (EsMomento $mod.name $n)) { [void]$cand[$n].Add(@($pags[0].page_url, 'módulo')) }
    }
}
foreach ($pg in (GetTodo "/courses/$Id/pages?search_term=momento")) {
    foreach ($n in $nums) { if (EsMomento $pg.title $n) { [void]$cand[$n].Add(@($pg.url, 'búsqueda')) } }
}

$plan = @()
foreach ($f in $archivos) {
    $n = [int]([regex]::Match($f.Name, '\d+').Value)
    $html = Leer $f.FullName
    if (-not (EsMomento (Texto $html) $n) -or -not ((Texto $html) -match "Momento $n\s*:")) {
        Write-Host "  Momento ${n}: el archivo no dice 'Momento ${n}:'; se omite." -ForegroundColor Yellow; continue
    }
    if (-not $cand[$n].Count) { Write-Host "  Momento ${n}: no se encontró su página en el curso; se omite." -ForegroundColor Yellow; continue }
    $slug = $cand[$n][0][0]; $fuente = $cand[$n][0][1]
    $pg = Pagina $slug
    # enlaces del curso correcto y botón "Inicio del curso" a la página de inicio real
    $html = [regex]::Replace($html, '/courses/\d+', "/courses/$Id")
    $html = [regex]::Replace($html, "(/courses/$Id/pages/)[^""]+(""[^>]*>\s*Inicio del curso)", "`${1}$slugInicio`$2")
    $html = [regex]::Replace($html, "(href=""[^""]*/courses/$Id/pages/)[^""]+(""[^>]*data-api-endpoint=""[^""]*/courses/$Id/pages/)[^""]+(""[^>]*>\s*Inicio del curso)", "`${1}$slugInicio`${2}$slugInicio`$3")
    $plan += [pscustomobject]@{ n = $n; archivo = $f.Name; slug = $pg.url; titulo = $pg.title; fuente = $fuente; html = $html; antes = [string]$pg.body }
}
if (-not $plan) { Salir 'No hay nada que publicar.' }

Write-Host "`nSe actualizará SOLO el contenido de estas páginas:" -ForegroundColor Cyan
$plan | Format-Table @{l='Momento';e={$_.n}}, @{l='Archivo';e={$_.archivo}}, @{l='Página en Canvas';e={$_.titulo}}, @{l='Dirección';e={$_.slug}}, @{l='Encontrada por';e={$_.fuente}} -AutoSize | Out-Host
if ($SoloRevisar) { Write-Host 'Modo revisión: no se cambió nada.'; $Token = $null; exit 0 }
if (-not $Confirmar) {
    $r = Read-Host "Escribe PUBLICAR para continuar (cualquier otra cosa cancela)"
    if ($r -ne 'PUBLICAR') { Write-Host 'Cancelado. No se cambió nada.'; $Token = $null; exit 0 }
}

# ---------- respaldo, publicación y verificación ----------
$resp = Join-Path $Carpeta ("respaldo_" + (Get-Date -Format 'yyyyMMdd_HHmmss'))
New-Item -ItemType Directory -Path $resp | Out-Null
foreach ($p in $plan) { [IO.File]::WriteAllText((Join-Path $resp "momento-$($p.n)-anterior.html"), $p.antes, (New-Object Text.UTF8Encoding $false)) }
($plan | Select-Object n, slug, titulo | ConvertTo-Json) | Out-File (Join-Path $resp 'paginas.json') -Encoding utf8
Write-Host "Respaldo guardado en $resp`n"

$errores = 0
foreach ($p in $plan) {
    try {
        Poner $p.slug $p.html | Out-Null
        $despues = Pagina $p.slug
        $t = Texto $despues.body
        if (($t -match "Momento $($p.n)\s*:") -and ($t -notmatch 'Copiar y pegar') -and ($t -eq (Texto $p.html))) {
            Write-Host "  Momento $($p.n): publicada y verificada  ->  https://$HostCurso/courses/$Id/pages/$($p.slug)" -ForegroundColor Green
        } else {
            Write-Host "  Momento $($p.n): publicada, pero el contenido en Canvas difiere; revísala." -ForegroundColor Yellow; $errores++
        }
    } catch {
        Write-Host "  Momento $($p.n): NO se publicó ($($_.Exception.Message))" -ForegroundColor Red; $errores++
    }
}
$Token = $null; $Cab = $null
Write-Host "`nListo. Para deshacer: .\publicar_canvas.ps1 -Curso $Curso -Restaurar `"$resp`""
Write-Host 'Recuerda eliminar el token en Canvas: Cuenta -> Configuraciones -> Integraciones aprobadas.'
exit $errores
