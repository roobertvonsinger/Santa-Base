<#
Registra el protocolo santabase-stealth:// en Windows para ESTE usuario (HKCU, no requiere admin).
Despues de correr esto UNA VEZ, el boton "Abrir en Stealth Browser" de la boveda de Santa Base
(https://2puty.tech/santabase) lanza este navegador directo, pre-llenado con el CURP y el estado
del hit.

Uso:
  powershell -ExecutionPolicy Bypass -File register_protocol.ps1

Si el operador usa el .exe compilado en vez del source de Python, cambiar $target abajo por la
ruta al StealthMobileBrowser.exe (debe estar compilado desde ESTE launch_mobile_browser.py para
soportar el argumento santabase-stealth://, ver README.md).
#>

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$launcher = Join-Path $scriptDir "launch_mobile_browser.py"

if (-not (Test-Path $launcher)) {
    Write-Error "No se encontro launch_mobile_browser.py junto a este script. Corre esto desde scripts\stealth_browser\."
    exit 1
}

# Busca pythonw.exe (sin consola) en el PATH; si no esta, usa python.exe normal.
$pythonw = (Get-Command pythonw.exe -ErrorAction SilentlyContinue).Source
if (-not $pythonw) {
    $pythonw = (Get-Command python.exe -ErrorAction SilentlyContinue).Source
}
if (-not $pythonw) {
    Write-Error "No se encontro python.exe/pythonw.exe en el PATH. Instala Python o edita este script con la ruta directa."
    exit 1
}

# Para usar el .exe compilado en vez del source, comenta la linea de $target de arriba y usa:
# $target = '"C:\ruta\a\StealthMobileBrowser.exe" "%1"'
$target = "`"$pythonw`" `"$launcher`" `"%1`""

$regPath = "HKCU:\Software\Classes\santabase-stealth"
New-Item -Path $regPath -Force | Out-Null
Set-ItemProperty -Path $regPath -Name "(Default)" -Value "URL:SantaBase Stealth Protocol"
Set-ItemProperty -Path $regPath -Name "URL Protocol" -Value ""

$cmdPath = "$regPath\shell\open\command"
New-Item -Path $cmdPath -Force | Out-Null
Set-ItemProperty -Path $cmdPath -Name "(Default)" -Value $target

Write-Output "Protocolo santabase-stealth:// registrado para este usuario."
Write-Output "Comando: $target"
Write-Output ""
Write-Output "Prueba con:"
Write-Output "  Start-Process 'santabase-stealth://open?curp=OIRM840921HDFRMR05&estado=Jalisco'"
