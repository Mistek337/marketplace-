# Скачивает Linux-колёса на хосте (обход SSL/таймаутов PyPI внутри docker build).
# Запуск из корня neomarket:
#   powershell -File moderation/scripts/download-wheels.ps1
#
# Если pypi.org недоступен, попробуйте зеркало:
#   $env:PIP_INDEX_URL = "https://pypi.org/simple"
#   powershell -File moderation/scripts/download-wheels.ps1
$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
$Wheels = Join-Path $Root "docker\wheels"
New-Item -ItemType Directory -Force -Path $Wheels | Out-Null
Remove-Item (Join-Path $Wheels "*.whl") -ErrorAction SilentlyContinue
Remove-Item (Join-Path $Wheels "*.tar.gz") -ErrorAction SilentlyContinue

$pipArgs = @(
    "download",
    "-r", (Join-Path $Root "requirements.txt"),
    "-d", $Wheels,
    "--platform", "manylinux2014_x86_64",
    "--python-version", "3.11",
    "--implementation", "cp",
    "--abi", "cp311",
    "--only-binary", ":all:"
)
if ($env:PIP_INDEX_URL) {
    $pipArgs += @("-i", $env:PIP_INDEX_URL)
}

Write-Host "Downloading wheels for Linux (Python 3.11) into $Wheels ..."
python -m pip @pipArgs
if (-not (Get-ChildItem $Wheels -Filter *.whl -ErrorAction SilentlyContinue)) {
    throw "No .whl files downloaded. Check internet/VPN or set PIP_INDEX_URL to another mirror."
}
Write-Host "Done. Rebuild: docker compose build moderation"
